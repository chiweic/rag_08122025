#!/bin/bash

# Kill any existing Python server
echo "Stopping any existing servers..."
pkill -9 -f "python main.py"
sleep 2

# Unset any existing embedding environment variables
unset EMBEDDING_PROVIDER
unset EMBEDDING_MODEL
unset EMBEDDING_DIMENSION
unset GOOGLE_API_KEY

# Export Ollama configuration explicitly
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=bge-m3
export EMBEDDING_DIMENSION=1024
export OLLAMA_BASE_URL=http://ollama.changpt.org
export OLLAMA_API_KEY=ddm_api_key
export OLLAMA_MAX_WORKERS=1

# Also set LLM provider to Google (from .env)
export LLM_PROVIDER=google
export LLM_MODEL=gemini-2.5-flash-lite
export GOOGLE_API_KEY=AIzaSyAIpkHecQ6rIHGz96z3U6qWIjFExjopvp0

# Print configuration
echo "Starting server with configuration:"
echo "  EMBEDDING_PROVIDER: $EMBEDDING_PROVIDER"
echo "  EMBEDDING_MODEL: $EMBEDDING_MODEL"
echo "  EMBEDDING_DIMENSION: $EMBEDDING_DIMENSION"
echo "  OLLAMA_BASE_URL: $OLLAMA_BASE_URL"
echo "  OLLAMA_MAX_WORKERS: $OLLAMA_MAX_WORKERS"
echo ""

# Activate virtual environment and start server
cd /home/chiweic/repo/rag_08122025
source venv/bin/activate
python main.py > ollama_server.log 2>&1 &

# Wait for server to start
sleep 8

# Check server status
echo "Checking server status..."
curl -s http://localhost:8000/health | jq .

# Show initial log
echo ""
echo "Server log:"
tail -30 ollama_server.log | grep -E "(Ollama|worker|dimension|provider|Started)"
