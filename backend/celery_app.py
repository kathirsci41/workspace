from celery import Celery
from app.config import settings

celery_app = Celery("docplatform")

celery_app.config_from_object({
    "broker_url": settings.redis_url,
    "result_backend": settings.redis_url,
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "task_soft_time_limit": 600,
    "task_time_limit": 660,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
})

celery_app.autodiscover_tasks(["app.services.extraction"])
