# DDM RAG Server Startup Guide

## Prerequisites Checklist

### ✅ Completed
- [x] Qdrant Docker setup ([docker-compose.yml](docker-compose.yml))
- [x] Environment configuration ([.env](.env))
- [x] Data chunks available (chunks/*.jsonl)

### ⚠️ Before Starting

1. **Check Qdrant is Running**
   ```bash
   sudo docker ps | grep qdrant
   # If not running:
   sudo docker compose up -d
   ```

2. **Verify Qdrant Health**
   ```bash
   curl http://localhost:6333/health
   # Should return: {"title":"qdrant - vector search engine","version":"..."}
   ```

3. **Check Custom LLM Endpoint** (Optional - if using custom provider)
   ```bash
   curl http://area51r5:8000/v1/models
   # Should return list of available models
   ```

## Current .env Configuration

### Required Settings
- **LLM Provider**: `custom` (Qwen3-30B at area51r5:8000)
- **Embedding**: `huggingface` (BAAI/bge-m3, 1024-dim)
- **Vector DB**: Qdrant at localhost:6333
- **API Server**: 0.0.0.0:8000

### ⚠️ Important Notes

1. **Embedding Model Changed**
   - Original: Custom fine-tuned model (512-dim) - **NOT FOUND**
   - Current: BAAI/bge-m3 (1024-dim)
   - **Warning**: Different embedding dimensions! If you have existing Qdrant data with 512-dim vectors, you'll need to:
     - Either find the original embedding model
     - Or recreate the collection with new dimensions

2. **Custom LLM Endpoint**
   - URL: `http://area51r5:8000/v1`
   - Make sure this endpoint is accessible from your machine
   - Test with: `curl http://area51r5:8000/v1/models`

3. **API Keys** (Currently not configured)
   - OpenAI, DeepSeek, Google, DashScope - all optional
   - Only needed if you switch LLM_PROVIDER

## Starting the Server

### Option 1: Direct Start
```bash
# Activate virtual environment
source venv/bin/activate

# Start server
python main.py
```

### Option 2: With Logging
```bash
source venv/bin/activate
python main.py 2>&1 | tee server.log
```

### Option 3: Background Mode
```bash
source venv/bin/activate
nohup python main.py > server.log 2>&1 &
echo $! > server.pid
```

## After Server Starts

### 1. Check Server Health
```bash
curl http://localhost:8000/health
```

### 2. Initialize Vector Store (REQUIRED - First Time Only)
```bash
curl -X POST http://localhost:8000/initialize
```

This will:
- Load all chunk data (text, audio, events)
- Generate embeddings using BAAI/bge-m3
- Upload vectors to Qdrant
- Takes 5-15 minutes depending on system

### 3. Get Statistics
```bash
curl http://localhost:8000/statistics
```

### 4. Test Query
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "什麼是禪修？", "top_k": 5, "include_sources": true}'
```

### 5. Access Web Interface
Open browser to: http://localhost:8000/

### 6. API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Common Issues & Solutions

### Issue 1: Qdrant Connection Failed
**Error**: `Failed to connect to Qdrant`

**Solution**:
```bash
# Check if Qdrant is running
sudo docker ps | grep qdrant

# If not, start it
sudo docker compose up -d

# Wait a few seconds, then test
curl http://localhost:6333/health
```

### Issue 2: Embedding Model Not Found
**Error**: `Model BAAI/bge-m3 not found`

**Solution**:
```bash
# The model will auto-download from HuggingFace on first use
# Ensure internet connection is available
# Download may take 5-10 minutes
```

### Issue 3: Custom LLM Unreachable
**Error**: `Failed to connect to http://area51r5:8000/v1`

**Solution**:
```bash
# Test connectivity
ping area51r5

# Test endpoint
curl http://area51r5:8000/v1/models

# If unreachable, switch to another provider in .env:
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o-mini
# OPENAI_API_KEY=sk-your-key-here
```

### Issue 4: Port Already in Use
**Error**: `Address already in use: 8000`

**Solution**:
```bash
# Find what's using port 8000
sudo lsof -i :8000

# Kill the process or change port in .env:
# API_PORT=8001
```

### Issue 5: Dimension Mismatch
**Error**: `Vector dimension mismatch: expected 512, got 1024`

**Solution**:
```bash
# Recreate collection with new dimensions
curl -X POST http://localhost:8000/initialize \
  -H "Content-Type: application/json" \
  -d '{"recreate_collection": true}'
```

## Stop the Server

### If running in foreground
Press `Ctrl+C`

### If running in background
```bash
# If you saved the PID
kill $(cat server.pid)

# Or find and kill
pkill -f "python main.py"
```

## Quick Reference

### All-in-One Startup
```bash
# 1. Start Qdrant
sudo docker compose up -d

# 2. Activate venv
source venv/bin/activate

# 3. Start server
python main.py
```

### All-in-One Shutdown
```bash
# 1. Stop server (Ctrl+C or kill PID)

# 2. Stop Qdrant (optional - data persists)
sudo docker compose down
```

## Next Steps

After successful startup:
1. Initialize the system (if first time)
2. Test with sample queries
3. Explore the web interface
4. Check API documentation
5. Consider setting up systemd service for auto-start (see production deployment)
