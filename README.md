# DDM RAG System

A Retrieval-Augmented Generation (RAG) system for Buddhist texts by Venerable Sheng Yen (聖嚴法師).

## Features

- **Configurable LLM Providers**: Support for OpenAI, DeepSeek, and Google Gemini
- **Flexible Embeddings**: OpenAI, Google, or local HuggingFace models
- **Vector Database**: Qdrant for efficient similarity search
- **RESTful API**: FastAPI-based endpoints with automatic documentation
- **Computation Tracking**: All endpoints report processing times
- **Buddhist Text Corpus**: 12 pre-processed texts with 1,067 chunks

## Installation

1. **Activate virtual environment**:
```bash
source venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**:
Ensure your `.env` file contains the necessary API keys and settings.

4. **Start Qdrant** (if not already running):

**Option A - Using Docker Compose (Recommended)**:
```bash
docker-compose up -d
```

**Option B - Using Docker directly**:
```bash
docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant
```

To stop Qdrant:
```bash
docker-compose down
```

## Running the Application

```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Key Endpoints

### 1. Initialize System
```bash
POST /initialize
```
Loads data and creates vector embeddings. Must be called before using other endpoints.

### 2. Query (RAG Pipeline)
```bash
POST /query
{
  "question": "What is the Buddhist view on meditation?",
  "top_k": 5,
  "include_sources": true
}
```
Complete RAG pipeline: retrieves relevant documents and synthesizes an answer.

### 3. Retrieve Only
```bash
POST /retrieve
{
  "query": "meditation techniques",
  "top_k": 10
}
```
Returns relevant documents without synthesis.

### 4. Synthesize Only
```bash
POST /synthesize
{
  "question": "Explain the concept",
  "contexts": [...],
  "prompt_type": "qa"
}
```
Generates an answer from provided contexts.

### 5. Update Configuration
```bash
POST /update_config
{
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "llm_temperature": 0.3
}
```
Dynamically update LLM or embedding configurations.

### 6. Get Statistics
```bash
GET /statistics
```
Returns information about loaded data and vector store.

## Configuration

The system can be configured through environment variables or the `/update_config` endpoint:

- **LLM Providers**: `openai`, `deepseek`, `google`
- **Embedding Providers**: `openai`, `huggingface`, `local`
- **Vector Store**: Qdrant (configurable URL and collection name)

## Project Structure

```
rag_08122025/
├── chunks/           # Pre-processed Buddhist texts (JSONL)
├── venv/            # Python virtual environment
├── api.py           # FastAPI application
├── config.py        # Configuration management
├── data_loader.py   # Data loading utilities
├── llm_factory.py   # LLM and embedding factory
├── rag_pipeline.py  # RAG pipeline implementation
├── vector_store.py  # Qdrant integration
├── main.py          # Application entry point
└── requirements.txt # Python dependencies
```

## Performance

All API endpoints include computation time tracking:
- Retrieval time
- Synthesis time
- Total processing time

## Notes

- The system uses pre-processed chunks from the `chunks/` directory
- Supports multilingual content (Chinese/English)
- Embeddings are cached in Qdrant for efficient retrieval
- The first initialization may take time to generate embeddings