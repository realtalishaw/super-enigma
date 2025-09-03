"""
CLI tool for managing the semantic search index.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Any

from .search_service import SemanticSearchService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_catalog_data(catalog_path: str) -> Dict[str, Any]:
    """Load catalog data from JSON file."""
    with open(catalog_path, 'r') as f:
        return json.load(f)

def build_index(catalog_path: str, index_path: str, model_name: str = "all-MiniLM-L6-v2"):
    """Build the semantic search index from catalog data."""
    logger.info(f"Building semantic search index from {catalog_path}")
    
    # Load catalog data
    catalog_data = load_catalog_data(catalog_path)
    
    # Initialize search service
    search_service = SemanticSearchService(
        embedding_model=model_name,
        index_path=index_path
    )
    
    # Build index
    search_service.build_index_from_catalog(catalog_data)
    
    # Print stats
    stats = search_service.get_index_stats()
    logger.info(f"Index built successfully:")
    logger.info(f"  - Vector count: {stats['faiss_stats']['vector_count']}")
    logger.info(f"  - Embedding dimension: {stats['faiss_stats']['embedding_dimension']}")
    logger.info(f"  - Model: {stats['embedding_model']['model_name']}")
    logger.info(f"  - Index saved to: {index_path}")

def search_index(index_path: str, query: str, k: int = 10, model_name: str = "all-MiniLM-L6-v2"):
    """Search the semantic index."""
    logger.info(f"Searching index with query: '{query}'")
    
    # Initialize search service
    search_service = SemanticSearchService(
        embedding_model=model_name,
        index_path=index_path
    )
    
    # Perform search
    results = search_service.search(query, k=k)
    
    # Print results
    print(f"\nSearch results for '{query}':")
    print("=" * 50)
    
    for i, result in enumerate(results, 1):
        item = result["item"]
        score = result["similarity_score"]
        
        print(f"\n{i}. {item.get('name', 'Unknown')} (Score: {score:.4f})")
        print(f"   Type: {item.get('type', 'unknown')}")
        print(f"   Description: {item.get('description', 'No description')[:100]}...")
        
        if item.get("provider_name"):
            print(f"   Provider: {item['provider_name']}")
        
        if item.get("tool_type"):
            print(f"   Tool Type: {item['tool_type']}")

def get_stats(index_path: str, model_name: str = "all-MiniLM-L6-v2"):
    """Get index statistics."""
    # Initialize search service
    search_service = SemanticSearchService(
        embedding_model=model_name,
        index_path=index_path
    )
    
    # Get stats
    stats = search_service.get_index_stats()
    
    print("Semantic Search Index Statistics:")
    print("=" * 40)
    print(f"Vector count: {stats['faiss_stats']['vector_count']}")
    print(f"Embedding dimension: {stats['faiss_stats']['embedding_dimension']}")
    print(f"Index type: {stats['faiss_stats']['index_type']}")
    print(f"Metric: {stats['faiss_stats']['metric']}")
    print(f"Memory usage: {stats['faiss_stats']['memory_usage_mb']:.2f} MB")
    print(f"Model: {stats['embedding_model']['model_name']}")
    print(f"Device: {stats['embedding_model']['device']}")
    print(f"Index path: {stats['index_path']}")

def main():
    parser = argparse.ArgumentParser(description="Semantic Search Index Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Build the semantic search index")
    build_parser.add_argument("catalog_path", help="Path to catalog JSON file")
    build_parser.add_argument("index_path", help="Path to save the index")
    build_parser.add_argument("--model", default="all-MiniLM-L6-v2", help="Embedding model name")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search the semantic index")
    search_parser.add_argument("index_path", help="Path to the index")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--k", type=int, default=10, help="Number of results to return")
    search_parser.add_argument("--model", default="all-MiniLM-L6-v2", help="Embedding model name")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Get index statistics")
    stats_parser.add_argument("index_path", help="Path to the index")
    stats_parser.add_argument("--model", default="all-MiniLM-L6-v2", help="Embedding model name")
    
    args = parser.parse_args()
    
    if args.command == "build":
        build_index(args.catalog_path, args.index_path, args.model)
    elif args.command == "search":
        search_index(args.index_path, args.query, args.k, args.model)
    elif args.command == "stats":
        get_stats(args.index_path, args.model)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
