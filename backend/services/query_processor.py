from typing import Dict, Any, List, Optional
from .database import DatabaseService
from .bedrock_client import BedrockClient


class QueryProcessor:
    def __init__(self, db_service: DatabaseService, bedrock_client: BedrockClient):
        """
        Initialize the query processor with database and Bedrock services.

        Args:
            db_service: DatabaseService instance
            bedrock_client: BedrockClient instance
        """
        self.db_service = db_service
        self.bedrock_client = bedrock_client

    def process_natural_language_query(self, natural_language_query: str,
                                       include_explanation: bool = True,
                                       conversation_history: List[Dict[str, Any]] = None,
                                       data_dictionary: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a natural language query end-to-end with conversation context and data dictionary.

        Args:
            natural_language_query: User's question in natural language
            include_explanation: Whether to generate natural language explanation of results
            conversation_history: Previous conversation messages for context
            data_dictionary: Optional data dictionary with column descriptions and business rules

        Returns:
            Dictionary containing:
                - success: bool
                - query: original natural language query
                - sql: generated SQL query
                - results: query results (if successful)
                - columns: column names (if successful)
                - explanation: natural language explanation (if requested)
                - error: error message (if failed)
        """
        response = {
            "success": False,
            "query": natural_language_query,
            "sql": None,
            "results": None,
            "columns": None,
            "explanation": None,
            "error": None
        }

        try:
            # Step 1: Get database schema
            schema = self.db_service.get_schema()

            # Step 2: Generate SQL using Bedrock with conversation history and data dictionary
            sql_query = self.bedrock_client.generate_sql(
                natural_language_query,
                schema,
                conversation_history=conversation_history,
                data_dictionary=data_dictionary
            )
            response["sql"] = sql_query

            # Step 3: Execute the SQL query
            results, columns = self.db_service.execute_query(sql_query)
            response["results"] = results
            response["columns"] = columns
            response["success"] = True

            # Step 4: Generate natural language explanation (optional)
            if include_explanation:
                explanation = self.bedrock_client.chat_with_results(
                    natural_language_query,
                    sql_query,
                    results,
                    conversation_history=conversation_history
                )
                response["explanation"] = explanation

        except Exception as e:
            response["error"] = str(e)
            response["success"] = False

            # Try to generate an explanation of what went wrong
            if include_explanation and response["sql"]:
                try:
                    explanation = self.bedrock_client.chat_with_results(
                        natural_language_query,
                        response["sql"],
                        [],
                        error=str(e),
                        conversation_history=conversation_history
                    )
                    response["explanation"] = explanation
                except:
                    pass  # If explanation fails, just skip it

        return response

    def get_database_info(self) -> Dict[str, Any]:
        """
        Get information about the database structure.

        Returns:
            Dictionary containing:
                - tables: list of table names
                - schema: full schema description
                - sample_data: sample data from each table
        """
        tables = self.db_service.get_all_tables()
        schema = self.db_service.get_schema()

        # Get sample data from each table
        sample_data = {}
        for table in tables:
            try:
                sample_data[table] = self.db_service.get_sample_data(table, limit=3)
            except Exception as e:
                sample_data[table] = f"Error getting sample data: {str(e)}"

        return {
            "tables": tables,
            "schema": schema,
            "sample_data": sample_data
        }

    def execute_direct_sql(self, sql_query: str) -> Dict[str, Any]:
        """
        Execute a SQL query directly without using Bedrock.

        Args:
            sql_query: SQL query string

        Returns:
            Dictionary containing:
                - success: bool
                - sql: the SQL query
                - results: query results (if successful)
                - columns: column names (if successful)
                - error: error message (if failed)
        """
        response = {
            "success": False,
            "sql": sql_query,
            "results": None,
            "columns": None,
            "error": None
        }

        try:
            results, columns = self.db_service.execute_query(sql_query)
            response["results"] = results
            response["columns"] = columns
            response["success"] = True

        except Exception as e:
            response["error"] = str(e)
            response["success"] = False

        return response
