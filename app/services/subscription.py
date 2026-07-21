from decimal import Decimal

from app.core.cache import CacheService
from app.models.subscription import Subscription
from app.repositories.subscription import SubscriptionRepository
from app.workers.celery_app import celery_app


class SubscriptionService:
    """Сервис для управления подписками и их жизненным циклом."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        cache: CacheService | None = None,
    ):
        self._subscription_repository = subscription_repository
        self._cache = cache

    async def create_subscription(
        self,
        user_id: int,
        marketplace: str,
        product_url: str,
        target_price: float | None = None,
    ) -> Subscription:
        """Создает новую подписку и немедленно запускает задачу парсинга."""
        subscription = await self._subscription_repository.create(
            user_id=user_id,
            marketplace=marketplace,
            product_url=product_url,
            target_price=target_price,
        )
        await self._subscription_repository.session.commit()

        celery_app.send_task("pricepulse.parse_price", args=[subscription.id])

        if self._cache:
            await self._cache.delete(f"subs:user:{user_id}")
        return subscription

    async def get_user_subscriptions(self, user_id: int) -> list[Subscription]:
        """Возвращает список активных подписок пользователя."""
        return await self._subscription_repository.get_by_user_id(user_id)

    async def get_subscription(self, subscription_id: int) -> Subscription | None:
        """Возвращает подписку по идентификатору."""
        return await self._subscription_repository.get(subscription_id)

    async def delete_subscription(self, subscription_id: int, user_id: int) -> bool:
        """Удаляет подписку пользователя и инвалидирует кэш."""
        deleted = await self._subscription_repository.delete_by_user(
            subscription_id, user_id
        )
        if deleted:
            await self._subscription_repository.session.commit()
            if self._cache:
                await self._cache.delete(f"subs:user:{user_id}")
                await self._cache.delete(f"prices:history:{subscription_id}")
        return deleted

    async def update_target_price(
        self, subscription_id: int, user_id: int, target_price: Decimal | None
    ) -> Subscription | None:
        """Обновляет целевую цену и сбрасывает флаг отправленного уведомления."""
        subscription = await self._subscription_repository.get(subscription_id)
        if not subscription or subscription.user_id != user_id:
            return None

        subscription.target_price = target_price
        if target_price is not None:
            await self._subscription_repository.reset_alert_sent(subscription_id)

        await self._subscription_repository.session.commit()

        if self._cache:
            await self._cache.delete(f"subs:user:{user_id}")
        return subscription

    async def mark_alert_sent(self, subscription_id: int) -> None:
        """Помечает уведомление о достижении цены как отправленное."""
        await self._subscription_repository.mark_alert_sent(subscription_id)

    async def get_archived_subscriptions(self, user_id: int) -> list[Subscription]:
        """Возвращает список архивных подписок пользователя."""
        return await self._subscription_repository.get_archived_by_user_id(user_id)

    async def reactivate_subscription(self, subscription_id: int, user_id: int) -> bool:
        """Реактивирует архивную подписку и запускает задачу парсинга."""
        reactivated = await self._subscription_repository.reactivate(
            subscription_id, user_id
        )
        if reactivated:
            await self._subscription_repository.session.commit()

            celery_app.send_task("pricepulse.parse_price", args=[subscription_id])

            if self._cache:
                await self._cache.delete(f"subs:user:{user_id}")
                await self._cache.delete(f"subs:archived:{user_id}")
        return reactivated

    async def update_cooldown(
        self, subscription_id: int, user_id: int, cooldown_hours: int
    ) -> Subscription | None:
        """Обновляет период задержки уведомлений для подписки."""
        subscription = await self._subscription_repository.get(subscription_id)
        if not subscription or subscription.user_id != user_id:
            return None

        subscription.cooldown_hours = cooldown_hours
        await self._subscription_repository.session.commit()

        if self._cache:
            await self._cache.delete(f"subs:user:{user_id}")
        return subscription
