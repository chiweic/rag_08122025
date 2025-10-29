#!/bin/bash
tail -100 ollama_server.log | grep -E "(batch|Embedded|ERROR|success)" | tail -5
echo ""
echo "Last updated: $(date +%H:%M:%S)"
