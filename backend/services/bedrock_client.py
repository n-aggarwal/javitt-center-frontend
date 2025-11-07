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
                     conversation_history: List[Dict[str, Any]] = None) -> str:
        """
        Convert natural language query to SQL using AWS Bedrock with conversation context.

        Args:
            natural_language_query: The user's question in natural language
            database_schema: String describing the database schema
            conversation_history: Previous conversation messages for context

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

Please provide a natural language summary of the results in 2-3 sentences."""

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
