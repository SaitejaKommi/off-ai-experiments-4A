#!/usr/bin/env python3
"""
run_api.py - Start the OFF AI Search API server

Usage:
    python run_api.py

The server will be available at http://localhost:8000
API docs at http://localhost:8000/docs
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.off_ai.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info",
    )
