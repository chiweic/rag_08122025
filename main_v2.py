#!/usr/bin/env python3
"""
Main entry point for Multi-Collection RAG API Server
Uses the new multi-collection architecture with separate text, audio, and event collections
"""

import uvicorn
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Start the Multi-Collection RAG API server"""
    
    # Server configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))  # Use port 8000 (replacing v1)
    reload = os.getenv("RELOAD", "true").lower() == "true"
    
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║         Multi-Collection DDM RAG API Server v2.0            ║
    ║                                                              ║
    ║  Features:                                                   ║
    ║  - Separate collections for text, audio, and events         ║
    ║  - Balanced retrieval (3 text + 1 audio + 1 event)         ║
    ║  - Enhanced metadata preservation                           ║
    ║  - Real audio references from 聖嚴法師                       ║
    ║  - Event recommendations for Buddhist activities            ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    print(f"🚀 Starting server on http://{host}:{port}")
    print(f"📚 API documentation: http://{host}:{port}/docs")
    print(f"🔄 Auto-reload: {'enabled' if reload else 'disabled'}")
    print(f"📁 Working directory: {os.getcwd()}")
    print()
    
    # Run the server
    uvicorn.run(
        "api_v2:app",  # Use the new api_v2 module
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[str(project_root)],
        log_level="info"
    )

if __name__ == "__main__":
    main()