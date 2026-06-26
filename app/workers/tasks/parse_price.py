from app.core.celery import celery_app


@celery_app.task(
    name="pricepulse.parse_price",
)
def parse_price(
    subscription_id: int,
) -> None:
    print(
        f"Parse subscription {subscription_id}",
    )
