"""
FAISS index implementation for fast similarity search over vector embeddings.
"""

import logging
import pickle
import os
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
import faiss
from pathlib import Path

logger = logging.getLogger(__name__)

class FAISSIndex:
    """
    FAISS-based vector index for fast similarity search.
    """
    
    def __init__(self, embedding_dim: int, index_type: str = "flat", metric: str = "cosine"):
        """
        Initialize FAISS index.
        
        Args:
            embedding_dim: Dimension of the embeddings
            index_type: Type of FAISS index ('flat', 'ivf', 'hnsw')
            metric: Distance metric ('cosine', 'l2', 'ip')
        """
        self.embedding_dim = embedding_dim
        self.index_type = index_type
        self.metric = metric
        
        # Initialize the index
        self.index = self._create_index()
        self.metadata = []  # Store metadata for each vector
        self.is_trained = False
        
        logger.info(f"Initialized FAISS index: {index_type}, dim={embedding_dim}, metric={metric}")
    
    def _create_index(self) -> faiss.Index:
        """Create FAISS index based on configuration."""
        if self.metric == "cosine":
            # For cosine similarity, we normalize vectors and use inner product
            index = faiss.IndexFlatIP(self.embedding_dim)
        elif self.metric == "l2":
            index = faiss.IndexFlatL2(self.embedding_dim)
        elif self.metric == "ip":
            index = faiss.IndexFlatIP(self.embedding_dim)
        else:
            raise ValueError(f"Unsupported metric: {self.metric}")
        
        return index
    
    def add_vectors(self, vectors: np.ndarray, metadata: List[Dict[str, Any]]) -> None:
        """
        Add vectors and their metadata to the index.
        
        Args:
            vectors: numpy array of shape (n_vectors, embedding_dim)
            metadata: List of metadata dictionaries for each vector
        """
        if len(vectors) != len(metadata):
            raise ValueError("Number of vectors must match number of metadata entries")
        
        if vectors.shape[1] != self.embedding_dim:
            raise ValueError(f"Vector dimension {vectors.shape[1]} doesn't match index dimension {self.embedding_dim}")
        
        # Normalize vectors for cosine similarity
        if self.metric == "cosine":
            vectors = self._normalize_vectors(vectors)
        
        # Add to index
        self.index.add(vectors.astype(np.float32))
        self.metadata.extend(metadata)
        
        logger.info(f"Added {len(vectors)} vectors to index. Total vectors: {self.index.ntotal}")
    
    def search(self, query_vector: np.ndarray, k: int = 10) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query vector of shape (embedding_dim,)
            k: Number of results to return
            
        Returns:
            Tuple of (distances, indices, metadata)
        """
        if query_vector.shape[0] != self.embedding_dim:
            raise ValueError(f"Query vector dimension {query_vector.shape[0]} doesn't match index dimension {self.embedding_dim}")
        
        if self.index.ntotal == 0:
            return np.array([]), np.array([]), []
        
        # Normalize query vector for cosine similarity
        if self.metric == "cosine":
            query_vector = self._normalize_vector(query_vector)
        
        # Reshape for FAISS
        query_vector = query_vector.reshape(1, -1).astype(np.float32)
        
        # Search
        distances, indices = self.index.search(query_vector, min(k, self.index.ntotal))
        
        # Get metadata for returned indices
        result_metadata = [self.metadata[idx] for idx in indices[0] if idx < len(self.metadata)]
        
        return distances[0], indices[0], result_metadata
    
    def search_batch(self, query_vectors: np.ndarray, k: int = 10) -> Tuple[np.ndarray, np.ndarray, List[List[Dict[str, Any]]]]:
        """
        Search for similar vectors for multiple queries.
        
        Args:
            query_vectors: Query vectors of shape (n_queries, embedding_dim)
            k: Number of results to return per query
            
        Returns:
            Tuple of (distances, indices, metadata_lists)
        """
        if query_vectors.shape[1] != self.embedding_dim:
            raise ValueError(f"Query vector dimension {query_vectors.shape[1]} doesn't match index dimension {self.embedding_dim}")
        
        if self.index.ntotal == 0:
            return np.array([]), np.array([]), []
        
        # Normalize query vectors for cosine similarity
        if self.metric == "cosine":
            query_vectors = self._normalize_vectors(query_vectors)
        
        # Search
        distances, indices = self.index.search(query_vectors.astype(np.float32), min(k, self.index.ntotal))
        
        # Get metadata for returned indices
        result_metadata = []
        for query_indices in indices:
            query_metadata = [self.metadata[idx] for idx in query_indices if idx < len(self.metadata)]
            result_metadata.append(query_metadata)
        
        return distances, indices, result_metadata
    
    def get_vector_count(self) -> int:
        """Get the number of vectors in the index."""
        return self.index.ntotal
    
    def clear(self) -> None:
        """Clear all vectors and metadata from the index."""
        self.index.reset()
        self.metadata.clear()
        logger.info("Cleared FAISS index")
    
    def save(self, filepath: Union[str, Path]) -> None:
        """
        Save the index and metadata to disk.
        
        Args:
            filepath: Path to save the index
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index
        index_path = filepath.with_suffix('.faiss')
        faiss.write_index(self.index, str(index_path))
        
        # Save metadata
        metadata_path = filepath.with_suffix('.metadata.pkl')
        with open(metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)
        
        # Save index configuration
        config_path = filepath.with_suffix('.config.pkl')
        config = {
            'embedding_dim': self.embedding_dim,
            'index_type': self.index_type,
            'metric': self.metric,
            'vector_count': self.index.ntotal
        }
        with open(config_path, 'wb') as f:
            pickle.dump(config, f)
        
        logger.info(f"Saved FAISS index to {filepath}")
    
    def load(self, filepath: Union[str, Path]) -> None:
        """
        Load the index and metadata from disk.
        
        Args:
            filepath: Path to load the index from
        """
        filepath = Path(filepath)
        
        # Load FAISS index
        index_path = filepath.with_suffix('.faiss')
        if not index_path.exists():
            raise FileNotFoundError(f"Index file not found: {index_path}")
        
        self.index = faiss.read_index(str(index_path))
        
        # Load metadata
        metadata_path = filepath.with_suffix('.metadata.pkl')
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        
        with open(metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)
        
        # Load configuration
        config_path = filepath.with_suffix('.config.pkl')
        if config_path.exists():
            with open(config_path, 'rb') as f:
                config = pickle.load(f)
                self.embedding_dim = config['embedding_dim']
                self.index_type = config['index_type']
                self.metric = config['metric']
        
        logger.info(f"Loaded FAISS index from {filepath} with {self.index.ntotal} vectors")
    
    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize a single vector."""
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm
    
    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """Normalize multiple vectors."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        return vectors / norms
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the index."""
        return {
            "vector_count": self.index.ntotal,
            "embedding_dimension": self.embedding_dim,
            "index_type": self.index_type,
            "metric": self.metric,
            "is_trained": self.is_trained,
            "memory_usage_mb": self.index.ntotal * self.embedding_dim * 4 / (1024 * 1024)  # Approximate
        }
