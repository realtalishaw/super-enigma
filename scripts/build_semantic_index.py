#!/usr/bin/env python3
"""
Script to build the semantic search index from the catalog data.
"""

import sys
import os
import json
import asyncio
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

async def main():
    """Build the semantic search index from database."""
    
    # Paths
    index_path = project_root / "data" / "semantic_index"
    
    # Create data directory if it doesn't exist
    index_path.parent.mkdir(exist_ok=True)
    
    logger.info("Building semantic search index from database...")
    logger.info(f"Index path: {index_path}")
    
    try:
        # Initialize search service
        logger.info("Initializing semantic search service...")
        search_service = SemanticSearchService(
            embedding_model="all-MiniLM-L6-v2",
            index_path=index_path
        )
        
        # Build index from database
        logger.info("Building FAISS index from database...")
        await search_service.build_index_from_database()
        
        # Get and display stats
        stats = search_service.get_index_stats()
        logger.info("Index built successfully!")
        logger.info(f"  - Vector count: {stats['faiss_stats']['vector_count']}")
        logger.info(f"  - Embedding dimension: {stats['faiss_stats']['embedding_dimension']}")
        logger.info(f"  - Model: {stats['embedding_model']['model_name']}")
        logger.info(f"  - Memory usage: {stats['faiss_stats']['memory_usage_mb']:.2f} MB")
        logger.info(f"  - Index saved to: {index_path}")
        
        # Test search
        logger.info("\nTesting search functionality...")
        test_queries = [
            "send email",
            "create calendar event", 
            "post to slack",
            "database query",
            "file upload"
        ]
        
        for query in test_queries:
            results = search_service.search(query, k=3)
            logger.info(f"Query: '{query}' -> {len(results)} results")
            if results:
                top_result = results[0]
                logger.info(f"  Top result: {top_result['item'].get('name', 'Unknown')} (score: {top_result['similarity_score']:.4f})")
        
        logger.info("\nSemantic search index is ready!")
        
    except Exception as e:
        logger.error(f"Error building index: {e}")
        sys.exit(1)

def main_sync():
    """Synchronous wrapper for the async main function."""
    asyncio.run(main())

if __name__ == "__main__":
    main_sync()
