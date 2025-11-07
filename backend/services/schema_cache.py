import json
import os
import hashlib
from typing import Dict, Any, Optional
from pathlib import Path


class SchemaCache:
    """
    Manages caching of database schema and data dictionary.
    Schema and data dictionary are computed once and cached to disk.
    """

    def __init__(self, cache_dir: str = ".cache"):
        """
        Initialize the schema cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _get_db_hash(self, db_path: str) -> str:
        """
        Generate a hash of the database file to detect changes.

        Args:
            db_path: Path to database file

        Returns:
            MD5 hash of database file
        """
        hash_md5 = hashlib.md5()
        with open(db_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _get_cache_path(self, db_path: str, cache_type: str) -> Path:
        """
        Get the cache file path for a specific cache type.

        Args:
            db_path: Path to database file
            cache_type: Type of cache ('schema', 'structured_schema', 'data_dictionary')

        Returns:
            Path to cache file
        """
        db_hash = self._get_db_hash(db_path)
        db_name = Path(db_path).stem
        return self.cache_dir / f"{db_name}_{db_hash}_{cache_type}.json"

    def has_cache(self, db_path: str) -> bool:
        """
        Check if cache exists for the database.

        Args:
            db_path: Path to database file

        Returns:
            True if all required cache files exist
        """
        required_caches = ['raw_schema', 'structured_schema', 'data_dictionary']
        return all(
            self._get_cache_path(db_path, cache_type).exists()
            for cache_type in required_caches
        )

    def save_raw_schema(self, db_path: str, raw_schema: str, sample_data: Dict[str, Any]):
        """
        Save raw schema and sample data to cache.

        Args:
            db_path: Path to database file
            raw_schema: Raw schema string
            sample_data: Sample data from tables
        """
        cache_path = self._get_cache_path(db_path, 'raw_schema')
        data = {
            'raw_schema': raw_schema,
            'sample_data': sample_data
        }
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def load_raw_schema(self, db_path: str) -> Optional[Dict[str, Any]]:
        """
        Load raw schema from cache.

        Args:
            db_path: Path to database file

        Returns:
            Dictionary with raw_schema and sample_data, or None if not cached
        """
        cache_path = self._get_cache_path(db_path, 'raw_schema')
        if not cache_path.exists():
            return None

        with open(cache_path, 'r') as f:
            return json.load(f)

    def save_structured_schema(self, db_path: str, structured_schema: Dict[str, Any]):
        """
        Save structured schema to cache.

        Args:
            db_path: Path to database file
            structured_schema: Structured schema dictionary
        """
        cache_path = self._get_cache_path(db_path, 'structured_schema')
        with open(cache_path, 'w') as f:
            json.dump(structured_schema, f, indent=2)

    def load_structured_schema(self, db_path: str) -> Optional[Dict[str, Any]]:
        """
        Load structured schema from cache.

        Args:
            db_path: Path to database file

        Returns:
            Structured schema dictionary, or None if not cached
        """
        cache_path = self._get_cache_path(db_path, 'structured_schema')
        if not cache_path.exists():
            return None

        with open(cache_path, 'r') as f:
            return json.load(f)

    def save_data_dictionary(self, db_path: str, data_dictionary: str):
        """
        Save data dictionary to cache.

        Args:
            db_path: Path to database file
            data_dictionary: Data dictionary string
        """
        cache_path = self._get_cache_path(db_path, 'data_dictionary')
        data = {'data_dictionary': data_dictionary}
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)

    def load_data_dictionary(self, db_path: str) -> Optional[str]:
        """
        Load data dictionary from cache.

        Args:
            db_path: Path to database file

        Returns:
            Data dictionary string, or None if not cached
        """
        cache_path = self._get_cache_path(db_path, 'data_dictionary')
        if not cache_path.exists():
            return None

        with open(cache_path, 'r') as f:
            data = json.load(f)
            return data.get('data_dictionary')

    def clear_cache(self, db_path: str):
        """
        Clear all cache files for a database.

        Args:
            db_path: Path to database file
        """
        cache_types = ['raw_schema', 'structured_schema', 'data_dictionary']
        for cache_type in cache_types:
            cache_path = self._get_cache_path(db_path, cache_type)
            if cache_path.exists():
                cache_path.unlink()

    def get_cache_info(self, db_path: str) -> Dict[str, Any]:
        """
        Get information about cached data.

        Args:
            db_path: Path to database file

        Returns:
            Dictionary with cache status and metadata
        """
        cache_types = ['raw_schema', 'structured_schema', 'data_dictionary']
        info = {
            'db_path': db_path,
            'db_hash': self._get_db_hash(db_path),
            'has_complete_cache': self.has_cache(db_path),
            'cache_files': {}
        }

        for cache_type in cache_types:
            cache_path = self._get_cache_path(db_path, cache_type)
            info['cache_files'][cache_type] = {
                'exists': cache_path.exists(),
                'path': str(cache_path),
                'size': cache_path.stat().st_size if cache_path.exists() else 0
            }

        return info
