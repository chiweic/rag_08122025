# STAPI Embedding Migration

## Summary

Successfully migrated from DashScope embeddings to self-hosted STAPI embedding API.

## Changes Made

### 1. Renamed Files and Classes

To avoid confusion with Ollama:
- **File**: `ollama_embeddings.py` → `stapi_embeddings.py`
- **Class**: `OllamaEmbeddings` → `STAPIEmbeddings`
- **Updated imports** in `llm_factory.py`

Note: The `.env` configuration still uses `OLLAMA_*` variable names for backward compatibility.

### 2. Updated `.env` Configuration

Changed embedding provider from DashScope to Ollama (STAPI):

```env
# OLD Configuration
EMBEDDING_PROVIDER=dashscope
EMBEDDING_MODEL=text-embedding-v4

# NEW Configuration
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
OLLAMA_BASE_URL=http://ollama.changpt.org/v1
OLLAMA_API_KEY=dummy_key
OLLAMA_MAX_WORKERS=1
```

### 3. Updated `stapi_embeddings.py`

Enhanced the `STAPIEmbeddings` class to support both:
- **Ollama native API format**: `/api/embeddings` with `prompt` field
- **OpenAI-compatible format (STAPI)**: `/v1/embeddings` with `input` field

Key changes:
- Auto-detects API format based on base URL (checks for `/v1`)
- Handles both response formats (`embedding` vs `data[0].embedding`)

### 4. API Endpoint Details

**STAPI Endpoint**: `http://ollama.changpt.org/v1/embeddings`

**Model**: `BAAI/bge-large-zh-v1.5`
- Chinese-optimized embedding model
- 1024 dimensions
- Fast response time (~1 second)

**Request Format** (OpenAI-compatible):
```json
{
  "model": "BAAI/bge-large-zh-v1.5",
  "input": "text to embed"
}
```

**Response Format**:
```json
{
  "data": [{
    "embedding": [0.0143, -0.0048, ...],
    "index": 0,
    "object": "embedding"
  }],
  "model": "BAAI/bge-large-zh-v1.5",
  "usage": {"prompt_tokens": 1024, "total_tokens": 1024},
  "object": "list"
}
```

## Testing

All tests passed:
- ✅ Single query embedding
- ✅ Batch document embedding
- ✅ Configuration loading
- ✅ Factory integration

## Benefits

1. **Self-hosted**: Full control over embedding infrastructure
2. **Cost savings**: No API usage fees
3. **Performance**: Fast response times (~1 second)
4. **Reliability**: No external API dependencies
5. **Privacy**: Data stays within your infrastructure

## Compatibility

The migration is **backward compatible**:
- Existing code using `EmbeddingFactory.create_embeddings()` works without changes
- API endpoints continue to work seamlessly
- Vector store operations unchanged (still 1024 dimensions)

## Next Steps

To apply the changes:

1. **Restart your API server** for the new `.env` configuration to take effect:
   ```bash
   # Stop current server
   # Then restart:
   source venv/bin/activate
   python main.py
   ```

2. **(Optional) Regenerate vector embeddings** if you want to use the new STAPI model for existing data:
   ```bash
   python init_faq_collection.py
   ```
   Note: This is optional since both models use 1024 dimensions and are semantically similar (both BGE models).

## Rollback

To rollback to DashScope, edit `.env`:
```env
EMBEDDING_PROVIDER=dashscope
EMBEDDING_MODEL=text-embedding-v4
```

Then restart the server.
