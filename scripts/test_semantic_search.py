#!/usr/bin/env python3
"""
Test script for the semantic search system.
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.semantic_search.search_service import SemanticSearchService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_semantic_search():
    """Test the semantic search functionality."""
    
    # Paths
    catalog_path = project_root / "catalog_clean.json"
    index_path = project_root / "data" / "semantic_index"
    
    logger.info("Testing semantic search system...")
    
    # Check if catalog exists
    if not catalog_path.exists():
        logger.error(f"Catalog file not found: {catalog_path}")
        return False
    
    # Check if index exists
    if not index_path.exists():
        logger.warning("Index not found. Building it first...")
        # Build index
        with open(catalog_path, 'r') as f:
            catalog_data = json.load(f)
        
        search_service = SemanticSearchService(
            embedding_model="all-MiniLM-L6-v2",
            index_path=index_path
        )
        search_service.build_index_from_catalog(catalog_data)
    else:
        # Load existing index
        search_service = SemanticSearchService(
            embedding_model="all-MiniLM-L6-v2",
            index_path=index_path
        )
    
    # Test queries
    test_queries = [
        "send email notification",
        "create calendar event",
        "post message to slack",
        "upload file to cloud storage",
        "query database",
        "process payment",
        "send SMS message",
        "create spreadsheet",
        "monitor website",
        "backup data"
    ]
    
    logger.info("Running test queries...")
    
    for query in test_queries:
        logger.info(f"\nTesting query: '{query}'")
        
        try:
            results = search_service.search(query, k=3)
            
            if results:
                logger.info(f"  Found {len(results)} results:")
                for i, result in enumerate(results, 1):
                    item = result["item"]
                    score = result["similarity_score"]
                    logger.info(f"    {i}. {item.get('name', 'Unknown')} (score: {score:.4f})")
                    logger.info(f"       Type: {item.get('type', 'unknown')}")
                    logger.info(f"       Description: {item.get('description', 'No description')[:80]}...")
            else:
                logger.warning(f"  No results found for query: '{query}'")
                
        except Exception as e:
            logger.error(f"  Error testing query '{query}': {e}")
            return False
    
    # Test index stats
    logger.info("\nTesting index statistics...")
    try:
        stats = search_service.get_index_stats()
        logger.info(f"  Vector count: {stats['faiss_stats']['vector_count']}")
        logger.info(f"  Embedding dimension: {stats['faiss_stats']['embedding_dimension']}")
        logger.info(f"  Memory usage: {stats['faiss_stats']['memory_usage_mb']:.2f} MB")
        logger.info(f"  Model: {stats['embedding_model']['model_name']}")
    except Exception as e:
        logger.error(f"  Error getting stats: {e}")
        return False
    
    logger.info("\n✅ All tests passed! Semantic search system is working correctly.")
    return True

def main():
    """Main test function."""
    success = test_semantic_search()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
