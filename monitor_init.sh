#!/bin/bash
# Monitor Ollama initialization progress

echo "Monitoring Ollama Initialization Progress"
echo "=========================================="
echo ""

while true; do
    clear
    echo "Monitoring Ollama Initialization Progress"
    echo "=========================================="
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Check server health
    echo "Server Status:"
    curl -s http://localhost:8000/health | jq '.' 2>/dev/null || echo "  Server not responding"
    echo ""

    # Check collection info
    echo "Collection Status:"
    curl -s http://localhost:6333/collections/ddm_rag 2>/dev/null | jq '.result | {points_count, vectors_count, status, config: .config.params.vectors}' 2>/dev/null || echo "  Qdrant not responding"
    echo ""

    # Check latest log entries
    echo "Latest Progress:"
    tail -30 ollama_clean.log 2>/dev/null | grep -E "(batch|Batch|complete|recommender|success)" | tail -10
    echo ""

    echo "Press Ctrl+C to stop monitoring"
    echo "Refreshing in 10 seconds..."
    sleep 10
done
