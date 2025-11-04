# DDM RAG System - Complete File Inventory

## Summary
- **Repository Size**: 7.7G (mostly Qdrant vector DB data and large JSON files)
- **Python Files**: 45 total files, 10,549 lines of code
- **Active Frontend**: `frontend_v2/` (latest version with login support)
- **Main Entry Point**: `main.py`
- **Initialized with**: `init_collections.py` (unified script)

---

## CORE FILES (Actively Used)

### Entry Points
| File | Lines | Purpose | Used By |
|------|-------|---------|---------|
| `main.py` | 22 | Server startup (imports api.py) | Direct execution |
| `api.py` | 1,290 | Main FastAPI application with all endpoints | main.py |

### Core Modules (Imported by api.py)
| File | Lines | Purpose | Dependencies |
|------|-------|---------|--------------|
| `config.py` | 72 | Environment and Pydantic settings | All modules |
| `data_loader.py` | 107 | Load JSONL chunks from chunks/ directory | init_collections.py |
| `vector_store.py` | 147 | Qdrant vector database integration | api.py, rag_pipeline.py |
| `rag_pipeline.py` | 164 | RAG orchestration (retrieval + synthesis) | api.py |
| `llm_factory.py` | 250+ | Factory pattern for LLM & embedding creation | api.py, rag_pipeline.py, init_collections.py |
| `stapi_embeddings.py` | 165 | STAPI/Ollama OpenAI-compatible API wrapper | llm_factory.py |

### Initialization
| File | Lines | Purpose | Entry Point |
|------|-------|---------|------------|
| `init_collections.py` | 300+ | Unified script for initializing all Qdrant collections | python init_collections.py [main\|faq\|all] |

### Recommendation Engines (Imported by api.py)
| File | Lines | Purpose | Dependencies |
|------|-------|---------|--------------|
| `book_recommender.py` | 164 | Book recommendations via TF-IDF similarity | sklearn, jieba |
| `query_recommender.py` | 400+ | Query suggestions via semantic similarity | sentence-transformers |
| `event_recommender.py` | 400+ | Event matching (解行並重 theory+practice) | - |
| `audio_recommender.py` | 200+ | Audio teaching recommendations | - |

### Authentication (Optional)
| File | Lines | Purpose | Used By |
|------|-------|---------|---------|
| `auth.py` | 400+ | JWT-based user auth + email verification | api.py (imported but can be disabled) |

---

## DEPRECATED FILES (_v2 versions - NOT USED)

These files were superseded by unified newer versions. **Safe to delete.**

| File | Lines | Reason for Deprecation | Replaced By |
|------|-------|------------------------|-------------|
| `api_v2.py` | 600+ | Multi-collection architecture replaced by single unified api.py | api.py |
| `main_v2.py` | 50+ | Separate entry point for v2 API, now unified | main.py |
| `rag_pipeline_v2.py` | 300+ | Legacy multi-collection pipeline | rag_pipeline.py |
| `vector_store_v2.py` | 400+ | Multi-collection vector store (replaced by single vector_store.py) | vector_store.py |
| `data_loader_v2.py` | 300+ | Multi-type data loader for separate collections | data_loader.py |

**Note**: Only `test_multi_collection.py` imports these _v2 files, and it's also deprecated.

---

## CONFIGURATION FILES

| File | Purpose | Critical |
|------|---------|----------|
| `.env` | Environment variables (API keys, URLs, settings) | YES - Required |
| `env.example` | Template for .env file | NO - Reference only |
| `config.py` | Pydantic settings class (reads from .env) | YES - Core |
| `embedding_config.json` | Legacy embedding config (now superseded by config.py) | NO - Unused |
| `embedding_config.py` | Legacy embedding configuration module | NO - Unused |

---

## DOCUMENTATION FILES

| File | Purpose | Recent |
|------|---------|--------|
| `README.md` | Overview and setup guide | Oct 24 |
| `CLAUDE.md` | AI assistant context (comprehensive) | Nov 3 |
| `SETUP.md` | Detailed setup instructions | Nov 3 |
| `EMBEDDING_INIT_GUIDE.md` | Guide for embedding initialization | Nov 3 |
| `STAPI_INTEGRATION_STATUS.md` | STAPI integration documentation | Nov 3 |
| `STAPI_MIGRATION.md` | Migration notes for STAPI | Nov 3 |
| `SCRIPT_CLEANUP.md` | Record of deprecated scripts removed | Nov 3 |
| `HASH_COLLISION_FIX.md` | Technical fix documentation | Nov 3 |
| `AUTH_IMPLEMENTATION_PLAN.md` | Auth system design (38KB) | Oct 24 |
| `AUTH_SETUP.md` | Auth setup guide | Nov 1 |
| `AUTH_CHECKLIST.md` | Auth implementation checklist | Nov 1 |
| `TESTING.md` | Testing guide | Oct 26 |
| `TEST_AUTH_GUIDE.md` | Auth testing documentation | Nov 1 |
| `DOCKER.md` | Docker configuration guide | Oct 24 |
| `FRONTEND_ACCESS.md` | Frontend access guide | Oct 24 |
| `SERVER_SETUP.md` | Server setup instructions | Oct 24 |
| `STARTUP.md` | Startup checklist | Oct 24 |
| `AGENTS.md` | Agent framework notes | Nov 1 |
| `presentation_outline.md` | Presentation outline (English) | Oct 24 |
| `presentation_outline_zh_tw.md` | Presentation outline (Traditional Chinese) | Oct 24 |

---

## DATA FILES

### Primary Collections (Used by init_collections.py)
| File | Size | Type | Records | Purpose |
|------|------|------|---------|---------|
| `chunks/text_chunks.jsonl` | 4.0MB | Document chunks | 1,067 | Buddhist texts from 12 books |
| `chunks/audio_chunks.jsonl` | 4.7MB | Audio transcripts | 2,287 | Transcribed teachings |
| `chunks/event_chunks.jsonl` | 276KB | Events | 210 | Buddhist events & activities |

### Metadata & Catalog Files
| File | Size | Type | Records | Purpose |
|------|------|------|---------|---------|
| `ddm_books.json` | 1.7MB | JSON | 180+ books | Law Drum book catalog (用於 BookRecommender) |
| `events.json` | 194KB | JSON | Events | Buddhist events database |
| `faq.json` | 1.2MB | JSON | FAQs | Query recommendations collection |
| `processed_audios.json` | 2.8MB | JSON | Audio metadata | Audio teaching metadata |
| `processed_videos.json` | 19MB | JSON | Video metadata | Video teaching metadata |

### Test & Report Files (Can be cleaned up)
| File | Size | Type | Purpose |
|------|------|------|---------|
| `init_result.json` | 8.2K | Results | Previous initialization results |
| `init_retry.json` | 57KB | Results | Retry logs from initialization |
| `ollama_init.json` | 50K | Results | Ollama initialization results |
| `ollama_parallel_init.json` | 6.1K | Results | Parallel init results |
| `dashscope_init.json` | 32K | Results | DashScope initialization (deprecated) |
| `*_test_report.json` | 5-22K | Results | Test reports (4 files) |
| `events_20250730_124843.jsonl` | 223K | Data | Legacy events export |
| `failed_upload_points.json` | 2 bytes | Empty | Placeholder |
| `embedding_config.json` | 116 bytes | Config | Legacy config |

---

## FRONTEND FILES

### Active Frontend (Current - Nov 4)
**Location**: `/home/chiweic/repo/rag_08122025/frontend_v2/`

| File | Size | Purpose |
|------|------|---------|
| `index.html` | 61KB | Main chat interface (Perplexity UI style) |
| `login.html` | 19KB | Login & registration form |

**Features**:
- Modern gradient UI (purple theme)
- Real-time Q&A with streaming responses
- Right sidebar with recommendations (books, events, audio)
- Practice journey modal with statistics
- Quiz generation and evaluation
- Interactive multimedia support

### Legacy Frontend (Deprecated)
**Location**: `/home/chiweic/repo/rag_08122025/frontend/`

| File | Size | Purpose | Status |
|------|------|---------|--------|
| `index.html` | 67KB | Original chat UI (v1) | DEPRECATED |
| `app.js` | 143KB | Original UI logic | DEPRECATED |
| `debug.html` | 2KB | Debug utility | DEPRECATED |
| `debug-init.html` | 1.2KB | Init debug | DEPRECATED |
| `test-basic.html` | 1.2KB | Basic test page | DEPRECATED |

**Status**: `frontend_v2/` is the active production frontend. Legacy `frontend/` can be deleted.

---

## TEST FILES

### Active Tests (Recently Updated)
| File | Lines | Purpose | Last Updated |
|------|-------|---------|--------------|
| `test_stapi_embeddings.py` | 50+ | STAPI embedding validation | Nov 3 |
| `test_config_embeddings.py` | 40+ | Config & embedding test | Nov 3 |
| `test_auth.py` | 400+ | Auth system testing | Nov 1 |
| `test_api_server.py` | 200+ | API endpoint testing | Nov 1 |

### Older Tests (Not Recently Used)
| File | Lines | Purpose | Last Updated | Status |
|------|-------|---------|--------------|--------|
| `test_query_pipeline.py` | 350+ | Query pipeline validation | Oct 28 | Executable |
| `test_book_recommendations.py` | 350+ | Book recommender validation | Oct 28 | Executable |
| `test_audio_recommendations.py` | 350+ | Audio recommender validation | Oct 28 | Executable |
| `test_event_recommendations.py` | 300+ | Event recommender validation | Oct 28 | Executable |
| `test_retrieval_accuracy.py` | 500+ | Retrieval accuracy metrics | Oct 28 | Executable |
| `test_gpu_embedding.py` | 200+ | GPU embedding test | Oct 24 | Outdated (local model path) |
| `test_multi_collection.py` | 200+ | Multi-collection RAG (v2) | Oct 24 | DEPRECATED |
| `quick_test_retrieval.py` | 100+ | Quick retrieval test | Oct 28 | Simple utility |

---

## UTILITY & LEGACY SCRIPTS

### Embedding-Related (Legacy)
| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `dashscope_embeddings.py` | 150+ | DashScope embedding wrapper | ACTIVE (imported by llm_factory.py) |
| `ollama_parallel_init.py` | 200+ | Old parallel Ollama initialization | DEPRECATED |

### Data Processing (Legacy)
| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `convert_events.py` | 150+ | Event data conversion | DEPRECATED (one-time use) |
| `reorganize_chunks.py` | 150+ | Chunk reorganization | DEPRECATED (one-time use) |
| `fix_text_chunks.py` | 100+ | Text chunk fixing | DEPRECATED (one-time use) |
| `audio_ingester.py` | 250+ | Audio ingestion (standalone) | DEPRECATED (not integrated) |
| `start_localized.py` | 50+ | Localization setup | DEPRECATED |

### Shell Scripts
| File | Purpose | Status |
|------|---------|--------|
| `start_qdrant.sh` | Start Qdrant container | ACTIVE |
| `check_setup.sh` | Verify environment setup | ACTIVE |
| `check_progress.sh` | Monitor initialization | DEPRECATED |
| `monitor_progress.sh` | Monitor background process | DEPRECATED |
| `monitor_init.sh` | Monitor init process | DEPRECATED |
| `monitor_all_batches.sh` | Monitor batch uploads | DEPRECATED |
| `install_docker.sh` | Docker installation script | One-time use |

### Other Utilities
| File | Purpose | Status |
|------|---------|--------|
| `init.sql` | SQL initialization (unused) | UNUSED |
| `docker-compose.yml` | Docker Compose config | ACTIVE |
| `requirements.txt` | Python dependencies | ACTIVE |

---

## SPECIAL DIRECTORIES

### auth_standalone/
**Purpose**: Standalone authentication system (designed but not integrated into main API)

| File | Purpose | Status |
|------|---------|--------|
| `auth_backend.py` | FastAPI auth backend | Design only |
| `config.py` | Auth config | Design only |
| `database.py` | PostgreSQL user database | Design only |
| `email_service.py` | Email verification service | Design only |
| `.env.example` | Auth .env template | Design only |
| `test_auth_app.py` | Auth testing | Design only |
| `requirements_auth.txt` | Auth dependencies | Design only |

**Status**: Designed for future use. Currently, basic auth is in main `auth.py`.

### chunks/
**Purpose**: Store preprocessed Buddhist text data (JSONL format)

Contains 3 main files:
- `text_chunks.jsonl` - 1,067 text chunks
- `audio_chunks.jsonl` - 2,287 audio chunks  
- `event_chunks.jsonl` - 210 event chunks

### qdrant_storage/
**Purpose**: Qdrant vector database persistent storage

**Size**: ~2-3GB (vectors are large)
**Status**: Git ignored (regenerated on init)

### scripts/
**Purpose**: Utility scripts directory

| File | Purpose |
|------|---------|
| `test_smtp.py` | SMTP email testing |

---

## LOG FILES (Can be cleaned)

| Pattern | Count | Purpose |
|---------|-------|---------|
| `*.log` | 10+ | Server/initialization logs |
| `bge_*.log` | 3 | BGE model initialization logs |
| `init_*.log` | 3 | Collection initialization logs |
| `ollama_*.log` | 6 | Ollama server logs |
| `server_*.log` | 4 | API server logs |
| `test_*.log` | 2 | Test run logs |

**Recommendation**: These can be deleted to reduce repository size.

---

## SUMMARY TABLE: File Categories

| Category | Count | Total Size | Status |
|----------|-------|-----------|--------|
| **CORE Python** | 6 | ~2MB | ACTIVE |
| **API & Server** | 2 | ~75KB | ACTIVE |
| **Recommenders** | 4 | ~1.5MB | ACTIVE |
| **Auth** | 1 | ~400KB | ACTIVE (optional) |
| **Deprecated _v2** | 5 | ~2.5MB | DELETE |
| **Test Files** | 11 | ~2MB | Mixed |
| **Utilities** | 8 | ~2MB | DEPRECATED |
| **Frontend (active)** | 2 | ~80KB | ACTIVE |
| **Frontend (legacy)** | 5 | ~215KB | DELETE |
| **Configuration** | 3 | ~50KB | ACTIVE |
| **Documentation** | 19 | ~300KB | REFERENCE |
| **Data (active)** | 5 | ~30MB | ACTIVE |
| **Data (metadata)** | 5 | ~25MB | ACTIVE |
| **Data (reports/test)** | 9 | ~130KB | DELETE |
| **Logs** | 15+ | ~100KB | DELETE |
| **Other** | 5 | ~300MB | REFERENCE |

---

## CLEANUP RECOMMENDATIONS

### Safe to Delete (Low Risk)
```
DELETE (Deprecated Versions):
- api_v2.py
- main_v2.py
- rag_pipeline_v2.py
- vector_store_v2.py
- data_loader_v2.py
- test_multi_collection.py

DELETE (Legacy Frontend):
- frontend/ (entire directory)

DELETE (Test/Report Files):
- init_result.json
- init_retry.json
- ollama_init.json
- ollama_parallel_init.json
- dashscope_init.json
- *_test_report.json
- events_20250730_124843.jsonl
- failed_upload_points.json
- embedding_config.json

DELETE (Log Files):
- *.log files (10+)

DELETE (Legacy Utilities):
- ollama_parallel_init.py
- convert_events.py
- reorganize_chunks.py
- fix_text_chunks.py
- start_localized.py
```

**Estimated Space Savings**: ~100-200MB

### Keep All
- CORE Python files (main.py, api.py, config.py, etc.)
- Active Frontend (frontend_v2/)
- All data files in chunks/
- All metadata JSON files
- Documentation
- docker-compose.yml
- requirements.txt
- Shell scripts that are still useful

---

## IMPORT DEPENDENCY MAP

### api.py (Main Application)
```
api.py
├── auth.py (optional authentication)
├── config.py (settings)
├── data_loader.py (chunk loading)
├── vector_store.py (Qdrant integration)
│   └── qdrant-client
├── rag_pipeline.py (RAG orchestration)
│   ├── vector_store.py
│   ├── llm_factory.py
│   └── config.py
├── llm_factory.py (LLM & embedding factory)
│   ├── stapi_embeddings.py
│   └── dashscope_embeddings.py
├── book_recommender.py (books from ddm_books.json)
├── query_recommender.py (query suggestions from faq.json)
├── event_recommender.py (events from events.json)
└── audio_recommender.py (audio from processed_audios.json)
```

### init_collections.py (Initialization)
```
init_collections.py
├── config.py (settings)
├── data_loader.py (load chunks)
├── llm_factory.py → stapi_embeddings.py
└── qdrant-client (Qdrant setup)
```

### IMPORTANT: Unused Imports
- `ollama_parallel_init.py` - Only imports deprecated modules, nothing imports it
- `dashscope_embeddings.py` - Imported by llm_factory.py but DashScope provider optional
- `auth.py` - Optional, can be disabled by not calling auth endpoints
- `embedding_config.py` - Superseded by config.py

---

## CONFIGURATION SUMMARY

### Active Environment Variables (from config.py)
```
LLM_PROVIDER=custom (or openai, deepseek, google, dashscope)
LLM_MODEL=specified model
CUSTOM_LLM_BASE_URL=vllm.roverai.com
EMBEDDING_PROVIDER=ollama (or openai, google, huggingface, dashscope)
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5 (via STAPI from ollama.changpt.org)
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=ddm_rag
```

### Embedding Providers Currently Supported
1. **STAPI (Ollama)** - Primary (ollama.changpt.org) - ACTIVE
2. **Local** - Secondary (HuggingFace local models)
3. **OpenAI** - Optional
4. **Google** - Optional
5. **DashScope** - Optional

### LLM Providers Currently Supported
1. **Custom** - Primary (vllm.roverai.com) - ACTIVE
2. **OpenAI** - Optional
3. **DeepSeek** - Optional
4. **Google** - Optional
5. **DashScope** - Optional

---

## NEXT STEPS FOR CLEANUP

1. **Backup** the current state
2. **Delete** deprecated _v2 files and test_multi_collection.py
3. **Delete** legacy frontend/ directory
4. **Delete** test report JSON files
5. **Delete** log files (*.log)
6. **Delete** obsolete utility scripts
7. **Update** git to track removal
8. **Document** the cleanup in CHANGELOG

This would reduce repository size from 7.7GB to ~7.5GB (most data is Qdrant storage).

