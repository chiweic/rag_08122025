# Embedding Initialization Guide

## Overview

This project provides multiple scripts for initializing vector embeddings in Qdrant. Use the appropriate script based on your needs.

## 🎯 Recommended Script: `init_collections.py` (NEW!)

### Description
**Unified, provider-agnostic initialization script** that handles all collections with a single interface.

### Key Features
- ✅ **All collections in one**: Initialize main, FAQ, or all collections
- ✅ **Provider-agnostic**: Automatically uses embedding provider from `.env`
- ✅ **Flexible options**: Test with limited data, recreate without prompts
- ✅ **Modern CLI**: Argument parsing with helpful examples
- ✅ **Same embedding server**: Uses single EmbeddingFactory instance

### Usage

```bash
# Initialize main document collection
python init_collections.py main

# Initialize FAQ collection
python init_collections.py faq

# Test FAQ with 100 questions first
python init_collections.py faq --limit 100

# Initialize all collections at once
python init_collections.py all

# Recreate all collections without prompts (useful for scripts)
python init_collections.py all --recreate

# Get help
python init_collections.py --help
```

### What It Does
1. Reads embedding provider from `.env`
2. Creates single embeddings instance (shared across all collections)
3. Loads documents based on collection type:
   - `main`: All chunks from `chunks/*.jsonl`
   - `faq`: Questions from `faq.json`
   - `all`: Both main and FAQ
4. Generates embeddings in batches
5. Uploads to appropriate Qdrant collections
6. Verifies and reports statistics

---

## Alternative Scripts

### `init_embeddings.py` ✅

### Description
Generic, provider-agnostic initialization script that uses `EmbeddingFactory` from `llm_factory.py`.

### Key Features
- ✅ **Provider-agnostic**: Automatically uses embedding provider from `.env`
- ✅ **Supports all providers**: STAPI, DashScope, OpenAI, Google, HuggingFace
- ✅ **Auto-configuration**: Reads all settings from `.env` file
- ✅ **Batch processing**: Efficient batch embedding generation
- ✅ **Progress tracking**: Shows progress bars and time estimates
- ✅ **Error recovery**: Fallback to individual embeddings on batch failure
- ✅ **Modern code**: Uses factory pattern and settings management

### Usage
```bash
source venv/bin/activate
python init_embeddings.py
```

### Configuration
Edit `.env` file to configure embedding provider:

```env
# For STAPI (self-hosted)
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
OLLAMA_BASE_URL=http://ollama.changpt.org/v1

# For DashScope
EMBEDDING_PROVIDER=dashscope
EMBEDDING_MODEL=text-embedding-v4
DASHSCOPE_API_KEY=your-api-key

# For OpenAI
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large
OPENAI_API_KEY=your-api-key

# Qdrant settings
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=ddm_rag
```

### What It Does
1. Loads embedding provider from `.env`
2. Reads all `chunks/*.jsonl` files
3. Generates embeddings in batches (50 docs/batch)
4. Uploads to Qdrant in batches (100 points/batch)
5. Shows progress and time estimates
6. Verifies final collection status

---

## Legacy Scripts (Provider-Specific)

### `dashscope_init.py` (Deprecated)

**Status**: ⚠️ Deprecated - Use `init_embeddings.py` instead

**Description**: DashScope-specific initialization script with hardcoded API calls.

**Why deprecated**:
- Hardcoded to DashScope API
- Direct HTTP requests instead of using factory pattern
- Doesn't support other embedding providers
- Requires code changes to switch providers

**Still works for**: Quick DashScope-only initialization if you don't want to use the factory pattern.

### `ollama_parallel_init.py` (Legacy)

**Status**: ⚠️ Legacy - Use `init_embeddings.py` instead

**Description**: Ollama-specific initialization with parallel processing.

**Why legacy**:
- Hardcoded to Ollama API
- Parallel processing may cause rate limiting
- Not compatible with STAPI
- Doesn't use factory pattern

---

## FAQ-Specific Initialization

### `init_faq_collection.py` ✅

**Status**: Active - Uses `EmbeddingFactory`

**Description**: Initializes FAQ collection for query recommendations.

**Usage**:
```bash
# Full FAQ dataset (20,744 questions)
python init_faq_collection.py

# Test with limited questions
python init_faq_collection.py 100
```

**Features**:
- ✅ Uses `EmbeddingFactory` (provider-agnostic)
- ✅ Reads configuration from `.env`
- ✅ Supports limiting for testing
- ✅ Interactive collection recreation
- ✅ ID collision prevention

---

## Comparison Table

| Feature | `init_collections.py` | `init_embeddings.py` | `init_faq_collection.py` | `dashscope_init.py` |
|---------|----------------------|---------------------|-------------------------|---------------------|
| **Provider-agnostic** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ DashScope only |
| **Uses factory pattern** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No |
| **Unified interface** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **CLI arguments** | ✅ Yes | ❌ No | ⚠️ Limited | ❌ No |
| **Batch processing** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Error recovery** | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Limited |
| **Target data** | Main + FAQ | Main | FAQ | Main |
| **Collections** | Multiple | `ddm_rag` | `ddm_faq` | `ddm_rag` |
| **Status** | 🎯 **Recommended** | ✅ Active | ✅ Active | ⚠️ Deprecated |

---

## Migration Guide

### From `dashscope_init.py` to `init_embeddings.py`

1. **No code changes needed** - Just use the new script:
   ```bash
   # Old way
   python dashscope_init.py

   # New way (same result if .env is configured for DashScope)
   python init_embeddings.py
   ```

2. **Switch to STAPI** by editing `.env`:
   ```env
   EMBEDDING_PROVIDER=ollama  # Change from dashscope
   EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
   OLLAMA_BASE_URL=http://ollama.changpt.org/v1
   ```

3. **Run the new script**:
   ```bash
   python init_embeddings.py
   ```

---

## Recommended Workflow

### First-Time Setup (Unified Approach) 🎯

1. **Configure `.env`** with your preferred embedding provider:
   ```env
   EMBEDDING_PROVIDER=ollama  # or dashscope, openai, etc.
   EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
   OLLAMA_BASE_URL=http://ollama.changpt.org/v1
   ```

2. **Start Qdrant**:
   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```

3. **Initialize all collections at once**:
   ```bash
   python init_collections.py all
   ```

4. **Start API server**:
   ```bash
   python main.py
   ```

That's it! One command initializes everything.

### Alternative Approach (Step-by-Step)

If you prefer to initialize collections separately:

```bash
# Test FAQ first with limited data
python init_collections.py faq --limit 100

# If test looks good, do full FAQ
python init_collections.py faq

# Then initialize main collection
python init_collections.py main
```

### Switching Embedding Providers

1. **Edit `.env`** to change `EMBEDDING_PROVIDER` and related settings
2. **Regenerate all embeddings**:
   ```bash
   python init_collections.py all --recreate
   ```
3. **Restart API server**:
   ```bash
   python main.py
   ```

The `--recreate` flag skips confirmation prompts, making it script-friendly!

---

## Performance Comparison

| Provider | Model | Dimension | Speed (docs/sec) | Cost |
|----------|-------|-----------|------------------|------|
| **STAPI** | bge-large-zh-v1.5 | 1024 | ~1-2 | Free (self-hosted) |
| **DashScope** | text-embedding-v4 | 1024 | ~0.5-1 | ¥0.0007/1K tokens |
| **OpenAI** | text-embedding-3-large | 3072 | ~2-3 | $0.13/1M tokens |
| **HuggingFace** | bge-m3 | 1024 | ~0.1-0.5 | Free (local CPU) |

*Speeds are approximate and depend on hardware/network conditions*

---

## Troubleshooting

### Error: "Embedding provider not found"
- Check `.env` file has correct `EMBEDDING_PROVIDER` setting
- Verify API keys are set if using cloud providers

### Error: "Collection already exists"
- Delete the collection manually or let the script recreate it
- Use Qdrant dashboard: http://localhost:6333/dashboard

### Error: "Connection refused"
- Ensure Qdrant is running: `docker ps | grep qdrant`
- Check `QDRANT_URL` in `.env` matches your Qdrant instance

### Slow performance with HuggingFace
- HuggingFace models run on CPU by default
- Consider using STAPI or cloud providers for production

---

## Best Practices

1. **Always use `init_embeddings.py`** for new projects
2. **Keep `.env` as single source of truth** for configuration
3. **Test with small datasets first** before full initialization
4. **Back up Qdrant data** before regenerating embeddings
5. **Document provider changes** in commit messages

---

## Future Improvements

Planned enhancements:
- [ ] Resume from checkpoint on failure
- [ ] Parallel collection initialization
- [ ] Incremental updates (add new chunks without full rebuild)
- [ ] Multi-provider comparison mode
- [ ] Automatic provider selection based on data characteristics
