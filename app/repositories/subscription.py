from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import joinedload

from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def get(self, obj_id: int) -> Subscription | None:
        """Получить подписку с загруженным пользователем (для уведомлений)."""
        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.user))
            .where(Subscription.id == obj_id)
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> list[Subscription]:
        """
        Получить список подписок пользователя.
        Исключает архивные подписки, чтобы они не светились в общем списке.
        """
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.is_active,
                Subscription.status != SubscriptionStatus.ARCHIVED,
            )
            .order_by(Subscription.created_at.desc())
        )
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
        self, price_check_interval: int, current_time: datetime
    ) -> list[Subscription]:
        """
        Получить подписки, готовые к проверке.

        Возвращает подписки, у которых:
        1. Статус IDLE или FAILED
        2. Прошло больше price_check_interval секунд с последней проверки
           ИЛИ никогда не проверялись (last_check_at IS NULL)
        """
        threshold = current_time - timedelta(seconds=price_check_interval)
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

    async def mark_last_check_now(
        self, subscription_id: int, check_time: datetime | None = None
    ) -> None:
        """Обновить last_check_at (вызывается при создании задачи)."""
        if check_time is None:
            check_time = datetime.now(UTC)

        await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(last_check_at=check_time)
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

    async def mark_alert_sent(self, subscription_id: int) -> None:
        """Отметить что уведомление отправлено."""
        await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(
                alert_sent=True,
                last_alert_at=datetime.now(UTC),
            )
        )

    async def reset_alert_status(self, subscription_id: int) -> None:
        """Сбросить статус уведомления (alert_sent и last_alert_at)."""
        await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(alert_sent=False, last_alert_at=None)
        )

    async def mark_last_check_now_bulk(
        self, subscription_ids: list[int], check_time: datetime
    ) -> None:
        """Массовое обновление last_check_at для оптимизации N+1."""
        if not subscription_ids:
            return
        await self.session.execute(
            update(Subscription)
            .where(Subscription.id.in_(subscription_ids))
            .values(last_check_at=check_time)
        )

    async def get_archived_by_user_id(self, user_id: int) -> list[Subscription]:
        """Получить архивные подписки пользователя."""
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ARCHIVED,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def reactivate(self, subscription_id: int, user_id: int) -> bool:
        """Реактивировать архивную подписку."""
        result = await self.session.execute(
            update(Subscription)
            .where(
                Subscription.id == subscription_id,
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ARCHIVED,
            )
            .values(
                status=SubscriptionStatus.IDLE, is_active=True, consecutive_errors=0
            )
        )
        return result.rowcount > 0
