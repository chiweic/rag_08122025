#!/bin/bash
# Start Qdrant using Docker Compose
# Run this script with: bash start_qdrant.sh

echo "Starting Qdrant vector database..."
echo ""

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    echo "Please install Docker first by running: bash install_docker.sh"
    exit 1
fi

# Try without sudo first
if docker compose ps &> /dev/null; then
    echo "Running docker compose without sudo..."
    docker compose up -d
else
    echo "Running docker compose with sudo (password required)..."
    sudo docker compose up -d
fi

echo ""
echo "Checking Qdrant status..."
sleep 3

# Check if container is running
if sudo docker ps | grep -q ddm_rag_qdrant; then
    echo "✓ Qdrant is running!"
    echo ""
    echo "Qdrant endpoints:"
    echo "  - REST API: http://localhost:6333"
    echo "  - Web UI: http://localhost:6333/dashboard"
    echo ""
    echo "Test connectivity:"
    echo "  curl http://localhost:6333/health"
else
    echo "✗ Qdrant failed to start. Checking logs..."
    sudo docker compose logs qdrant
fi
