"""
Crime-Aware Routing API - FastAPI Main Application

A RESTful API for calculating crime-aware routes in Toronto using real crime data.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn

from api.routes.routing import router as routing_router
from api.services.routing_service import routing_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle - startup and shutdown events.
    """
    # Startup
    logger.info("Starting Crime-Aware Routing API...")
    
    # Verify routing service is initialized
    health = routing_service.get_health_status()
    if health.crime_data_loaded:
        logger.info(f"✓ Routing service ready with {health.crime_incidents_count} crime incidents")
    else:
        logger.warning("⚠ Routing service running in degraded mode - crime data not loaded")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Crime-Aware Routing API...")


# Create FastAPI application
app = FastAPI(
    title="Crime-Aware Routing API",
    description="""
    **Calculate safer routes using real Toronto crime data**
    
    This API provides crime-aware routing capabilities that help users find routes
    that balance distance efficiency with personal safety. It uses real assault
    incident data from Toronto Police Service to identify safer pathways.
    
    ## Features
    
    - **Crime-Aware Routing**: Routes that avoid high-crime areas
    - **Flexible Weighting**: Adjust balance between distance and safety
    - **Multiple Route Types**: Shortest, safest, or balanced routes
    - **GeoJSON Output**: Standard geographic data format
    - **Route Statistics**: Detailed metrics about safety and distance
    
    ## Coverage Area
    
    Currently supports routing within Toronto, Ontario, Canada.
    
    ## Data Sources
    
    - **Crime Data**: Toronto Police Service Assault Open Data (5,583+ incidents)
    - **Street Network**: OpenStreetMap via OSMnx
    
    ## Quick Start
    
    1. Check service health: `GET /api/routing/health`
    2. Calculate a route: `POST /api/routing/calculate`
    3. View results in GeoJSON format for mapping applications
    """,
    version="1.0.0",
    contact={
        "name": "Crime-Aware Routing API",
        "url": "https://github.com/your-repo/crime-aware-routing",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan
)

# Add CORS middleware for web applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors with detailed information.
    """
    logger.warning(f"Validation error for {request.url}: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "validation_error",
            "message": "Request validation failed",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected errors gracefully.
    """
    logger.error(f"Unexpected error for {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "details": None
        }
    )


# Include routers
app.include_router(routing_router)


@app.get("/", tags=["general"])
async def root():
    """
    API root endpoint with basic information.
    """
    return {
        "api": "Crime-Aware Routing API",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
        "health_check": "/api/routing/health",
        "coverage_area": "Toronto, Ontario, Canada"
    }


@app.get("/health", tags=["general"])
async def api_health():
    """
    Simple health check endpoint.
    """
    try:
        service_health = routing_service.get_health_status()
        return {
            "api_status": "healthy",
            "service_status": service_health.status,
            "timestamp": "2024-01-01T00:00:00Z"  # In production, use real timestamp
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "api_status": "unhealthy",
                "error": str(e),
                "timestamp": "2024-01-01T00:00:00Z"
            }
        )


# Development server configuration
if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    ) 