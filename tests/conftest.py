"""Common fixtures for PricePulse tests."""

import asyncio
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.base import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with rollback after each test."""
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost:5432/pricepulse_test",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def sample_subscription_data() -> dict[str, Any]:
    """Sample data for creating a subscription."""
    return {
        "user_id": 1,
        "marketplace": "ozon",
        "product_url": "https://www.ozon.ru/product/test-item-1234567890/",
        "target_price": Decimal("999.99"),
    }
