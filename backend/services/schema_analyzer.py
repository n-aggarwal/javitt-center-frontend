from typing import Dict, Any, Optional
from .database import DatabaseService
from .bedrock_client import BedrockClient
import json


class SchemaAnalyzer:
    """
    Analyzes database schema and automatically generates data dictionary using Bedrock.
    This is done once on initialization and cached for all subsequent queries.
    """

    def __init__(self, db_service: DatabaseService, bedrock_client: BedrockClient):
        """
        Initialize the schema analyzer.

        Args:
            db_service: DatabaseService instance
            bedrock_client: BedrockClient instance
        """
        self.db_service = db_service
        self.bedrock_client = bedrock_client

        # Cache for schema and data dictionary
        self._structured_schema: Optional[Dict[str, Any]] = None
        self._data_dictionary: Optional[str] = None
        self._is_initialized: bool = False

    def is_initialized(self) -> bool:
        """Check if schema analysis has been performed."""
        return self._is_initialized

    def get_structured_schema(self) -> Optional[Dict[str, Any]]:
        """Get the structured schema (cached)."""
        return self._structured_schema

    def get_data_dictionary(self) -> Optional[str]:
        """Get the auto-generated data dictionary (cached)."""
        return self._data_dictionary

    def initialize(self) -> Dict[str, Any]:
        """
        Perform initial schema analysis and data dictionary generation.
        This should be called once when the database is first loaded.

        Returns:
            Dictionary containing:
                - success: bool
                - structured_schema: Dict with parsed schema
                - data_dictionary: str with generated data dictionary
                - error: str if failed
        """
        result = {
            "success": False,
            "structured_schema": None,
            "data_dictionary": None,
            "error": None
        }

        try:
            # Step 1: Get raw schema from database
            raw_schema = self.db_service.get_schema()
            tables = self.db_service.get_all_tables()

            # Step 2: Get sample data for pattern analysis
            sample_data = {}
            for table in tables:
                try:
                    sample_data[table] = self.db_service.get_sample_data(table, limit=5)
                except:
                    sample_data[table] = []

            # Step 3: Use Bedrock to analyze and structure the schema
            self._structured_schema = self.bedrock_client.analyze_schema(
                raw_schema,
                sample_data
            )

            # Step 4: Use Bedrock to generate data dictionary from structured schema
            self._data_dictionary = self.bedrock_client.generate_data_dictionary(
                self._structured_schema,
                sample_data
            )

            # Mark as initialized
            self._is_initialized = True

            result["success"] = True
            result["structured_schema"] = self._structured_schema
            result["data_dictionary"] = self._data_dictionary

        except Exception as e:
            result["error"] = str(e)
            self._is_initialized = False

        return result

    def get_info(self) -> Dict[str, Any]:
        """
        Get current state of schema analysis.

        Returns:
            Dictionary with initialization status and cached data
        """
        return {
            "is_initialized": self._is_initialized,
            "structured_schema": self._structured_schema,
            "data_dictionary": self._data_dictionary
        }

    def reset(self):
        """Reset the analyzer (for re-initialization)."""
        self._structured_schema = None
        self._data_dictionary = None
        self._is_initialized = False
