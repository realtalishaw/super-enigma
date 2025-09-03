#!/usr/bin/env python3
"""
Demo script showing how to use semantic search for evaluation improvements.
"""

import sys
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

def demo_eval_improvement():
    """Demo how semantic search improves evaluation accuracy."""
    
    # Initialize semantic search
    index_path = project_root / "data" / "semantic_index"
    search_service = SemanticSearchService(index_path=index_path)
    
    # Sample evaluation queries (from your eval reports)
    eval_queries = [
        "I need to send an email to my team",
        "Create a new calendar appointment",
        "Upload a file to cloud storage", 
        "Post a message in Slack channel",
        "Query customer database",
        "Process a payment transaction",
        "Send SMS notification",
        "Generate a PDF report",
        "Monitor website uptime",
        "Backup important data"
    ]
    
    print("🚀 Semantic Search for Evaluation Improvement Demo")
    print("=" * 60)
    
    for i, query in enumerate(eval_queries, 1):
        print(f"\n{i}. Query: '{query}'")
        print("-" * 40)
        
        # Get semantic search results
        results = search_service.search(query, k=3)
        
        if results:
            print("📍 Top semantic matches:")
            for j, result in enumerate(results, 1):
                item = result['item']
                score = result['similarity_score']
                print(f"   {j}. {item.get('name', 'Unknown')} (score: {score:.4f})")
                print(f"      Type: {item.get('type', 'unknown')}")
                print(f"      Category: {item.get('category', 'N/A')}")
                if item.get('description'):
                    desc = item['description'][:100] + "..." if len(item['description']) > 100 else item['description']
                    print(f"      Description: {desc}")
        else:
            print("   No matches found")
    
    # Show index statistics
    stats = search_service.get_index_stats()
    print(f"\n📊 Index Statistics:")
    print(f"   • Vector count: {stats['faiss_stats']['vector_count']:,}")
    print(f"   • Embedding dimension: {stats['faiss_stats']['embedding_dimension']}")
    print(f"   • Memory usage: {stats['faiss_stats']['memory_usage_mb']:.2f} MB")
    print(f"   • Model: {stats['embedding_model']['model_name']}")
    
    print(f"\n✨ Benefits for Evaluation:")
    print(f"   • Semantic understanding vs keyword matching")
    print(f"   • Fast retrieval ({stats['faiss_stats']['vector_count']:,} items in milliseconds)")
    print(f"   • Contextual relevance scoring")
    print(f"   • Handles synonyms and related concepts")
    print(f"   • Improves tool recommendation accuracy")

if __name__ == "__main__":
    demo_eval_improvement()
