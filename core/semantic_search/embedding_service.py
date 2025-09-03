"""
Embedding service using sentence-transformers for generating vector embeddings.
"""

import logging
from typing import List, Dict, Any, Optional, Union
import numpy as np
from sentence_transformers import SentenceTransformer
import torch

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service for generating embeddings from text using sentence-transformers.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: Optional[str] = None):
        """
        Initialize the embedding service.
        
        Args:
            model_name: Name of the sentence-transformer model to use
            device: Device to run the model on ('cpu', 'cuda', or None for auto)
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        logger.info(f"Loading sentence-transformer model: {model_name} on {self.device}")
        self.model = SentenceTransformer(model_name, device=self.device)
        
        # Get embedding dimension
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded with embedding dimension: {self.embedding_dim}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text string.
        
        Args:
            text: Input text to embed
            
        Returns:
            numpy array of embeddings
        """
        if not text or not text.strip():
            return np.zeros(self.embedding_dim)
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding for text: {e}")
            return np.zeros(self.embedding_dim)
    
    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for multiple text strings.
        
        Args:
            texts: List of input texts to embed
            batch_size: Batch size for processing
            
        Returns:
            numpy array of embeddings with shape (len(texts), embedding_dim)
        """
        if not texts:
            return np.array([])
        
        # Filter out empty texts
        valid_texts = [text.strip() if text else "" for text in texts]
        
        try:
            embeddings = self.model.encode(
                valid_texts, 
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(texts) > 100
            )
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings for texts: {e}")
            return np.zeros((len(texts), self.embedding_dim))
    
    def embed_catalog_item(self, item: Dict[str, Any]) -> np.ndarray:
        """
        Generate embedding for a catalog item (provider, tool, etc.).
        
        Args:
            item: Dictionary containing catalog item data
            
        Returns:
            numpy array of embeddings
        """
        # Extract semantic text from catalog item
        semantic_text = self._extract_semantic_text(item)
        return self.embed_text(semantic_text)
    
    def embed_catalog_items(self, items: List[Dict[str, Any]], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for multiple catalog items.
        
        Args:
            items: List of catalog item dictionaries
            batch_size: Batch size for processing
            
        Returns:
            numpy array of embeddings
        """
        if not items:
            return np.array([])
        
        # Extract semantic text from all items
        semantic_texts = [self._extract_semantic_text(item) for item in items]
        return self.embed_texts(semantic_texts, batch_size)
    
    def _extract_semantic_text(self, item: Dict[str, Any]) -> str:
        """
        Extract semantic text from a catalog item for embedding.
        
        Args:
            item: Catalog item dictionary
            
        Returns:
            Concatenated semantic text
        """
        text_parts = []
        
        # Extract basic information
        if "name" in item:
            text_parts.append(item["name"])
        
        if "description" in item and item["description"]:
            text_parts.append(item["description"])
        
        # Extract provider-specific information
        if "metadata" in item and isinstance(item["metadata"], dict):
            metadata = item["metadata"]
            if "name" in metadata:
                text_parts.append(metadata["name"])
            if "description" in metadata and metadata["description"]:
                text_parts.append(metadata["description"])
            if "category" in metadata and metadata["category"]:
                text_parts.append(f"category: {metadata['category']}")
            if "tags" in metadata and isinstance(metadata["tags"], list):
                text_parts.extend([f"tag: {tag}" for tag in metadata["tags"]])
        
        # Extract tool-specific information
        if "tool_type" in item:
            text_parts.append(f"type: {item['tool_type']}")
        
        if "parameters" in item and isinstance(item["parameters"], list):
            for param in item["parameters"]:
                if isinstance(param, dict):
                    if "name" in param:
                        text_parts.append(f"parameter: {param['name']}")
                    if "description" in param and param["description"]:
                        text_parts.append(param["description"])
        
        # Extract examples
        if "examples" in item and isinstance(item["examples"], list):
            for example in item["examples"]:
                if isinstance(example, dict):
                    if "description" in example and example["description"]:
                        text_parts.append(example["description"])
        
        # Join all text parts with spaces
        return " ".join(text_parts)
    
    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension of the model."""
        return self.embedding_dim
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "embedding_dimension": self.embedding_dim,
            "max_seq_length": self.model.max_seq_length
        }
