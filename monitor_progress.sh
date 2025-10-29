#!/bin/bash
echo "=== Monitoring Ollama Initialization Progress ==="
echo "Started at: $(date)"
echo ""

while true; do
    # Get latest batch info
    LAST_BATCH=$(tail -100 ollama_server.log | grep "Processing embedding batch" | tail -1)
    EMBEDDED=$(tail -100 ollama_server.log | grep "Embedded" | tail -1)
    ERRORS=$(tail -100 ollama_server.log | grep -E "(ERROR|timeout|Failed)" | wc -l)
    
    # Check if initialization completed
    SUCCESS=$(tail -50 ollama_server.log | grep "initialized successfully" | wc -l)
    
    clear
    echo "=== Ollama Initialization Progress ==="
    echo "Time: $(date +%H:%M:%S)"
    echo ""
    echo "Last batch: $LAST_BATCH"
    echo "Progress:   $EMBEDDED"
    echo "Errors:     $ERRORS"
    echo ""
    
    if [ "$SUCCESS" -gt 0 ]; then
        echo "✅ INITIALIZATION COMPLETED!"
        tail -20 ollama_server.log | grep -E "(initialized|success|points_count)"
        break
    fi
    
    sleep 30
done
