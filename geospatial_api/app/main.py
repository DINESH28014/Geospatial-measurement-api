from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.logging import logger
from app.core.exceptions import GeospatialAPIException
from app.api.routers.files import router as files_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown actions."""
    logger.info("Starting Geospatial File Measurement API...")
    # Initialize DB tables
    await init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down Geospatial File Measurement API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Production-grade FastAPI service for ingesting, parsing, reprojecting, "
        "and measuring geospatial files (KML and Shapefile Zip archives)."
    ),
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
@app.exception_handler(GeospatialAPIException)
async def geospatial_api_exception_handler(request: Request, exc: GeospatialAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "status_code": exc.status_code},
    )


# Include routers
app.include_router(files_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
async def health_check():
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }
