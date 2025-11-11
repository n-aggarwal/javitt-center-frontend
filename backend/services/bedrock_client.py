import boto3
import json
from typing import Optional, List, Dict, Any


class BedrockClient:
    def __init__(self, region_name: str, model_id: str):
        """
        Initialize AWS Bedrock client.

        Args:
            region_name: AWS region (e.g., 'us-east-1')
            model_id: Bedrock model ID (e.g., 'anthropic.claude-3-5-sonnet-20241022-v2:0')
        """
        self.region_name = region_name
        self.model_id = model_id
        self.client = boto3.client('bedrock-runtime', region_name=region_name)

    def generate_sql(self, natural_language_query: str, database_schema: str,
                     conversation_history: List[Dict[str, Any]] = None,
                     data_dictionary: Optional[str] = None,
                     similar_examples: List[Dict[str, str]] = None) -> str:
        """
        Convert natural language query to SQL using AWS Bedrock with conversation context and RAG examples.

        Args:
            natural_language_query: The user's question in natural language
            database_schema: String describing the database schema
            conversation_history: Previous conversation messages for context
            data_dictionary: Optional data dictionary with column descriptions and business rules
            similar_examples: Optional list of similar query examples from RAG

        Returns:
            Generated SQL query string
        """
        # Build messages array with conversation history
        messages = []

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg.get("role"),
                    "content": msg.get("content")
                })

        # Construct the current prompt for Claude
        prompt = f"""You are a SQL expert. Given a database schema, a natural language question, and a database dictionary if provided, generate a valid SQLite query.

{database_schema}
"""

        # Add data dictionary if provided
        if data_dictionary:
            prompt += f"""
Data Dictionary (Column Descriptions and Business Rules):
{data_dictionary}
"""

        # Add similar examples from RAG if provided
        if similar_examples and len(similar_examples) > 0:
            prompt += "\n\nHere are some similar example queries to help guide your response:\n\n"
            for i, example in enumerate(similar_examples, 1):
                prompt += f"Example {i}:\n"
                prompt += f"Question: {example['natural_language_query']}\n"
                prompt += f"SQL: {example['sql_query']}\n\n"

        prompt += f"""
User Question: {natural_language_query}

Important instructions:
1. Generate ONLY the SQL query, no explanations
2. Use proper SQLite syntax
3. Return only SELECT queries (no INSERT, UPDATE, DELETE, DROP, etc.)
4. Make sure the query is safe and optimized
5. Use proper JOIN clauses when needed
6. Include appropriate WHERE clauses to filter results
7. Return ONLY the SQL query without any markdown formatting, backticks, or code blocks
8. Consider previous conversation context when generating the query
9. Use the data dictionary to understand column meanings and business rules
10. Do NOT use dollar signs ($) for currency - use plain numbers instead

SQL Query:"""

        # Add current query to messages
        messages.append({
            "role": "user",
            "content": prompt
        })

        # Prepare the request body for Claude
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": messages,
            "temperature": 0.1,  # Low temperature for more deterministic output
        }

        try:
            # Call Bedrock API
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())

            # Extract the generated SQL
            sql_query = response_body['content'][0]['text'].strip()

            # Clean up the response (remove any markdown formatting if present)
            sql_query = self._clean_sql_response(sql_query)

            return sql_query

        except Exception as e:
            raise Exception(f"Error calling Bedrock API: {str(e)}")

    def _clean_sql_response(self, sql: str) -> str:
        """
        Clean up the SQL response by removing markdown formatting or extra text.

        Args:
            sql: Raw SQL response from the model

        Returns:
            Cleaned SQL query
        """
        # Remove markdown code blocks if present
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0].strip()

        # Remove "SQL Query:" prefix if present
        if sql.lower().startswith("sql query:"):
            sql = sql[10:].strip()

        # Remove any leading/trailing whitespace
        sql = sql.strip()

        # Remove semicolon at the end if present
        if sql.endswith(';'):
            sql = sql[:-1].strip()

        return sql

    def chat_with_results(self, natural_language_query: str, sql_query: str,
                          results: list, error: Optional[str] = None,
                          conversation_history: List[Dict[str, Any]] = None) -> str:
        """
        Generate a natural language response based on the query results with conversation context.

        Args:
            natural_language_query: Original user question
            sql_query: Generated SQL query
            results: Query results
            error: Error message if query failed
            conversation_history: Previous conversation messages for context

        Returns:
            Natural language explanation of results
        """
        # Build messages array with conversation history
        messages = []

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg.get("role"),
                    "content": msg.get("content")
                })

        # Build the prompt for explanation
        if error:
            prompt = f"""The user asked: "{natural_language_query}"

We generated this SQL query: {sql_query}

But it resulted in an error: {error}

Please explain what went wrong in simple terms and suggest what might be needed."""

        else:
            prompt = f"""The user asked: "{natural_language_query}"

We ran this SQL query: {sql_query}

Results: {json.dumps(results, indent=2)}

Please provide a natural language summary of the results in 2-3 sentences.

IMPORTANT: Do NOT use dollar signs ($) when mentioning currency values. Instead, write currency amounts without the dollar sign (e.g., write "1,117.90" instead of "$1,117.90"). The frontend will handle currency formatting."""

        # Add current prompt to messages
        messages.append({
            "role": "user",
            "content": prompt
        })

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": messages,
            "temperature": 0.7,
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            explanation = response_body['content'][0]['text'].strip()

            return explanation

        except Exception as e:
            return f"Query executed successfully but couldn't generate explanation: {str(e)}"

    def analyze_schema(self, raw_schema: str, sample_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze raw database schema and return structured version.

        Args:
            raw_schema: Raw schema string from database
            sample_data: Sample data from each table for pattern analysis

        Returns:
            Structured schema dictionary
        """
        prompt = f"""You are a database expert. Analyze this SQLite database schema and sample data.

Raw Schema:
{raw_schema}

Sample Data (first few rows from each table):
{json.dumps(sample_data, indent=2, default=str)}

Analyze the schema and provide a structured JSON response with:
1. Tables and their purposes
2. Column types and meanings
3. Relationships between tables (foreign keys, implied relationships)
4. Data patterns observed in sample data
5. Potential primary and foreign keys

Return ONLY valid JSON in this format:
{{
  "tables": {{
    "table_name": {{
      "purpose": "brief description",
      "columns": [
        {{
          "name": "column_name",
          "type": "data_type",
          "meaning": "what this column represents",
          "patterns": "observed patterns from sample data"
        }}
      ],
      "relationships": [
        {{"type": "foreign_key", "references": "other_table.column", "description": "relationship description"}}
      ]
    }}
  }}
}}

Return only the JSON, no additional text."""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "messages": [{
                "role": "user",
                "content": prompt
            }],
            "temperature": 0.3
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            result_text = response_body['content'][0]['text'].strip()

            # Clean JSON response (remove markdown if present)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            # Parse JSON
            structured_schema = json.loads(result_text)
            return structured_schema

        except Exception as e:
            raise Exception(f"Error analyzing schema: {str(e)}")

    def generate_data_dictionary(self, structured_schema: Dict[str, Any],
                                  sample_data: Dict[str, Any]) -> str:
        """
        Generate human-readable data dictionary from structured schema.

        Args:
            structured_schema: Structured schema from analyze_schema()
            sample_data: Sample data from each table

        Returns:
            Data dictionary as formatted string
        """
        prompt = f"""You are a database documentation expert. Create a comprehensive data dictionary based on this structured schema analysis.

Structured Schema:
{json.dumps(structured_schema, indent=2)}

Sample Data:
{json.dumps(sample_data, indent=2, default=str)}

Create a data dictionary that includes:
1. Each table and column with clear descriptions
2. Data types and constraints
3. Business rules inferred from the data
4. Relationships between tables
5. Valid values or ranges (based on sample data)
6. Any naming conventions or patterns

Format the dictionary in a clear, readable way like:

tablename.columnname: Description (Type)
- Business rule if applicable
- Valid values or patterns

Example:
customers.customer_id: Unique identifier for each customer (INTEGER)
- Primary key, auto-incremented

customers.status: Customer account status (INTEGER)
- 1 = active, 0 = inactive
- Default appears to be 1

orders.customer_id: Reference to customer who placed the order (INTEGER)
- Foreign key referencing customers.customer_id

Provide the complete data dictionary for all tables and columns."""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "messages": [{
                "role": "user",
                "content": prompt
            }],
            "temperature": 0.4
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            data_dictionary = response_body['content'][0]['text'].strip()

            return data_dictionary

        except Exception as e:
            raise Exception(f"Error generating data dictionary: {str(e)}")
