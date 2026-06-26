from app.core.celery import celery_app

celery_app.autodiscover_tasks(
    [
        "app.workers.tasks",
    ],
)


__all__ = [
    "celery_app",
]
