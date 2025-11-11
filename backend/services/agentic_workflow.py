from typing import Dict, Any, List, Optional
from .database import DatabaseService
from .bedrock_client import BedrockClient
from .schema_cache import SchemaCache
from .schema_initializer import SchemaInitializer
from .rag_service import RAGService
from .example_generator import ExampleGenerator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgenticWorkflow:
    """
    Main agentic workflow service that orchestrates query processing.

    This service ensures that:
    1. Schema and data dictionary are initialized once on database load
    2. All queries use the cached schema and data dictionary
    3. The workflow is efficient and maintainable
    """

    def __init__(self, db_service: DatabaseService, bedrock_client: BedrockClient,
                 db_path: str, cache_dir: str = ".cache", data_dir: str = "data"):
        """
        Initialize the agentic workflow.

        Args:
            db_service: DatabaseService instance
            bedrock_client: BedrockClient instance
            db_path: Path to the database file
            cache_dir: Directory for caching
            data_dir: Directory for RAG data storage
        """
        self.db_service = db_service
        self.bedrock_client = bedrock_client
        self.db_path = db_path

        # Initialize cache and schema initializer
        self.cache = SchemaCache(cache_dir)
        self.schema_initializer = SchemaInitializer(db_service, bedrock_client, self.cache)

        # Initialize RAG service and example generator
        self.rag_service = RAGService(data_dir=data_dir)
        self.example_generator = ExampleGenerator(db_service, bedrock_client)

        # Schema information (loaded lazily)
        self._schema_info = None

    def _ensure_schema_initialized(self):
        """
        Ensure schema and data dictionary are initialized.
        This is called automatically before processing queries.
        """
        if self._schema_info is None:
            logger.info("Schema not loaded, initializing...")
            self._schema_info = self.schema_initializer.get_schema_info(self.db_path)
            logger.info("Schema loaded successfully")

    def process_query(self, natural_language_query: str,
                     include_explanation: bool = True,
                     conversation_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Agent 4: Query Agent - Process a natural language query using cached schema and data dictionary.

        Args:
            natural_language_query: User's question in natural language
            include_explanation: Whether to generate natural language explanation of results
            conversation_history: Previous conversation messages for context

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
        # Ensure schema and data dictionary are initialized
        self._ensure_schema_initialized()

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
            # Step 1: Get schema and data dictionary from cache
            raw_schema = self._schema_info['raw_schema']
            data_dictionary = self._schema_info['data_dictionary']

            logger.info(f"Processing query: {natural_language_query[:50]}...")

            # Step 1.5: Retrieve similar examples using RAG
            similar_examples = []
            try:
                similar_examples = self.rag_service.find_similar_examples(
                    natural_language_query,
                    k=3  # Retrieve top 3 similar examples
                )
                if similar_examples:
                    logger.info(f"Retrieved {len(similar_examples)} similar examples from RAG")
            except Exception as e:
                logger.warning(f"Could not retrieve RAG examples: {e}")

            # Step 2: Generate SQL using Bedrock with schema, data dictionary, and RAG examples
            sql_query = self.bedrock_client.generate_sql(
                natural_language_query,
                raw_schema,
                conversation_history=conversation_history,
                data_dictionary=data_dictionary,
                similar_examples=similar_examples
            )
            response["sql"] = sql_query
            logger.info(f"Generated SQL: {sql_query}")

            # Step 3: Execute the SQL query
            results, columns = self.db_service.execute_query(sql_query)
            response["results"] = results
            response["columns"] = columns
            response["success"] = True
            logger.info(f"Query executed successfully, returned {len(results)} rows")

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
            logger.error(f"Error processing query: {e}")
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
                - raw_schema: full schema description
                - structured_schema: analyzed schema structure
                - data_dictionary: data dictionary
                - sample_data: sample data from each table
        """
        # Ensure schema is initialized
        self._ensure_schema_initialized()

        tables = self.db_service.get_all_tables()

        return {
            "tables": tables,
            "raw_schema": self._schema_info['raw_schema'],
            "structured_schema": self._schema_info['structured_schema'],
            "data_dictionary": self._schema_info['data_dictionary'],
            "sample_data": self._schema_info['sample_data']
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

    def refresh_schema(self) -> Dict[str, Any]:
        """
        Force refresh of schema and data dictionary.
        Useful when the database structure has changed.

        Returns:
            Updated schema information
        """
        logger.info("Refreshing schema and data dictionary...")
        self._schema_info = self.schema_initializer.refresh_schema(self.db_path)
        logger.info("Schema refresh complete")
        return self.get_database_info()

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the cache status.

        Returns:
            Dictionary with cache status and metadata
        """
        return self.cache.get_cache_info(self.db_path)

    def initialize_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Explicitly initialize or refresh the schema.

        Args:
            force_refresh: If True, regenerate even if cache exists

        Returns:
            Schema information
        """
        logger.info("Initializing schema...")
        self._schema_info = self.schema_initializer.initialize_schema(
            self.db_path,
            force_refresh=force_refresh
        )
        logger.info("Schema initialization complete")
        return self.get_database_info()

    def generate_rag_examples(self, num_examples: int = 50) -> Dict[str, Any]:
        """
        Generate RAG examples for improved query processing.

        Args:
            num_examples: Number of examples to generate

        Returns:
            Dictionary with generation status and examples
        """
        logger.info(f"Generating {num_examples} RAG examples...")

        try:
            # Generate examples using the example generator
            examples = self.example_generator.generate_examples(num_examples)

            # Add examples to RAG service
            self.rag_service.add_examples(examples)

            logger.info(f"Successfully generated and stored {len(examples)} RAG examples")

            return {
                "success": True,
                "num_examples": len(examples),
                "examples": examples
            }

        except Exception as e:
            logger.error(f"Error generating RAG examples: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_rag_info(self) -> Dict[str, Any]:
        """
        Get information about the RAG system.

        Returns:
            Dictionary with RAG system stats
        """
        return self.rag_service.get_stats()

    def get_rag_examples(self) -> List[Dict[str, str]]:
        """
        Get all RAG examples.

        Returns:
            List of all examples
        """
        return self.rag_service.get_all_examples()

    def clear_rag_examples(self):
        """Clear all RAG examples."""
        self.rag_service.clear_examples()
        logger.info("Cleared all RAG examples")
