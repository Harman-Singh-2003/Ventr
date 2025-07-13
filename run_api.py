#!/usr/bin/env python3
"""
Startup script for the Crime-Aware Routing API server.

This script starts the FastAPI server with proper configuration and
ensures the network cache is available for optimal performance.
"""

import os
import sys
import uvicorn
import argparse
import logging
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from crime_aware_routing_2.mapping.network.network_cache import ensure_toronto_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Start the FastAPI server."""
    parser = argparse.ArgumentParser(description="Crime-Aware Routing API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"], 
                       help="Log level")
    parser.add_argument("--skip-cache", action="store_true", 
                       help="Skip network cache initialization (faster startup for development)")
    
    args = parser.parse_args()
    
    print("🚀 Starting Crime-Aware Routing API Server")
    print(f"📍 URL: http://{args.host}:{args.port}")
    print(f"📚 Documentation: http://{args.host}:{args.port}/docs")
    print(f"🔍 Health check: http://{args.host}:{args.port}/health")
    print("-" * 50)
    
    # Ensure we're in the right directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Initialize network cache if not skipped
    if not args.skip_cache:
        print("🗺️  Initializing network cache...")
        try:
            cache_ready = ensure_toronto_cache()
            if cache_ready:
                print("✅ Network cache ready - routes will use cached data for better performance")
            else:
                print("⚠️  Network cache initialization failed - routes will use direct downloads")
        except Exception as e:
            print(f"⚠️  Network cache error: {e}")
            print("   Routes will still work but may be slower")
    else:
        print("⏭️  Skipping network cache initialization")
    
    print("-" * 50)
    
    # Start the server
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=args.reload,
        log_level=args.log_level,
        access_log=True
    )

if __name__ == "__main__":
    main() 