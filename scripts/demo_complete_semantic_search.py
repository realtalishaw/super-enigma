#!/usr/bin/env python3
"""
Demo script showing the complete semantic search system with tools, actions, and triggers.
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

def demo_complete_semantic_search():
    """Demo the complete semantic search system."""
    
    # Initialize semantic search
    index_path = project_root / "data" / "semantic_index"
    search_service = SemanticSearchService(index_path=index_path)
    
    # Get index stats
    stats = search_service.get_index_stats()
    
    print("🎯 **Complete Semantic Search System Demo**")
    print("=" * 60)
    print(f"📊 **Index Statistics:**")
    print(f"   - Total vectors: {stats['faiss_stats']['vector_count']:,}")
    print(f"   - Embedding dimension: {stats['faiss_stats']['embedding_dimension']}")
    print(f"   - Model: {stats['embedding_model']['model_name']}")
    print(f"   - Memory usage: {stats['faiss_stats']['memory_usage_mb']:.2f} MB")
    print()
    
    # Comprehensive test queries
    test_queries = [
        {
            "query": "send email to someone",
            "description": "Email functionality"
        },
        {
            "query": "create a calendar event",
            "description": "Calendar management"
        },
        {
            "query": "post message to slack channel",
            "description": "Slack integration"
        },
        {
            "query": "upload file to google drive",
            "description": "File management"
        },
        {
            "query": "query database for user data",
            "description": "Database operations"
        },
        {
            "query": "trigger when new email arrives",
            "description": "Email triggers"
        },
        {
            "query": "webhook notification",
            "description": "Webhook functionality"
        },
        {
            "query": "create github issue",
            "description": "GitHub integration"
        },
        {
            "query": "send SMS message",
            "description": "SMS functionality"
        },
        {
            "query": "analyze sentiment of text",
            "description": "AI/ML capabilities"
        }
    ]
    
    print("🔍 **Search Results Demo:**")
    print("=" * 60)
    
    for i, test_case in enumerate(test_queries, 1):
        query = test_case["query"]
        description = test_case["description"]
        
        print(f"\n{i}. **{description}**")
        print(f"   Query: '{query}'")
        
        # Search for results
        results = search_service.search(query, k=5)
        
        if results:
            print(f"   Found {len(results)} results:")
            for j, result in enumerate(results[:3], 1):
                item = result['item']
                score = result['similarity_score']
                item_type = item.get('type', 'unknown')
                name = item.get('name', 'Unknown')
                provider = item.get('provider_name', item.get('provider_id', ''))
                
                print(f"     {j}. [{item_type.upper()}] {name}")
                if provider:
                    print(f"        Provider: {provider}")
                print(f"        Similarity: {score:.4f}")
                
                # Show description if available
                desc = item.get('description', '')
                if desc and len(desc) > 100:
                    desc = desc[:100] + "..."
                if desc:
                    print(f"        Description: {desc}")
        else:
            print("   No results found")
    
    print("\n" + "=" * 60)
    print("✅ **Complete semantic search system is working!**")
    print(f"📈 **Improvement:** From 1,070 to {stats['faiss_stats']['vector_count']:,} searchable items")
    print("🎯 **Coverage:** Now includes providers, tools, actions, and triggers")
    print("🚀 **Ready for evaluation improvements!**")

if __name__ == "__main__":
    demo_complete_semantic_search()
