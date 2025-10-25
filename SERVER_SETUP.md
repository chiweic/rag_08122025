# DDM RAG Server Setup Guide

This guide provides step-by-step instructions for starting and using the DDM RAG (Retrieval-Augmented Generation) system for Buddhist text analysis.

## Prerequisites

- Python 3.12 or higher
- Virtual environment setup
- Required dependencies installed (`pip install -r requirements.txt`)
- Buddhist text data in `chunks/` directory
- Environment configuration (`.env` file)

## Quick Start

### 1. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 2. Start the Server
```bash
python main.py
```

The server will start on `http://localhost:8000` with the following endpoints:
- API Documentation: `http://localhost:8000/docs`
- Frontend Interface: `http://localhost:8000` (serves `frontend/index.html`)

### 3. Initialize the System
Before using the RAG system, you must initialize it:

```bash
# Initialize with existing vector collection
curl -X POST http://localhost:8000/initialize

# Or recreate the vector collection (slower, use when data changes)
curl -X POST http://localhost:8000/initialize \
  -H "Content-Type: application/json" \
  -d '{"recreate_collection": true}'
```

### 4. Access the Frontend
Open your web browser and navigate to `http://localhost:8000` to use the interactive chat interface.

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Query (Non-streaming)
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什麼是佛教？",
    "top_k": 5,
    "include_sources": true
  }'
```

### Query (Streaming)
```bash
curl -X POST "http://localhost:8000/query/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什麼是佛教？",
    "top_k": 5,
    "include_sources": true
  }'
```

### Book Recommendations
```bash
curl -X POST "http://localhost:8000/books/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "禪修",
    "top_k": 5,
    "min_similarity": 0.1
  }'
```

### Get Individual Chunk Content
```bash
curl "http://localhost:8000/chunk/{chunk_id}"
```

## System Status

### Check if System is Running
```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Expected response:
```json
{
    "status": "healthy",
    "initialized": true,
    "vector_store_connected": true,
    "pipeline_ready": true
}
```

### Collection Information
```bash
curl http://localhost:8000/collection/info
```

## Frontend Features

The web interface at `http://localhost:8000` provides:

1. **Interactive Chat**: Ask questions about Buddhist texts in Chinese or English
2. **Real-time Streaming**: Responses stream in real-time for better user experience
3. **Source References**: View source documents with:
   - Document titles
   - Page numbers
   - Content previews (first 80 characters)
   - Relevance scores
   - Categories
4. **Book Recommendations**: Auto-rotating carousel showing related books (flips every 3 seconds)
5. **Full Content Modal**: Click on source cards to view complete document content

## Configuration

### Environment Variables
The system uses the following key environment variables (configured in `.env`):

- `DEEPSEEK_API_KEY`: Primary LLM provider API key
- `QDRANT_URL`: Vector database URL (default: `http://localhost:6333`)
- `EMBEDDING_MODEL`: Text embedding model
- `MAX_WORKERS`: Parallel processing threads

### Data Structure
- **Chunks Directory**: `chunks/*.jsonl` - Processed Buddhist texts
- **Books Database**: `ddm_books.json` - Book recommendation data
- **Vector Store**: Qdrant collection named `ddm_rag`

## Troubleshooting

### Server Won't Start
1. Check if virtual environment is activated
2. Verify all dependencies are installed: `pip install -r requirements.txt`
3. Ensure port 8000 is not in use: `lsof -i :8000`

### System Not Initialized Error (503)
Run the initialization command:
```bash
curl -X POST http://localhost:8000/initialize
```

### Vector Store Connection Issues
1. Check if Qdrant is running on port 6333
2. Verify `QDRANT_URL` in `.env` file
3. Check firewall settings

### No Book Recommendations
Ensure `ddm_books.json` exists in the project root directory.

### Empty Content Previews
The system automatically includes content previews in source cards. If previews are empty, the chunks may lack text content.

## Development

### Restart Server with Changes
The server runs with auto-reload enabled. Code changes will automatically restart the server.

To manually restart:
1. Stop server (Ctrl+C)
2. Start again: `python main.py`

### Background Mode
To run server in background:
```bash
nohup python main.py > server.log 2>&1 &
```

## Performance Notes

- **Initialization Time**: First-time setup takes ~8-10 seconds
- **Query Response**: Typically 0.01-0.05s for retrieval, 2-5s for synthesis
- **Collection Size**: 1,067 Buddhist text chunks across 12 books
- **Auto-rotation**: Book recommendations flip every 3 seconds (pauses on hover)

## Data Sources

The system contains processed texts from 12 books by Venerable Sheng Yen (聖嚴法師):
- 佛教入門
- 正信的佛教
- 學佛群疑
- 學佛知津
- 律制生活
- 聖者的故事
- 念佛生淨土
- 聖嚴法師教觀音法門
- 聖嚴法師教淨土法門
- And more...

Each document includes rich metadata: title, pagination, keyphrases, categories, and source information.