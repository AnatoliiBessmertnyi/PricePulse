import asyncio
import traceback

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.subscription import Subscription
from app.workers.tasks.parse_price import _parse_price


async def get_first_subscription() -> int | None:
    """Получаем ID первой подписки для тестирования."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Subscription).limit(1),
        )
        subscription = result.scalar_one_or_none()
        return subscription.id if subscription else None


async def main() -> None:
    subscription_id = await get_first_subscription()
    
    if subscription_id is None:
        print("❌ Нет подписок в базе. Создайте подписку через API.")
        return
    
    print(f"✅ Найдена подписка ID: {subscription_id}")
    print(f"🚀 Запускаем задачу парсинга...")
    
    # Вызываем внутреннюю async функцию напрямую (без Celery)
    try:
        await _parse_price(subscription_id)
        print("✅ Задача выполнена")
    except Exception as e:
        print(f"❌ Ошибка выполнения задачи: {e}")
        traceback.print_exc()
    
    # Проверяем результат
    async with async_session_factory() as session:
        from app.models.price_history import PriceHistory
        from app.models.parse_error import ParseError
        
        # Проверяем историю цен
        result = await session.execute(
            select(PriceHistory)
            .where(PriceHistory.subscription_id == subscription_id)
            .order_by(PriceHistory.created_at.desc())
            .limit(1),
        )
        price = result.scalar_one_or_none()
        
        if price:
            print(f"💰 Последняя цена: {price.price} ₽")
        else:
            print("⚠️ Цена не найдена")
        
        # Проверяем ошибки
        result = await session.execute(
            select(ParseError)
            .where(ParseError.subscription_id == subscription_id)
            .order_by(ParseError.created_at.desc())
            .limit(1),
        )
        error = result.scalar_one_or_none()
        
        if error:
            print(f"❌ Последняя ошибка: {error.error_type}: {error.error_message}")


if __name__ == "__main__":
    asyncio.run(main())
