import asyncio

from redis.asyncio import Redis


async def test_redis_connection():
    """Тест подключения к Redis"""
    print("Testing Redis connection...")

    # Вариант 1: через host/port
    try:
        redis = Redis(
            host="localhost",
            port=6379,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        await redis.ping()
        print("✓ Connected via localhost:6379")
        await redis.close()
    except Exception as e:
        print(f"✗ Failed via localhost:6379: {e}")

    # Вариант 2: через 127.0.0.1
    try:
        redis = Redis(
            host="127.0.0.1",
            port=6379,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        await redis.ping()
        print("✓ Connected via 127.0.0.1:6379")
        await redis.close()
    except Exception as e:
        print(f"✗ Failed via 127.0.0.1:6379: {e}")

    # Вариант 3: через from_url
    try:
        redis = Redis.from_url(
            "redis://localhost:6379/0",
            decode_responses=True,
            socket_connect_timeout=5,
        )
        await redis.ping()
        print("✓ Connected via redis://localhost:6379/0")
        await redis.close()
    except Exception as e:
        print(f"✗ Failed via redis://localhost:6379/0: {e}")


if __name__ == "__main__":
    asyncio.run(test_redis_connection())
