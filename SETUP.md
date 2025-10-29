# DDM RAG System - Setup and Operation Guide

Complete guide for setting up and running the Buddhist Text RAG system from scratch.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Environment Configuration](#environment-configuration)
4. [Database Setup (Qdrant)](#database-setup-qdrant)
5. [Embedding Initialization](#embedding-initialization)
6. [Starting the Server](#starting-the-server)
7. [Accessing the System](#accessing-the-system)
8. [Common Operations](#common-operations)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- Python 3.12 or higher
- Git
- Docker (for Qdrant vector database)
- curl (for testing)

### Required Resources
- ~10GB disk space
- 8GB RAM minimum (16GB recommended)
- Internet connection for API access

### Required API Keys
- **DashScope API Key** (for embeddings and LLM) - Get from: https://dashscope.aliyun.com/
- Optional: OpenAI, DeepSeek, Google API keys

---

## Initial Setup

### Step 1: Clone the Repository

```bash
# Navigate to your workspace
cd ~/repo

# Clone the repository (replace with actual repo URL)
git clone <repository-url> rag_08122025
cd rag_08122025
```

### Step 2: Create Python Virtual Environment

```bash
# Create virtual environment
python3.12 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Step 3: Install Python Dependencies

```bash
# Install all required packages
pip install -r requirements.txt
```

Expected packages include:
- FastAPI
- Uvicorn
- Qdrant-client
- OpenAI
- Sentence-transformers
- DashScope SDK
- And more...

---

## Environment Configuration

### Step 1: Create Environment File

Create a `.env` file in the project root:

```bash
cp .env.example .env  # If example exists, otherwise create new file
```

### Step 2: Configure API Keys and Settings

Edit `.env` with your configuration:

```bash
# LLM Configuration
LLM_PROVIDER=dashscope
LLM_MODEL=qwen-plus-latest
DEFAULT_TEMPERATURE=0.7
DEFAULT_MAX_TOKENS=2000

# Embedding Configuration
EMBEDDING_PROVIDER=dashscope
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSION=1024

# DashScope API Key (REQUIRED)
DASHSCOPE_API_KEY=sk-your-dashscope-api-key-here

# OpenAI Configuration (Optional)
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1

# DeepSeek Configuration (Optional)
DEEPSEEK_API_KEY=your-deepseek-key-here

# Google Configuration (Optional)
GOOGLE_API_KEY=your-google-key-here

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=ddm_rag

# API Server Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Processing Configuration
MAX_WORKERS=4
BATCH_SIZE=5
```

**Important**: Replace `sk-your-dashscope-api-key-here` with your actual DashScope API key.

---

## Database Setup (Qdrant)

### Step 1: Start Qdrant Vector Database

Using Docker (recommended):

```bash
# Start Qdrant in background
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant

# Verify Qdrant is running
curl http://localhost:6333/
```

Expected response: JSON with Qdrant version information.

### Step 2: Verify Qdrant Connection

```bash
# Check collections (should be empty initially)
curl http://localhost:6333/collections
```

**Alternative: Using Docker Compose**

If you have a `docker-compose.yml`:

```bash
docker-compose up -d qdrant
```

---

## Embedding Initialization

This is the **most critical step** - it creates vector embeddings for all documents and stores them in Qdrant.

### Step 1: Verify Data Files Exist

Check that chunk files are present:

```bash
ls -lh chunks/
```

Expected files:
- `text_chunks.jsonl` (1,067 text chunks, ~4.0MB)
- `audio_chunks.jsonl` (2,287 audio chunks, ~4.7MB)
- `event_chunks.jsonl` (210 event chunks, ~276KB)

**Total: 3,564 chunks**

### Step 2: Run DashScope Embedding Initialization

```bash
# Make script executable
chmod +x dashscope_init.py

# Activate virtual environment (if not already activated)
source venv/bin/activate

# Run initialization (will take 5-15 minutes)
python dashscope_init.py 2>&1 | tee dashscope_init.json
```

**What this does:**
1. Loads all 3,564 chunks from JSONL files
2. Generates 1024-dimensional embeddings using DashScope
3. Creates `ddm_rag` collection in Qdrant
4. Uploads all embeddings to Qdrant

**Progress Monitoring:**

The script will show progress like:
```
INFO - Loaded 3564 chunks from JSONL files
INFO - Creating Qdrant collection: ddm_rag
INFO - Embedding batch 1/713 (5 docs)
INFO - Uploading batch 1/72 (50 points)
...
INFO - Successfully initialized 3564 documents
```

**Expected Duration:**
- With good internet: 5-10 minutes
- With slower connection: 10-20 minutes

### Step 3: Verify Initialization

```bash
# Check Qdrant collection
curl http://localhost:6333/collections/ddm_rag
```

Expected response should show:
```json
{
  "result": {
    "status": "green",
    "vectors_count": 3564,
    "points_count": 3564,
    ...
  }
}
```

---

## Starting the Server

### Step 1: Start the FastAPI Server

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Start server
python main.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Verify Server Health

In another terminal:

```bash
# Check health endpoint
curl http://localhost:8000/health | python3 -m json.tool
```

Expected response:
```json
{
  "status": "healthy",
  "initialized": true,
  "vector_store_connected": true,
  "pipeline_ready": true,
  "qdrant_collection": {
    "name": "ddm_rag",
    "points_count": 3564,
    "status": "green"
  }
}
```

### Step 3: Check Statistics

```bash
# Get system statistics
curl http://localhost:8000/statistics | python3 -m json.tool
```

---

## Accessing the System

### Web Interface

Open your browser and navigate to:

```
http://localhost:8000/
```

You should see: **佛學普化小助手** (Buddhist Assistant)

Features available:
- Main chat interface
- Book recommendations
- Event recommendations
- Audio teaching recommendations
- Quiz generation
- Practice journey tracking

### API Documentation

Interactive API docs:

```
http://localhost:8000/docs
```

This shows all available endpoints with interactive testing.

### API Endpoints

Key endpoints:

- **Query**: `POST /query` - Full RAG pipeline
- **Streaming Query**: `POST /query/stream` - Streaming responses
- **Health Check**: `GET /health`
- **Statistics**: `GET /statistics`
- **Update Config**: `POST /update_config`
- **Book Recommendations**: `POST /books/recommend`
- **Event Recommendations**: `POST /events/recommend`
- **Audio Recommendations**: `POST /audio/recommend`

---

## Common Operations

### Testing a Query

```bash
# Simple query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什麼是禪修？",
    "top_k": 5,
    "include_sources": true
  }' | python3 -m json.tool
```

### Switching LLM Models

```bash
# Switch to OpenAI
curl -X POST http://localhost:8000/update_config \
  -H "Content-Type: application/json" \
  -d '{
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 2000
  }'

# Switch back to DashScope
curl -X POST http://localhost:8000/update_config \
  -H "Content-Type: application/json" \
  -d '{
    "llm_provider": "dashscope",
    "llm_model": "qwen-plus-latest",
    "temperature": 0.7,
    "max_tokens": 2000
  }'
```

### Stopping the Server

```bash
# In the terminal running the server, press:
Ctrl + C
```

### Stopping Qdrant

```bash
# Stop Qdrant container
docker stop qdrant

# Remove Qdrant container (data persists in volume)
docker rm qdrant

# To completely remove (including data)
docker rm -f qdrant
rm -rf qdrant_storage/
```

### Restarting Everything

```bash
# 1. Start Qdrant
docker start qdrant

# 2. Activate virtual environment
source venv/bin/activate

# 3. Start server
python main.py
```

---

## Troubleshooting

### Issue: "Qdrant connection failed"

**Solution:**
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# If not running, start it
docker start qdrant

# Or create new container
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
```

### Issue: "Collection not found"

**Solution:**
```bash
# Re-run embedding initialization
python dashscope_init.py
```

### Issue: "DashScope API key invalid"

**Solution:**
1. Check `.env` file has correct API key
2. Verify key at https://dashscope.aliyun.com/
3. Restart server after updating `.env`

### Issue: "Module not found" errors

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "Port 8000 already in use"

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or change port in .env
API_PORT=8001
```

### Issue: Query returns empty or "nothing"

**Possible causes:**
1. **Embeddings not initialized**: Run `python dashscope_init.py`
2. **Qdrant not running**: Check `docker ps | grep qdrant`
3. **LLM provider issue**: Check API keys in `.env`
4. **Streaming timeout**: Switch to non-streaming mode or verify organization (for OpenAI)

**Debug:**
```bash
# Check Qdrant has data
curl http://localhost:6333/collections/ddm_rag

# Test retrieval only
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"question": "什麼是禪修？", "top_k": 3}'
```

### Issue: Slow responses

**Solutions:**
1. Reduce `top_k` parameter (default 5, try 3)
2. Use faster model (gpt-4o-mini instead of gpt-4o)
3. Reduce `max_tokens` (default 2000, try 1000)
4. Check internet connection
5. Verify Qdrant performance:
   ```bash
   curl http://localhost:6333/collections/ddm_rag
   # Check "optimizer_status" should be "ok"
   ```

### Issue: Frontend shows errors

**Solutions:**
1. Check browser console (F12) for JavaScript errors
2. Verify server is running: `curl http://localhost:8000/health`
3. Clear browser cache
4. Check CORS settings in `.env`

---

## Performance Optimization

### Recommended Settings

For **best quality**:
```env
LLM_MODEL=qwen-plus-latest
DEFAULT_MAX_TOKENS=2000
RETRIEVAL_TOP_K=5
```

For **faster responses**:
```env
LLM_MODEL=qwen-turbo-latest
DEFAULT_MAX_TOKENS=1000
RETRIEVAL_TOP_K=3
```

For **cost optimization**:
```env
LLM_MODEL=qwen-turbo-latest
DEFAULT_MAX_TOKENS=800
RETRIEVAL_TOP_K=3
```

---

## System Architecture Summary

```
User Browser (Frontend)
    ↓
FastAPI Server (port 8000)
    ↓
RAG Pipeline
    ├── DashScope Embeddings (query → vector)
    ├── Qdrant Vector DB (similarity search)
    └── DashScope LLM (answer synthesis)
```

**Data Flow:**
1. User asks question → Frontend
2. Frontend sends to `/query/stream`
3. Server embeds question (DashScope)
4. Server searches Qdrant for similar chunks
5. Server sends chunks + question to LLM (DashScope)
6. LLM streams answer back
7. Frontend displays answer + sources

---

## Maintenance

### Daily Operations
- Server should run continuously
- Monitor logs for errors
- Check Qdrant disk space

### Weekly Tasks
- Review query logs
- Update API keys if needed
- Backup Qdrant data:
  ```bash
  docker exec qdrant tar czf /tmp/backup.tar.gz /qdrant/storage
  docker cp qdrant:/tmp/backup.tar.gz ./backups/
  ```

### Monthly Tasks
- Update dependencies: `pip install --upgrade -r requirements.txt`
- Review and optimize slow queries
- Update LLM models if new versions available

---

## Useful Commands Reference

```bash
# Start everything
docker start qdrant
source venv/bin/activate
python main.py

# Check status
curl http://localhost:8000/health
curl http://localhost:6333/collections/ddm_rag

# View logs
tail -f server.log  # If logging to file

# Monitor Qdrant
docker logs qdrant -f

# Backup Qdrant
docker exec qdrant tar czf /qdrant/backup.tar.gz /qdrant/storage

# Restore Qdrant
# 1. Stop Qdrant
# 2. Extract backup to qdrant_storage/
# 3. Start Qdrant

# Re-initialize embeddings (if needed)
python dashscope_init.py

# Test query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "什麼是禪修？", "top_k": 3}'
```

---

## Support and Documentation

- **API Documentation**: http://localhost:8000/docs
- **Project Documentation**: See CLAUDE.md for detailed system architecture
- **Qdrant Docs**: https://qdrant.tech/documentation/
- **DashScope Docs**: https://dashscope.aliyun.com/

---

## Quick Start Checklist

- [ ] Clone repository
- [ ] Create and activate virtual environment
- [ ] Install dependencies (`pip install -r requirements.txt`)
- [ ] Configure `.env` with DashScope API key
- [ ] Start Qdrant (`docker run -d -p 6333:6333 qdrant/qdrant`)
- [ ] Run embedding initialization (`python dashscope_init.py`)
- [ ] Verify Qdrant has 3,564 points
- [ ] Start server (`python main.py`)
- [ ] Test health endpoint
- [ ] Access frontend at http://localhost:8000/
- [ ] Test a query

**Total setup time:** 30-60 minutes (mostly waiting for embeddings)

---

## Version Information

- Python: 3.12+
- FastAPI: Latest
- Qdrant: Latest (Docker)
- DashScope: text-embedding-v4 (embeddings), qwen-plus-latest (LLM)

Last updated: 2025-10-29
