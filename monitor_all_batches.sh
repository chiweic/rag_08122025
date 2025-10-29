#!/bin/bash
echo "=== Ollama Initialization Monitor - Started at $(date +%H:%M:%S) ==="
echo "Total: 22 batches, 1,067 documents"
echo ""

while true; do
  # Count completed batches
  COMPLETED=$(grep -c "Batch .*/22 complete" ollama_server.log)
  
  # Get current batch
  CURRENT_BATCH=$(tail -50 ollama_server.log | grep "Processing embedding batch" | tail -1 | grep -oP "batch \d+/22" || echo "N/A")
  
  # Get current progress within batch
  CURRENT_PROGRESS=$(tail -50 ollama_server.log | grep "Embedded" | tail -1 | grep -oP "\d+/\d+ documents" || echo "N/A")
  
  # Check for completion
  SUCCESS=$(grep -c "initialized successfully" ollama_server.log)
  
  # Check for errors
  ERRORS=$(tail -200 ollama_server.log | grep -c "ERROR")
  
  echo "[$(date +%H:%M:%S)] Completed: $COMPLETED/22 batches | Current: $CURRENT_BATCH ($CURRENT_PROGRESS) | Errors: $ERRORS"
  
  if [ "$SUCCESS" -gt 0 ]; then
    echo ""
    echo "========================================="
    echo "✅ INITIALIZATION COMPLETED!"
    echo "========================================="
    tail -40 ollama_server.log | grep -E "(success|points_count|initialized|recommender)"
    break
  fi
  
  sleep 300  # Check every 5 minutes
done
