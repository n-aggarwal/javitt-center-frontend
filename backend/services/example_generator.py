import json
from typing import List, Dict, Any
from .database import DatabaseService
from .bedrock_client import BedrockClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExampleGenerator:
    """
    Generate diverse natural language to SQL query examples for RAG.

    Uses the database schema and AI to create realistic, varied examples.
    """

    def __init__(self, db_service: DatabaseService, bedrock_client: BedrockClient):
        """
        Initialize example generator.

        Args:
            db_service: DatabaseService instance
            bedrock_client: BedrockClient instance
        """
        self.db_service = db_service
        self.bedrock_client = bedrock_client

    def generate_examples(self, num_examples: int = 50) -> List[Dict[str, str]]:
        """
        Generate diverse natural language to SQL query examples.

        Args:
            num_examples: Number of examples to generate

        Returns:
            List of dicts with 'natural_language_query' and 'sql_query'
        """
        logger.info(f"Generating {num_examples} example queries...")

        # Get database schema and sample data
        schema = self.db_service.get_schema()
        tables = self.db_service.get_all_tables()

        # Get sample data from each table for context
        sample_data = {}
        for table in tables:
            try:
                sample_data[table] = self.db_service.get_sample_data(table, limit=3)
            except Exception as e:
                logger.warning(f"Could not get sample data for {table}: {e}")
                sample_data[table] = []

        # Create prompt for example generation
        prompt = f"""You are a SQL expert. Generate {num_examples} diverse, realistic natural language to SQL query examples based on this database schema.

{schema}

Sample Data:
{json.dumps(sample_data, indent=2, default=str)}

Requirements:
1. Create {num_examples} different examples covering various query types:
   - Simple SELECT queries (e.g., "Show all customers")
   - COUNT queries (e.g., "How many orders were placed?")
   - WHERE clauses with filters (e.g., "Find customers in New York")
   - JOIN queries (e.g., "Show orders with customer names")
   - GROUP BY and aggregations (e.g., "Total sales by customer")
   - ORDER BY and LIMIT (e.g., "Top 10 customers by revenue")
   - Date/time filters
   - Multiple conditions
   - Nested queries when appropriate
   - Various complexity levels (simple to advanced)

2. Make queries realistic and business-oriented
3. Use actual column names from the schema
4. Ensure SQL queries are valid SQLite syntax
5. Cover all tables in the schema
6. Vary the complexity and structure

Return ONLY a valid JSON array with this exact format:
[
  {{
    "natural_language_query": "the question in plain English",
    "sql_query": "the corresponding SQL query"
  }},
  ...
]

Important:
- Return ONLY the JSON array, no additional text or explanation
- Do NOT use markdown code blocks
- Each SQL query should be valid and executable
- Natural language queries should be conversational and varied
- Do NOT use dollar signs ($) in queries"""

        try:
            # Call Bedrock to generate examples
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 8000,
                "messages": [{
                    "role": "user",
                    "content": prompt
                }],
                "temperature": 0.8,  # Higher temperature for more diversity
            }

            response = self.bedrock_client.client.invoke_model(
                modelId=self.bedrock_client.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            result_text = response_body['content'][0]['text'].strip()

            # Clean the response (remove markdown if present)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            # Parse JSON
            examples = json.loads(result_text)

            # Validate examples
            validated_examples = []
            for ex in examples:
                if isinstance(ex, dict) and 'natural_language_query' in ex and 'sql_query' in ex:
                    # Clean up SQL (remove semicolons, extra whitespace)
                    sql = ex['sql_query'].strip()
                    if sql.endswith(';'):
                        sql = sql[:-1].strip()

                    validated_examples.append({
                        'natural_language_query': ex['natural_language_query'].strip(),
                        'sql_query': sql
                    })

            logger.info(f"Generated {len(validated_examples)} valid examples")

            # If we didn't get enough examples, generate more
            if len(validated_examples) < num_examples:
                logger.warning(f"Only generated {len(validated_examples)} examples, expected {num_examples}")

            return validated_examples[:num_examples]  # Return exactly num_examples

        except Exception as e:
            logger.error(f"Error generating examples: {e}")
            # Return some basic fallback examples if generation fails
            return self._get_fallback_examples(tables)

    def _get_fallback_examples(self, tables: List[str]) -> List[Dict[str, str]]:
        """
        Generate basic fallback examples if AI generation fails.

        Args:
            tables: List of table names

        Returns:
            List of basic example queries
        """
        logger.info("Using fallback example generation")

        examples = []

        for table in tables[:10]:  # Limit to first 10 tables
            # Basic SELECT
            examples.append({
                'natural_language_query': f"Show all {table}",
                'sql_query': f"SELECT * FROM {table} LIMIT 100"
            })

            # Count
            examples.append({
                'natural_language_query': f"How many {table} are there?",
                'sql_query': f"SELECT COUNT(*) as count FROM {table}"
            })

        return examples[:50]  # Return up to 50 examples
