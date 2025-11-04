# DDM RAG System

A Retrieval-Augmented Generation (RAG) system for Buddhist texts by Venerable Sheng Yen (聖嚴法師), featuring semantic search, recommendations, and an interactive web interface.

## Features

- **Multi-Modal Content**: Text (1,067 chunks), Audio (2,287 chunks), Events (210 items)
- **Advanced RAG Pipeline**: Vector search + LLM synthesis with streaming support
- **Smart Recommendations**:
  - 📚 Book recommendations (TF-IDF, 622 books)
  - 🏮 Event recommendations (semantic search, 210 events)
  - 🎧 Audio recommendations (2,287 audio teachings)
  - 💭 Related query suggestions (20,744 FAQ questions)
- **Modern Web Interface**: Real-time streaming responses, carousels, and interactive UI
- **Flexible LLM Support**: vLLM, OpenAI, DeepSeek, Google Gemini, DashScope
- **Configurable Embeddings**: STAPI (Ollama), DashScope, OpenAI, Google, HuggingFace
- **Vector Database**: Qdrant for efficient similarity search
- **RESTful API**: FastAPI with automatic OpenAPI documentation
- **OpenAI v1 Compatible**: Can be used as drop-in replacement for OpenAI API

## System Requirements

- Python 3.12
- Docker (for Qdrant)
- ~30MB of preprocessed data
- Network access to embedding/LLM providers

## Quick Start

### 1. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy and edit the environment configuration:

```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

**Key configurations** (see `.env` for all options):

```env
# LLM Provider (custom = vLLM)
LLM_PROVIDER=custom
LLM_MODEL=cpatonn/Qwen3-4B-Instruct-2507-AWQ-4bit
CUSTOM_LLM_BASE_URL=https://vllm.roverai.com/v1
CUSTOM_LLM_API_KEY=dummy

# Embeddings (ollama = STAPI)
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
OLLAMA_BASE_URL=http://ollama.changpt.org/v1

# Vector Database
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=ddm_rag
```

### 4. Start Qdrant

**Option A - Docker Compose (Recommended)**:
```bash
docker-compose up -d
```

**Option B - Docker Command**:
```bash
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant
```

Verify Qdrant is running:
```bash
curl http://localhost:6333/health
```

### 5. Initialize Collections

**IMPORTANT**: Run this before starting the server for the first time.

```bash
# Initialize all collections (main + FAQ)
python init_collections.py all

# Or initialize separately:
python init_collections.py main  # Main document collection
python init_collections.py faq   # FAQ collection for query recommendations
```

This will:
- Load data from `chunks/*.jsonl` and `faq.json`
- Generate embeddings using your configured provider
- Upload vectors to Qdrant (takes ~15-20 minutes)
- Show progress with estimated time remaining

### 6. Start the Server

```bash
python main.py
```

The system will:
- Auto-connect to Qdrant and verify collections
- Initialize RAG pipeline and recommenders
- Start serving requests immediately

### 7. Access the Application

- **Web Interface**: http://localhost:8000/
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Web Interface

Open http://localhost:8000/ to access the **佛學普化小助手** (Buddhist Learning Assistant):

### Features:
- 💬 **Real-time Q&A**: Ask questions with streaming responses
- 📚 **Book Recommendations**: TF-IDF-based book suggestions
- 🏮 **Event Recommendations**: Semantic search for Buddhist events
- 🎧 **Audio Teachings**: Recommended audio content
- 📝 **Summarization**: Generate summaries of answers
- 🧠 **Quiz Generation**: Interactive learning quizzes
- 🔍 **Related Queries**: Discover similar questions
- 🎯 **Retrieval Mode**: Toggle between full RAG and retrieval-only

## Core API Endpoints

### System Management

#### Health Check
```bash
GET /health
```

Returns system status and Qdrant collection info.

#### Statistics
```bash
GET /statistics
```

Returns collection statistics and data counts.

### RAG Operations

#### Query (Full RAG Pipeline)
```bash
POST /query
{
  "question": "什麼是禪修？",
  "top_k": 5,
  "include_sources": true
}
```

Complete RAG pipeline: retrieves relevant documents and synthesizes an answer.

#### Streaming Query
```bash
POST /query/stream
{
  "question": "什麼是禪修？",
  "top_k": 10,
  "include_sources": true
}
```

Returns streaming Server-Sent Events (SSE) for real-time responses.

#### Retrieve Only
```bash
POST /retrieve
{
  "query": "禪修的方法",
  "top_k": 10
}
```

Returns relevant documents without synthesis.

#### Synthesize Only
```bash
POST /synthesize
{
  "question": "Explain the concept",
  "contexts": ["context1", "context2"],
  "prompt_type": "qa"
}
```

Generates an answer from provided contexts.

### Recommendations

#### Book Recommendations
```bash
POST /books/recommend
{
  "query": "禪修",
  "top_k": 3
}
```

Returns book recommendations using TF-IDF similarity.

#### Event Recommendations
```bash
POST /events/recommend
{
  "query": "禪修",
  "top_k": 3
}
```

Returns event recommendations using semantic search.

#### Audio Recommendations
```bash
POST /audio/recommend
{
  "query": "禪修",
  "top_k": 3
}
```

Returns audio teaching recommendations.

#### Related Queries
```bash
POST /queries/related
{
  "query": "什麼是禪修",
  "top_k": 5,
  "min_similarity": 0.5
}
```

Returns semantically similar questions from FAQ database.

### Interactive Features

#### Summarize
```bash
POST /summarize
{
  "text": "Long answer text to summarize..."
}
```

Generate a concise summary using LLM.

#### Generate Quiz
```bash
POST /quiz/generate
{
  "reference_chunks": ["chunk1", "chunk2"],
  "num_questions": 3
}
```

Generate quiz questions from reference text.

#### Evaluate Quiz
```bash
POST /quiz/evaluate
{
  "question": "What is meditation?",
  "user_answer": "A practice for mindfulness",
  "reference_context": "Meditation is..."
}
```

Evaluate user answers with LLM feedback.

### OpenAI v1 Compatible

#### List Models
```bash
GET /v1/models
```

#### Chat Completions (with RAG)
```bash
POST /v1/chat/completions
{
  "model": "ddm-rag",
  "messages": [{"role": "user", "content": "什麼是禪修？"}],
  "stream": false
}
```

Compatible with OpenAI SDK - can be used as drop-in replacement.

## Configuration

### Environment Variables

All settings are configurable via `.env`:

**LLM Providers:**
- `custom` - vLLM or custom OpenAI-compatible endpoint
- `openai` - OpenAI GPT models
- `deepseek` - DeepSeek models
- `google` - Google Gemini models
- `dashscope` - Alibaba DashScope models

**Embedding Providers:**
- `ollama` - STAPI embeddings via Ollama-compatible API
- `dashscope` - Alibaba DashScope embeddings
- `openai` - OpenAI embeddings
- `google` - Google embeddings
- `huggingface` - HuggingFace models (local or remote)

**Performance Settings:**
```env
MAX_WORKERS=4              # Parallel processing threads
BATCH_SIZE=5               # Embedding batch size
DEFAULT_TEMPERATURE=0.7    # LLM temperature
DEFAULT_MAX_TOKENS=1000    # Max tokens per response
```

### Dynamic Configuration

Update settings without restarting:

```bash
POST /update_config
{
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "llm_temperature": 0.3,
  "embedding_provider": "openai"
}
```

## Project Structure

```
rag_08122025/
├── Core Python Modules (14 files)
│   ├── main.py                  # Entry point
│   ├── api.py                   # Main FastAPI app (1,290 lines)
│   ├── config.py                # Settings management
│   ├── vector_store.py          # Qdrant integration
│   ├── rag_pipeline.py          # RAG orchestration
│   ├── llm_factory.py           # LLM/embedding factory
│   ├── data_loader.py           # JSONL chunk loader
│   ├── stapi_embeddings.py      # STAPI embeddings client
│   ├── init_collections.py      # Unified initialization
│   ├── book_recommender.py      # Book recommendations (TF-IDF)
│   ├── query_recommender.py     # Related queries
│   ├── event_recommender.py     # Event matching (semantic)
│   ├── audio_recommender.py     # Audio recommendations
│   └── auth.py                  # Authentication (optional)
│
├── frontend_v2/                 # Active web interface
│   └── index.html               # 1,348 lines, fully functional
│
├── chunks/                      # Preprocessed data (JSONL)
│   ├── text_chunks.jsonl        # 1,067 text chunks (4.0MB)
│   ├── audio_chunks.jsonl       # 2,287 audio chunks (4.7MB)
│   └── event_chunks.jsonl       # 210 event chunks (276KB)
│
├── Data Files
│   ├── ddm_books.json           # 622 books catalog (1.7MB)
│   ├── events.json              # 210 events (198KB)
│   ├── faq.json                 # 20,744 FAQ questions
│   ├── processed_audios.json    # Audio metadata (2.9MB)
│   └── processed_videos.json    # Video metadata (19MB)
│
├── Configuration
│   ├── .env                     # Environment configuration
│   ├── requirements.txt         # Python dependencies
│   └── .gitignore              # Git ignore rules
│
├── Documentation
│   ├── README.md               # This file
│   ├── CLAUDE.md               # Claude Code project guide
│   ├── SETUP.md                # Detailed setup instructions
│   ├── HASH_COLLISION_FIX.md   # Technical notes
│   └── CLEANUP_SUMMARY.md      # Codebase organization
│
└── backup_deprecated/          # Archived old code
```

## Data Overview

- **Total Chunks**: 3,564 (text: 1,067, audio: 2,287, events: 210)
- **Books**: 622 in catalog (法鼓文化)
- **Events**: 210 Buddhist activities
- **FAQ Questions**: 20,744 questions
- **Languages**: Traditional Chinese + English
- **Embedding Dimension**: 1024 (STAPI/bge-large-zh-v1.5)

## Development

### Running Tests

```bash
# Test query endpoint
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "什麼是禪修？", "top_k": 5, "include_sources": true}'

# Test book recommendations
curl -X POST http://localhost:8000/books/recommend \
  -H "Content-Type: application/json" \
  -d '{"query": "禪修", "top_k": 3}'

# Test health endpoint
curl http://localhost:8000/health
```

### Re-initializing Collections

If you need to regenerate embeddings:

```bash
# This will recreate the collections from scratch
python init_collections.py all
```

### Accessing Logs

The server logs to stdout. To save logs:

```bash
python main.py > server.log 2>&1 &
```

## Performance

- **Initialization Time**: ~15-20 minutes (one-time, generates all embeddings)
- **Query Response**: 2-6 seconds (depends on LLM provider)
- **Streaming**: Real-time token-by-token responses
- **Retrieval Only**: <1 second
- **Recommendations**: <500ms (books), <1s (events/audio)

All API endpoints include computation time tracking.

## Troubleshooting

### Common Issues

**"Collection not found" error:**
```bash
# Initialize collections first
python init_collections.py all
```

**Qdrant connection error:**
```bash
# Check if Qdrant is running
curl http://localhost:6333/health

# Restart Qdrant
docker-compose restart
```

**Embedding generation fails:**
- Check your `OLLAMA_BASE_URL` or embedding provider settings in `.env`
- Verify network connectivity to the embedding service

**LLM timeout:**
- Check `CUSTOM_LLM_BASE_URL` is accessible
- Try increasing timeout in `config.py`

**Frontend not loading:**
- Ensure server is running on port 8000
- Check browser console for errors
- Verify `API_BASE_URL` in frontend matches your setup

## Authentication (Optional)

The system includes optional JWT-based authentication (currently not enabled by default). To enable:

1. Configure PostgreSQL database
2. Update `.env` with database credentials
3. Uncomment auth routes in `api.py`

See `auth.py` for implementation details.

## Contributing

This is a specialized system for Buddhist text RAG. For modifications:

1. Core logic: `api.py`, `rag_pipeline.py`
2. LLM integration: `llm_factory.py`
3. Vector search: `vector_store.py`
4. Frontend: `frontend_v2/index.html`
5. Data processing: `data_loader.py`

## License

See project maintainers for license information.

## Support

For issues or questions, refer to:
- `CLAUDE.md` - Comprehensive project guide
- `SETUP.md` - Detailed setup instructions
- API Documentation: http://localhost:8000/docs

---

**Built with**: FastAPI, Qdrant, STAPI, vLLM, and ❤️ for Buddhist education.
