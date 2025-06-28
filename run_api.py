#!/usr/bin/env python3
"""
Startup script for the Crime-Aware Routing API server.

This script starts the FastAPI server with proper configuration.
"""

import os
import sys
import uvicorn
import argparse

def main():
    """Start the FastAPI server."""
    parser = argparse.ArgumentParser(description="Crime-Aware Routing API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"], 
                       help="Log level")
    
    args = parser.parse_args()
    
    print("🚀 Starting Crime-Aware Routing API Server")
    print(f"📍 URL: http://{args.host}:{args.port}")
    print(f"📚 Documentation: http://{args.host}:{args.port}/docs")
    print(f"🔍 Health check: http://{args.host}:{args.port}/health")
    print("-" * 50)
    
    # Ensure we're in the right directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Start the server
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        access_log=True
    )

if __name__ == "__main__":
    main() 