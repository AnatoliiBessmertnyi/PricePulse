from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, update

from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def get_by_user_id(self, user_id: int) -> list[Subscription]:
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_user(self, subscription_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            delete(Subscription).where(
                Subscription.id == subscription_id, Subscription.user_id == user_id
            )
        )
        return result.rowcount > 0

    async def get_subscriptions_for_check(
        self, price_check_interval: int
    ) -> list[Subscription]:
        """
        Получить подписки, готовые к проверке.

        Возвращает подписки, у которых:
        1. Статус IDLE или FAILED
        2. Прошло больше price_check_interval секунд с последней проверки
           ИЛИ никогда не проверялись (last_check_at IS NULL)
        """
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=price_check_interval)
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.is_active.is_(True),
                Subscription.status.in_(
                    [SubscriptionStatus.IDLE, SubscriptionStatus.FAILED]
                ),
                or_(
                    Subscription.last_check_at.is_(None),
                    Subscription.last_check_at < threshold,
                ),
            )
        )
        return list(result.scalars().all())

    async def mark_last_check_now(self, subscription_id: int) -> None:
        """Обновить last_check_at (вызывается при создании задачи)."""
        await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(last_check_at=datetime.now(UTC))
        )

    async def mark_as_idle(self, subscription_id: int) -> None:
        """Отметить подписку как успешно проверенную."""
        await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(status=SubscriptionStatus.IDLE, last_success_at=datetime.now(UTC))
        )

    async def mark_as_failed(self, subscription_id: int) -> None:
        """Отметить подписку как упавшую с ошибкой."""
        await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(status=SubscriptionStatus.FAILED)
        )

    async def reset_alert_sent(self, subscription_id: int) -> None:
        """Сбросить флаг alert_sent (при изменении target_price)."""
        await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(alert_sent=False)
        )
