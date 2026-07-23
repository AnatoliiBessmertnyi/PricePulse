from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.subscription import Subscription
from app.services.notification import NotificationService


@pytest.fixture
def mock_subscription() -> Subscription:
    """Фикстура базовой подписки для тестов."""
    return Subscription(
        id=1,
        user_id=1,
        product_url="https://example.com/product",
        product_name="Test Product",
        current_price=Decimal("1000.00"),
        target_price=Decimal("900.00"),
        alert_sent=False,
        cooldown_hours=24,
        last_alert_at=None,
    )


def test_should_send_alert_first_time(mock_subscription: Subscription) -> None:
    """Уведомление должно отправляться при первом достижении цели."""
    service = NotificationService()
    assert service.should_send_alert(mock_subscription, Decimal("900.00")) is True


def test_should_send_alert_respects_cooldown(mock_subscription: Subscription) -> None:
    """Уведомление не должно отправляться, если не прошел cooldown."""
    mock_subscription.alert_sent = True
    mock_subscription.last_alert_at = datetime.now(UTC) - timedelta(hours=12)

    service = NotificationService()
    assert service.should_send_alert(mock_subscription, Decimal("850.00")) is False


def test_should_send_alert_after_cooldown(mock_subscription: Subscription) -> None:
    """Уведомление должно отправляться после истечения cooldown."""
    mock_subscription.alert_sent = True
    mock_subscription.last_alert_at = datetime.now(UTC) - timedelta(hours=25)

    service = NotificationService()
    assert service.should_send_alert(mock_subscription, Decimal("850.00")) is True
