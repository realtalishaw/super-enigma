#!/bin/bash

# Setup script for semantic search system
set -e

echo "🚀 Setting up semantic search system..."

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📦 Installing dependencies..."
pip install sentence-transformers faiss-cpu torch transformers

echo "📁 Creating data directory..."
mkdir -p data

echo "🔨 Building semantic search index..."
python scripts/build_semantic_index.py

echo "🧪 Running tests..."
python scripts/test_semantic_search.py

echo "✅ Semantic search system setup complete!"
echo ""
echo "You can now:"
echo "  - Search the index: python -m core.semantic_search.cli search data/semantic_index 'your query'"
echo "  - Get stats: python -m core.semantic_search.cli stats data/semantic_index"
echo "  - Use the API: curl 'http://localhost:8001/api/semantic-search/search?query=your%20query'"
echo ""
echo "For more information, see: core/semantic_search/README.md"
