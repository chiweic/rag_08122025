# DDM RAG System - Quick Reference Guide

## Active Entry Points

### 1. Start the Server
```bash
python main.py
```
- Starts FastAPI server on `localhost:8000`
- Auto-connects to Qdrant at startup
- Auto-initializes if needed

### 2. Initialize Vector Database (First Time Only)
```bash
python init_collections.py all
```
- Loads all chunks from `chunks/*.jsonl`
- Generates embeddings via STAPI
- Uploads to Qdrant collections

**Options**:
- `init_collections.py main` - Only text/audio/events
- `init_collections.py faq` - Only FAQ for query recommendations

---

## Core Active Files

| File | Purpose | Do Not Delete |
|------|---------|---|
| `main.py` | Server entry point | YES |
| `api.py` | API application | YES |
| `config.py` | Settings & environment | YES |
| `vector_store.py` | Qdrant integration | YES |
| `rag_pipeline.py` | RAG orchestration | YES |
| `llm_factory.py` | LLM/embedding factory | YES |
| `data_loader.py` | Load chunks | YES |
| `stapi_embeddings.py` | STAPI API wrapper | YES |
| `auth.py` | User authentication | Optional |
| `book_recommender.py` | Book suggestions | YES |
| `query_recommender.py` | Query suggestions | YES |
| `event_recommender.py` | Event matching | YES |
| `audio_recommender.py` | Audio suggestions | YES |
| `init_collections.py` | Initialize collections | YES |

---

## Files to Delete (Safe)

```
# Deprecated _v2 versions (replaced by unified versions)
api_v2.py
main_v2.py
rag_pipeline_v2.py
vector_store_v2.py
data_loader_v2.py
test_multi_collection.py

# Legacy frontend (superseded by frontend_v2)
frontend/  (entire directory)

# Test/debug files
init_result.json
init_retry.json
ollama_*.json
dashscope_init.json
*_test_report.json
events_20250730_124843.jsonl

# Log files
*.log

# One-time utilities
ollama_parallel_init.py
convert_events.py
reorganize_chunks.py
fix_text_chunks.py
start_localized.py
```

---

## Active Frontend

**Location**: `frontend_v2/`

Files:
- `index.html` - Chat interface
- `login.html` - Login page

**Access**: Navigate to `http://localhost:8000/` in browser

---

## Configuration

### Environment Variables (.env)
```bash
# LLM
LLM_PROVIDER=custom
CUSTOM_LLM_BASE_URL=http://vllm.roverai.com/v1
LLM_MODEL=<model-name>

# Embeddings (via STAPI/Ollama)
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama.changpt.org/v1
OLLAMA_API_KEY=<key-if-needed>

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=ddm_rag

# Optional API keys
OPENAI_API_KEY=<key>
GOOGLE_API_KEY=<key>
DEEPSEEK_API_KEY=<key>
```

---

## API Endpoints (Main)

### Query & Retrieval
```bash
# Full RAG (retrieve + synthesize)
POST /query
{
  "question": "What is meditation?",
  "top_k": 5,
  "include_sources": true
}

# Retrieve only
POST /retrieve
{
  "query": "meditation techniques",
  "top_k": 10
}
```

### Recommendations
```bash
# Book recommendations
POST /books/recommend
{
  "query": "Buddhism basics",
  "top_k": 5
}

# Event recommendations
POST /events/recommend
{
  "query": "meditation practice",
  "top_k": 3
}

# Related queries
POST /queries/related
{
  "query": "What is enlightenment?",
  "top_k": 5
}
```

### System
```bash
# Health check
GET /health

# Statistics
GET /statistics

# Update configuration
POST /update_config
{
  "llm_provider": "openai",
  "embedding_provider": "openai"
}
```

---

## Data Files (Keep All)

### Chunks (Used by init_collections.py)
- `chunks/text_chunks.jsonl` (1,067 records)
- `chunks/audio_chunks.jsonl` (2,287 records)
- `chunks/event_chunks.jsonl` (210 records)

### Metadata
- `ddm_books.json` - Book catalog
- `events.json` - Events database
- `faq.json` - FAQ collection
- `processed_audios.json` - Audio metadata
- `processed_videos.json` - Video metadata

---

## Common Tasks

### Check System Status
```bash
curl http://localhost:8000/health
curl http://localhost:8000/statistics
```

### Run Tests
```bash
# Auth tests
python test_auth.py

# API tests
python test_api_server.py

# Embedding tests
python test_stapi_embeddings.py
```

### Reinitialize Database
```bash
# Start fresh Qdrant
docker-compose down
docker-compose up -d

# Reinitialize collections
python init_collections.py all
```

---

## Troubleshooting

### Server won't start
1. Check `.env` file exists and has required variables
2. Verify Qdrant is running: `docker ps`
3. Check Qdrant is accessible: `curl http://localhost:6333/health`

### Embeddings not working
1. Check STAPI server is running (ollama.changpt.org)
2. Verify `EMBEDDING_PROVIDER=ollama` in .env
3. Test: `python test_stapi_embeddings.py`

### LLM not responding
1. Verify custom LLM endpoint is accessible: `curl http://vllm.roverai.com/v1/models`
2. Check `CUSTOM_LLM_BASE_URL` in .env
3. Try switching to OpenAI with API key

---

## Directory Structure

```
rag_08122025/
├── main.py              # Entry point
├── api.py               # FastAPI app
├── config.py            # Settings
├── rag_pipeline.py      # RAG logic
├── vector_store.py      # Qdrant
├── llm_factory.py       # LLM/embedding factory
├── data_loader.py       # Load chunks
├── stapi_embeddings.py  # STAPI wrapper
├── *_recommender.py     # Recommendation engines
├── auth.py              # Authentication
├── init_collections.py  # Initialize DB
├── chunks/              # JSONL data files
│   ├── text_chunks.jsonl
│   ├── audio_chunks.jsonl
│   └── event_chunks.jsonl
├── frontend_v2/         # Active frontend
│   ├── index.html
│   └── login.html
├── ddm_books.json       # Book catalog
├── events.json          # Events
├── faq.json             # FAQ
├── docker-compose.yml   # Qdrant setup
└── requirements.txt     # Dependencies
```

---

## Key Configuration

### LLM Providers
- **Custom** (vllm.roverai.com) - Primary
- OpenAI - Optional
- DeepSeek - Optional
- Google Gemini - Optional
- DashScope - Optional

### Embedding Providers
- **STAPI/Ollama** (ollama.changpt.org) - Primary
- Local HuggingFace - Secondary
- OpenAI - Optional
- Google - Optional
- DashScope - Optional

---

## Documentation

For detailed information, see:
- `SETUP.md` - Detailed setup instructions
- `EMBEDDING_INIT_GUIDE.md` - Embedding initialization
- `CLAUDE.md` - Comprehensive system documentation
- `FILE_INVENTORY.md` - Complete file listing and categorization
