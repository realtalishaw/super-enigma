# Semantic Search System

This module provides semantic search capabilities for the tool catalog using FAISS and sentence-transformers. It enables finding relevant tools and providers based on natural language queries rather than exact keyword matches.

## Features

- **Vector Embeddings**: Converts tool descriptions, names, and metadata into high-dimensional vectors using sentence-transformers
- **Fast Similarity Search**: Uses FAISS for efficient similarity search over large vector collections
- **Semantic Understanding**: Finds relevant tools even when exact keywords don't match
- **Flexible Filtering**: Supports filtering by tool types, categories, and providers
- **API Integration**: RESTful API endpoints for search functionality
- **CLI Tools**: Command-line interface for index management

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Catalog Data  │───▶│ Embedding Service│───▶│  FAISS Index    │
│   (JSON)        │    │ (sentence-       │    │  (Vector DB)    │
│                 │    │  transformers)   │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Search API    │◀───│ Search Service   │◀───│   Query Vector  │
│   (FastAPI)     │    │ (Orchestration)  │    │   Generation    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Components

### 1. EmbeddingService (`embedding_service.py`)
- Generates vector embeddings from text using sentence-transformers
- Supports batch processing for efficiency
- Handles catalog item extraction and text preprocessing
- Uses the `all-MiniLM-L6-v2` model by default (384-dimensional embeddings)

### 2. FAISSIndex (`faiss_index.py`)
- Manages FAISS vector index for fast similarity search
- Supports cosine similarity, L2 distance, and inner product metrics
- Provides index persistence (save/load functionality)
- Handles vector normalization for cosine similarity

### 3. SemanticSearchService (`search_service.py`)
- High-level orchestration service
- Combines embedding generation and FAISS indexing
- Provides search functionality with filtering options
- Manages index lifecycle (build, rebuild, stats)

### 4. CLI Tool (`cli.py`)
- Command-line interface for index management
- Supports building, searching, and getting statistics
- Useful for debugging and manual operations

## Installation

The semantic search system requires additional dependencies:

```bash
pip install sentence-transformers faiss-cpu torch transformers
```

Or install from the updated requirements.txt:

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Build the Index

First, build the semantic search index from your catalog data:

```bash
# Using the build script
python scripts/build_semantic_index.py

# Or using the CLI tool
python -m core.semantic_search.cli build catalog.json data/semantic_index
```

### 2. Search the Index

```bash
# Using the CLI tool
python -m core.semantic_search.cli search data/semantic_index "send email notification"

# Using the API
curl "http://localhost:8001/api/semantic-search/search?query=send%20email&k=5"
```

### 3. Get Statistics

```bash
# Using the CLI tool
python -m core.semantic_search.cli stats data/semantic_index

# Using the API
curl "http://localhost:8001/api/semantic-search/stats"
```

## API Endpoints

### Search
- `GET /api/semantic-search/search` - Search with query parameters
- `POST /api/semantic-search/search` - Search with request body

### Similar Tools
- `POST /api/semantic-search/similar-tools` - Find tools similar to a given tool

### Index Management
- `GET /api/semantic-search/stats` - Get index statistics
- `POST /api/semantic-search/rebuild` - Rebuild the index

## Usage Examples

### Python API

```python
from core.semantic_search.search_service import SemanticSearchService

# Initialize service
search_service = SemanticSearchService(
    embedding_model="all-MiniLM-L6-v2",
    index_path="data/semantic_index"
)

# Search for tools
results = search_service.search("send email notification", k=5)

# Find similar tools
similar = search_service.search_similar_tools(tool_item, k=3)

# Get index stats
stats = search_service.get_index_stats()
```

### Enhanced Suggestions Service

```python
from api.user_services.semantic_suggestions_service import SemanticSuggestionsService

# Initialize service
suggestions_service = SemanticSuggestionsService()

# Get tool suggestions
suggestions = suggestions_service.get_tool_suggestions(
    "When I receive an email, post to Slack",
    max_suggestions=10
)

# Get workflow suggestions
workflows = suggestions_service.get_workflow_suggestions(
    "Automate customer onboarding",
    max_suggestions=5
)
```

## Configuration

### Model Selection

The system uses `all-MiniLM-L6-v2` by default, which provides a good balance of:
- **Speed**: Fast inference and small model size
- **Quality**: Good semantic understanding
- **Dimension**: 384-dimensional embeddings

Alternative models you can use:
- `all-mpnet-base-v2`: Higher quality, slower
- `paraphrase-MiniLM-L6-v2`: Optimized for paraphrasing
- `multi-qa-MiniLM-L6-cos-v1`: Optimized for Q&A tasks

### Index Configuration

The FAISS index is configured with:
- **Type**: Flat index (exact search, good for small-medium datasets)
- **Metric**: Cosine similarity (normalized vectors)
- **Dimension**: Automatically determined from the embedding model

For larger datasets, consider using:
- **IVF**: Inverted file index for faster approximate search
- **HNSW**: Hierarchical navigable small world for very fast search

## Performance Considerations

### Index Size
- **Memory**: ~1.5MB per 1000 vectors (384-dimensional float32)
- **Disk**: ~1.5MB per 1000 vectors (compressed with metadata)

### Search Performance
- **Latency**: ~1-5ms per query (depending on index size)
- **Throughput**: ~100-1000 queries/second (depending on hardware)

### Optimization Tips
1. **Batch Processing**: Use batch embedding generation for large datasets
2. **Index Persistence**: Save/load index to avoid rebuilding
3. **Filtering**: Use filters to reduce search space
4. **Model Selection**: Choose appropriate model for your use case

## Integration with Evaluation System

The semantic search system can be integrated with your evaluation system to:

1. **Improve Tool Selection**: Use semantic similarity to find better tool matches
2. **Enhance Suggestions**: Provide more relevant tool recommendations
3. **Workflow Generation**: Suggest better tool combinations based on semantic similarity
4. **Accuracy Metrics**: Use similarity scores as accuracy indicators

### Example Integration

```python
# In your evaluation system
def evaluate_tool_selection(user_prompt, generated_tools):
    # Get semantic suggestions
    suggestions = suggestions_service.get_tool_suggestions(user_prompt)
    
    # Calculate semantic accuracy
    semantic_accuracy = calculate_semantic_overlap(generated_tools, suggestions)
    
    return {
        "semantic_accuracy": semantic_accuracy,
        "suggestions": suggestions
    }
```

## Troubleshooting

### Common Issues

1. **Index Not Found**: Build the index first using the build script
2. **Memory Issues**: Use a smaller embedding model or reduce batch size
3. **Slow Search**: Consider using an approximate index type for large datasets
4. **Poor Results**: Try a different embedding model or adjust the text preprocessing

### Debugging

Enable debug logging to see detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Performance Monitoring

Monitor index performance:

```python
stats = search_service.get_index_stats()
print(f"Index size: {stats['faiss_stats']['vector_count']} vectors")
print(f"Memory usage: {stats['faiss_stats']['memory_usage_mb']:.2f} MB")
```

## Future Enhancements

1. **Multi-modal Search**: Support for image and other media types
2. **Real-time Updates**: Incremental index updates for dynamic catalogs
3. **Advanced Filtering**: More sophisticated filtering options
4. **Query Expansion**: Automatic query expansion for better results
5. **Personalization**: User-specific search preferences and history
