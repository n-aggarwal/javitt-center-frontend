from typing import Dict, Any
from .database import DatabaseService
from .bedrock_client import BedrockClient
from .schema_cache import SchemaCache
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchemaInitializer:
    """
    Agent that initializes the database schema, structured schema, and data dictionary.
    This runs once when the database is first loaded and caches the results.
    """

    def __init__(self, db_service: DatabaseService, bedrock_client: BedrockClient,
                 cache: SchemaCache):
        """
        Initialize the schema initializer agent.

        Args:
            db_service: DatabaseService instance
            bedrock_client: BedrockClient instance
            cache: SchemaCache instance
        """
        self.db_service = db_service
        self.bedrock_client = bedrock_client
        self.cache = cache

    def initialize_schema(self, db_path: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Initialize schema and data dictionary for the database.
        This is the main agentic workflow that orchestrates all agents.

        Workflow:
        1. Agent 1: Extract raw schema and sample data
        2. Agent 2: Analyze schema with Bedrock to get structured schema
        3. Agent 3: Generate data dictionary with Bedrock
        4. Cache all results

        Args:
            db_path: Path to database file
            force_refresh: If True, regenerate even if cache exists

        Returns:
            Dictionary containing all schema information
        """
        # Check if cache exists and is valid
        if not force_refresh and self.cache.has_cache(db_path):
            logger.info(f"Loading schema from cache for {db_path}")
            return self._load_from_cache(db_path)

        logger.info(f"Initializing schema for {db_path} (this may take a moment...)")

        # Agent 1: Schema Extraction Agent
        logger.info("Agent 1: Extracting raw schema and sample data...")
        raw_schema, sample_data = self._extract_raw_schema()
        self.cache.save_raw_schema(db_path, raw_schema, sample_data)

        # Agent 2: Schema Analysis Agent
        logger.info("Agent 2: Analyzing schema with Bedrock...")
        structured_schema = self._analyze_schema(raw_schema, sample_data)
        self.cache.save_structured_schema(db_path, structured_schema)

        # Agent 3: Data Dictionary Generation Agent
        logger.info("Agent 3: Generating data dictionary with Bedrock...")
        data_dictionary = self._generate_data_dictionary(structured_schema, sample_data)
        self.cache.save_data_dictionary(db_path, data_dictionary)

        logger.info("Schema initialization complete!")

        return {
            'raw_schema': raw_schema,
            'sample_data': sample_data,
            'structured_schema': structured_schema,
            'data_dictionary': data_dictionary
        }

    def _extract_raw_schema(self) -> tuple[str, Dict[str, Any]]:
        """
        Agent 1: Extract raw schema and sample data from database.

        Returns:
            Tuple of (raw_schema, sample_data)
        """
        # Get raw schema
        raw_schema = self.db_service.get_schema()

        # Get sample data from all tables
        tables = self.db_service.get_all_tables()
        sample_data = {}

        for table in tables:
            try:
                # Get 5 sample rows from each table
                sample_data[table] = self.db_service.get_sample_data(table, limit=5)
            except Exception as e:
                logger.warning(f"Could not get sample data for table {table}: {e}")
                sample_data[table] = []

        return raw_schema, sample_data

    def _analyze_schema(self, raw_schema: str, sample_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agent 2: Analyze schema using Bedrock to get structured information.

        Args:
            raw_schema: Raw schema string
            sample_data: Sample data from tables

        Returns:
            Structured schema dictionary
        """
        structured_schema = self.bedrock_client.analyze_schema(raw_schema, sample_data)
        return structured_schema

    def _generate_data_dictionary(self, structured_schema: Dict[str, Any],
                                   sample_data: Dict[str, Any]) -> str:
        """
        Agent 3: Generate data dictionary using Bedrock.

        Args:
            structured_schema: Structured schema from Agent 2
            sample_data: Sample data from tables

        Returns:
            Data dictionary as formatted string
        """
        data_dictionary = self.bedrock_client.generate_data_dictionary(
            structured_schema,
            sample_data
        )
        return data_dictionary

    def _load_from_cache(self, db_path: str) -> Dict[str, Any]:
        """
        Load all schema information from cache.

        Args:
            db_path: Path to database file

        Returns:
            Dictionary containing all schema information
        """
        raw_schema_data = self.cache.load_raw_schema(db_path)
        structured_schema = self.cache.load_structured_schema(db_path)
        data_dictionary = self.cache.load_data_dictionary(db_path)

        return {
            'raw_schema': raw_schema_data['raw_schema'],
            'sample_data': raw_schema_data['sample_data'],
            'structured_schema': structured_schema,
            'data_dictionary': data_dictionary
        }

    def get_schema_info(self, db_path: str) -> Dict[str, Any]:
        """
        Get schema information, initializing if necessary.

        Args:
            db_path: Path to database file

        Returns:
            Dictionary containing schema information
        """
        if not self.cache.has_cache(db_path):
            return self.initialize_schema(db_path)
        else:
            return self._load_from_cache(db_path)

    def refresh_schema(self, db_path: str) -> Dict[str, Any]:
        """
        Force refresh of schema and data dictionary.

        Args:
            db_path: Path to database file

        Returns:
            Dictionary containing refreshed schema information
        """
        logger.info(f"Force refreshing schema for {db_path}")
        self.cache.clear_cache(db_path)
        return self.initialize_schema(db_path, force_refresh=True)
