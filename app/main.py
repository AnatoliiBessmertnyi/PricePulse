"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.logging import RequestLoggingMiddleware
from app.api.routers.health import router as health_router
from app.api.routers.subscription import router as subscription_router
from app.api.routers.user import router as user_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging

setup_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("application_starting", version=settings.project_version)
    yield
    logger.info("application_stopping")


app = FastAPI(
    title=settings.project_name,
    version=settings.project_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Routers
app.include_router(health_router)
app.include_router(subscription_router)
app.include_router(user_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning service information."""
    return {
        "service": settings.project_name,
        "version": settings.project_version,
        "status": "running",
    }
