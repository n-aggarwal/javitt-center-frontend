import json
import os
import numpy as np
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import faiss
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGService:
    """
    Retrieval-Augmented Generation service for SQL query examples.

    Uses sentence-transformers for embeddings and FAISS for fast similarity search.
    """

    def __init__(self, data_dir: str = "data", model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize RAG service.

        Args:
            data_dir: Directory to store examples and embeddings
            model_name: Sentence-transformers model name
        """
        self.data_dir = data_dir
        self.examples_path = os.path.join(data_dir, "rag_examples.json")
        self.index_path = os.path.join(data_dir, "rag_embeddings.faiss")

        # Initialize sentence-transformers model
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        # Storage
        self.examples: List[Dict[str, str]] = []
        self.index: faiss.Index = None

        # Load existing data if available
        self._load_data()

    def _load_data(self):
        """Load examples and FAISS index from disk."""
        if os.path.exists(self.examples_path) and os.path.exists(self.index_path):
            logger.info("Loading existing RAG examples and index...")

            # Load examples
            with open(self.examples_path, 'r') as f:
                self.examples = json.load(f)

            # Load FAISS index
            self.index = faiss.read_index(self.index_path)

            logger.info(f"Loaded {len(self.examples)} examples")
        else:
            logger.info("No existing RAG data found. Will need to generate examples.")
            # Initialize empty FAISS index
            self.index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product for cosine similarity

    def _save_data(self):
        """Save examples and FAISS index to disk."""
        # Ensure directory exists
        os.makedirs(self.data_dir, exist_ok=True)

        # Save examples
        with open(self.examples_path, 'w') as f:
            json.dump(self.examples, f, indent=2)

        # Save FAISS index
        faiss.write_index(self.index, self.index_path)

        logger.info(f"Saved {len(self.examples)} examples to {self.examples_path}")

    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a text query.

        Args:
            text: Natural language query

        Returns:
            Normalized embedding vector
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        # Normalize for cosine similarity (FAISS uses inner product)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding

    def add_examples(self, examples: List[Dict[str, str]]):
        """
        Add examples to the RAG system.

        Args:
            examples: List of dicts with 'natural_language_query' and 'sql_query' keys
        """
        logger.info(f"Adding {len(examples)} examples to RAG system...")

        # Generate embeddings for all examples
        queries = [ex['natural_language_query'] for ex in examples]
        embeddings = self.model.encode(queries, convert_to_numpy=True, show_progress_bar=True)

        # Normalize embeddings for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms

        # Reset index and add all embeddings
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.index.add(embeddings.astype('float32'))

        # Store examples
        self.examples = examples

        # Save to disk
        self._save_data()

        logger.info(f"Successfully added {len(examples)} examples")

    def find_similar_examples(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Find k most similar examples to the given query.

        Args:
            query: Natural language query
            k: Number of similar examples to return

        Returns:
            List of dicts with 'natural_language_query', 'sql_query', and 'similarity_score'
        """
        if len(self.examples) == 0:
            logger.warning("No examples available for RAG retrieval")
            return []

        # Generate embedding for query
        query_embedding = self.generate_embedding(query)

        # Search in FAISS index
        k = min(k, len(self.examples))  # Don't request more than available
        similarities, indices = self.index.search(
            query_embedding.reshape(1, -1).astype('float32'),
            k
        )

        # Build results
        results = []
        for idx, similarity in zip(indices[0], similarities[0]):
            if idx < len(self.examples):  # Safety check
                result = self.examples[idx].copy()
                result['similarity_score'] = float(similarity)
                results.append(result)

        logger.info(f"Found {len(results)} similar examples for query: {query[:50]}...")

        return results

    def get_all_examples(self) -> List[Dict[str, str]]:
        """Get all stored examples."""
        return self.examples

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RAG system."""
        return {
            "total_examples": len(self.examples),
            "embedding_dimension": self.embedding_dim,
            "model_name": self.model._model_card_data.model_name if hasattr(self.model, '_model_card_data') else "all-MiniLM-L6-v2",
            "index_type": "FAISS IndexFlatIP (cosine similarity)",
            "data_loaded": len(self.examples) > 0
        }

    def clear_examples(self):
        """Clear all examples and reset the index."""
        self.examples = []
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self._save_data()
        logger.info("Cleared all examples")
