# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a DDM RAG (Retrieval-Augmented Generation) system for processing and querying Buddhist texts, specifically works by Venerable Sheng Yen (聖嚴法師). The system is designed to enable semantic search and question-answering over Buddhist literature with a comprehensive web interface.

## System Architecture

### Technology Stack
- **Backend**: FastAPI (Python 3.12)
- **Vector Database**: Qdrant (localhost:6333)
- **Embeddings**: Fine-tuned local model at `/home/chiweic/repo/synthetic_dataset/emb_finetune_small_32/final` (512-dim)
- **LLM Providers**: Custom (Qwen3-30B), DeepSeek, OpenAI, Google Gemini, DashScope
- **Frontend**: Vanilla JavaScript with modern CSS (no framework)

### Data Structure
The `chunks/` directory contains three types of processed content in JSONL format:

1. **Text Chunks** (1,067 items - 4.0MB)
   - Buddhist texts from 12 books
   - Each chunk contains: id, header, content, metadata
   - Metadata includes: title, summary, keyphrases, category, source, pagination
   - Example source: Buddhist entrance texts by Master Sheng Yen

2. **Audio Chunks** (2,287 items - 4.7MB)
   - Transcribed audio teachings
   - Contains: audio_id, audio_url, speaker, timestamp ranges
   - Organized by sections and topics

3. **Event Chunks** (210 items - 276KB)
   - Buddhist events and activities
   - Contains: event_id, title, location, time_period, category
   - Includes organizer, target audience, and venue details

## Core API Endpoints

### Primary Endpoints ([api.py](api.py))
The main API file is 1,290 lines and includes:

#### System Management
- `POST /initialize` - Load data and create vector embeddings (required first)
- `GET /health` - System health check
- `GET /statistics` - Collection and data statistics
- `POST /update_config` - Dynamic LLM/embedding configuration

#### RAG Operations
- `POST /query` - Full RAG pipeline (retrieval + synthesis)
- `POST /query/stream` - Streaming RAG responses
- `POST /retrieve` - Document retrieval only
- `POST /synthesize` - Answer synthesis from provided contexts

#### Recommendations & Enrichment
- `POST /books/recommend` - Book recommendations based on query
- `GET /books/random/{count}` - Random book suggestions
- `GET /books/{isbn}` - Book details by ISBN
- `POST /queries/related` - Related queries (semantic similarity)
- `GET /queries/popular` - Popular queries
- `POST /events/recommend` - Event recommendations (解行並重 - Theory + Practice)
- `GET /events/upcoming` - Upcoming events
- `POST /audio/recommend` - Audio teaching recommendations
- `GET /audio/{audio_id}` - Audio chunk details

#### Interactive Features
- `POST /translate` - Text translation (placeholder)
- `POST /summarize` - LLM-based summarization
- `POST /quiz/generate` - Generate quiz from reference chunks
- `POST /quiz/evaluate` - Evaluate quiz answers with LLM
- `GET /query/history` - Recent query cache (50 items)

#### OpenAI v1 Compatible
- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat completions with RAG

### Frontend Interface ([frontend/index.html](frontend/index.html))

**佛學普化小助手** (Buddhist Assistant) - 2,264 lines of HTML/CSS

Features:
- **Main Chat Interface**: Real-time Q&A with streaming responses
- **Right Sidebar**:
  - 📚 Book recommendations (法鼓文化)
  - 🏮 Event recommendations (解行並重)
  - 🎧 Audio teaching recommendations
- **Interactive Actions**:
  - 📝 Summarize last answer
  - 🧠 Quiz generation and evaluation
- **Practice Journey Modal**:
  - Practice statistics (days, hours, sutras read, events attended)
  - Monthly calendar visualization
  - Quiz history tracking
  - Achievement badges
- **Popular Queries Section**: Quick-access common questions
- **Multimedia Support**: Video/audio player modals with waveform visualizations

Design: Modern gradient UI (purple theme), responsive layout, smooth animations

## Key Components

### Backend Modules

1. **[config.py](config.py:1)** - Pydantic settings with .env integration
   - LLM/embedding provider configuration
   - Qdrant connection settings
   - API server settings (host, port, CORS)

2. **data_loader.py** - JSONL chunk loader with metadata extraction

3. **vector_store.py / vector_store_v2.py** - Qdrant integration
   - Collection management
   - Batch document upload
   - Similarity search

4. **llm_factory.py** - Factory pattern for LLM and embedding creation
   - Supports: OpenAI, DeepSeek, Google Gemini, DashScope, Custom
   - HuggingFace sentence-transformers for embeddings

5. **rag_pipeline.py / rag_pipeline_v2.py** - RAG orchestration
   - Document retrieval
   - Context synthesis
   - Streaming support

6. **Recommenders**:
   - **book_recommender.py** - Book recommendations from ddm_books.json
   - **query_recommender.py** - Related query suggestions
   - **event_recommender.py** - Buddhist event matching
   - **audio_recommender.py** - Audio teaching recommendations

### Data Files

- **ddm_books.json** (1.7MB) - 法鼓文化 book catalog
- **events.json** (198KB) - Buddhist events database
- **processed_audios.json** (2.9MB) - Audio metadata
- **processed_videos.json** (19MB) - Video metadata

## Development Workflow

### Initial Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Ensure Qdrant is running
docker run -p 6333:6333 qdrant/qdrant
```

### Running the Server
```bash
# Start API server (runs on 0.0.0.0:8000)
python main.py

# Access points:
# - Frontend: http://localhost:8000/
# - API docs: http://localhost:8000/docs
# - Health: http://localhost:8000/health
```

### First-Time Initialization
```bash
# Initialize vector store (required before queries)
curl -X POST http://localhost:8000/initialize

# Force recreate collection
curl -X POST http://localhost:8000/initialize \
  -H "Content-Type: application/json" \
  -d '{"recreate_collection": true}'
```

### Testing Endpoints
```bash
# Query example
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "什麼是禪修？", "top_k": 5, "include_sources": true}'

# Get statistics
curl http://localhost:8000/statistics
```

## Configuration

### Environment Variables (.env)
Key configurations:
- **LLM**: `LLM_PROVIDER=custom`, `LLM_MODEL=cpatonn/Qwen3-30B-A3B-Instruct-2507-AWQ`
- **Custom LLM**: `CUSTOM_LLM_BASE_URL=http://area51r5:8000/v1`
- **Embeddings**: `EMBEDDING_MODEL=/home/chiweic/repo/synthetic_dataset/emb_finetune_small_32/final`
- **Vector DB**: `QDRANT_URL=http://localhost:6333`
- **Providers**: DeepSeek, OpenAI, Google, DashScope API keys configured

### Performance Settings
- `MAX_WORKERS=4` - Parallel processing threads
- `BATCH_SIZE=5` - Embedding batch size
- `DEFAULT_TEMPERATURE=0.7`
- `DEFAULT_MAX_TOKENS=1000`

## Project Structure

```
rag_08122025/
├── chunks/                     # Data (JSONL format)
│   ├── text_chunks.jsonl      # 1,067 text chunks (4.0MB)
│   ├── audio_chunks.jsonl     # 2,287 audio chunks (4.7MB)
│   └── event_chunks.jsonl     # 210 event chunks (276KB)
├── frontend/                   # Web interface
│   ├── index.html             # Main UI (2,264 lines)
│   └── app.js                 # Frontend logic
├── api.py                      # Main FastAPI app (1,290 lines)
├── main.py                     # Entry point
├── config.py                   # Settings management
├── data_loader.py              # Chunk data loader
├── vector_store.py             # Qdrant integration
├── rag_pipeline.py             # RAG orchestration
├── llm_factory.py              # LLM/embedding factory
├── book_recommender.py         # Book recommendations
├── query_recommender.py        # Query suggestions
├── event_recommender.py        # Event matching
├── audio_recommender.py        # Audio recommendations
├── ddm_books.json              # Book catalog (1.7MB)
├── events.json                 # Events database (198KB)
├── processed_audios.json       # Audio metadata (2.9MB)
├── processed_videos.json       # Video metadata (19MB)
├── requirements.txt            # Python dependencies
└── .env                        # Environment configuration
```

## Important Notes

### System Requirements
- Python 3.12
- Qdrant vector database (Docker recommended)
- ~8.9MB of preprocessed chunk data
- GPU recommended for local embedding model
- Network access to custom LLM endpoint (area51r5:8000)

### Data Characteristics
- **Total Chunks**: 3,564 (text: 1,067, audio: 2,287, events: 210)
- **Multilingual**: Chinese (Traditional) and English
- **Source Types**: PDF books, audio transcripts, event listings
- **Embedding Dimension**: 512 (custom fine-tuned model)

### Key Features
1. **Multi-modal Content**: Text, audio, video, events
2. **Rich Recommendations**: Books, queries, events, audio
3. **Interactive Learning**: Quiz generation and evaluation
4. **Practice Tracking**: User journey and achievements (frontend only, no backend storage yet)
5. **Streaming Responses**: Real-time answer generation
6. **OpenAI Compatible**: Can be used as drop-in replacement for OpenAI API

### Development Status
- ✅ Core RAG pipeline functional
- ✅ Multi-provider LLM support
- ✅ Recommendation systems implemented
- ✅ Interactive quiz features
- ⚠️ Translation endpoint is placeholder (not implemented)
- ⚠️ Practice journey data not persisted (frontend mock only)
- ⚠️ Authentication system designed but not implemented (see AUTH_IMPLEMENTATION_PLAN.md)

### Performance Considerations
- First initialization takes time (embedding generation)
- Collection info checked before re-loading data
- Batch processing for embeddings (50 chunks/batch for upload, 5 for generation)
- Query history cached in memory (deque, 50 items max)
- Streaming available for better UX on long responses

## Troubleshooting

### Common Issues
1. **"System not initialized"**: Run `POST /initialize` first
2. **Embedding errors**: Check local model path exists
3. **LLM timeout**: Verify custom LLM endpoint is accessible
4. **Qdrant connection**: Ensure Docker container is running on port 6333

### Logs
- Logging configured at INFO level
- Check console output for initialization progress
- API errors logged with full stack traces
