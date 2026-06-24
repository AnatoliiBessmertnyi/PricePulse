from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.project_name,
    version=settings.project_version,
    lifespan=lifespan,
)

@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.project_name,
        "version": settings.project_version,
        "status": "running",
    }

@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
