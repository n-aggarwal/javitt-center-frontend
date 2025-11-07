import sqlite3
from typing import List, Dict, Any, Tuple
import os


class DatabaseService:
    def __init__(self, db_path: str):
        """Initialize the database service with the path to SQLite database."""
        self.db_path = db_path
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    def get_schema(self) -> str:
        """
        Get the database schema in a format suitable for sending to LLM.
        Returns a string describing all tables and their columns.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cursor.fetchall()

        schema_description = "Database Schema:\n\n"

        for table in tables:
            table_name = table[0]
            schema_description += f"Table: {table_name}\n"

            # Get column info for each table
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()

            for col in columns:
                col_id, col_name, col_type, not_null, default_val, pk = col
                schema_description += f"  - {col_name} ({col_type})"
                if pk:
                    schema_description += " PRIMARY KEY"
                if not_null:
                    schema_description += " NOT NULL"
                schema_description += "\n"

            schema_description += "\n"

        conn.close()
        return schema_description

    def execute_query(self, query: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Execute a SQL query and return results.

        Args:
            query: SQL query string to execute

        Returns:
            Tuple of (results as list of dicts, column names)
        """
        # Basic validation to prevent dangerous operations
        query_upper = query.strip().upper()
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']

        for keyword in dangerous_keywords:
            if query_upper.startswith(keyword):
                raise ValueError(f"Query type '{keyword}' is not allowed. Only SELECT queries are permitted.")

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(query)

            # Get column names
            columns = [description[0] for description in cursor.description] if cursor.description else []

            # Fetch results
            rows = cursor.fetchall()

            # Convert rows to list of dictionaries
            results = []
            for row in rows:
                row_dict = {}
                for idx, col_name in enumerate(columns):
                    row_dict[col_name] = row[idx]
                results.append(row_dict)

            return results, columns

        except sqlite3.Error as e:
            raise Exception(f"Database error: {str(e)}")

        finally:
            conn.close()

    def get_sample_data(self, table_name: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get sample data from a specific table.

        Args:
            table_name: Name of the table
            limit: Number of rows to return

        Returns:
            List of dictionaries representing rows
        """
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        results, _ = self.execute_query(query)
        return results

    def get_all_tables(self) -> List[str]:
        """Get list of all table names in the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
