from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def create_worker_engine():
    """Создать async engine для Celery worker."""
    return create_async_engine(settings.postgres_url, echo=False, pool_pre_ping=True)


def create_worker_session_factory(engine):
    """Создать session factory для Celery worker."""
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
