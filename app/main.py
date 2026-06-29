from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers.health import (
    router as health_router,
)
from app.api.routers.subscription import (
    router as subscription_router,
)
from app.api.routers.user import (
    router as user_router,
)
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.project_name,
    version=settings.project_version,
    lifespan=lifespan,
)

app.include_router(
    health_router,
)

app.include_router(
    subscription_router,
)

app.include_router(
    user_router,
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.project_name,
        "version": settings.project_version,
        "status": "running",
    }
