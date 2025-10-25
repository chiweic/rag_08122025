#!/usr/bin/env python3
"""
Startup script for the localized RAG system
"""
import sys
import os

# Add the localized directory to Python path
localized_path = "/home/chiweic/repo/rag_localized"
sys.path.insert(0, localized_path)

# Change working directory
os.chdir(localized_path)

# Import and run the localized version
import uvicorn
from config import settings

if __name__ == "__main__":
    print("🌍 Starting Localized ChanGPT on port 8002...")
    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=8002,
        reload=False,  # Disable reload to avoid path issues
        log_level="info"
    )