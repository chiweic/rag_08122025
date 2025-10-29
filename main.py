#!/usr/bin/env python3
"""
Main entry point for the DDM RAG System.
"""

import uvicorn
import logging
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,  # Disabled reload to ensure clean .env loading
        log_level="info"
    )