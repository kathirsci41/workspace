import logging

from celery import Celery
from celery.signals import task_failure, task_retry, after_setup_logger
from app.config import settings
from app.logging_config import setup_logging

setup_logging("celery")

_logger = logging.getLogger("app.services.extraction.tasks")


@after_setup_logger.connect
def suppress_celery_timer_spam(logger, **kwargs):
    """Runs after Celery's own logging init — overrides survive the --loglevel flag."""
    logging.getLogger("celery.worker").setLevel(logging.WARNING)
    logging.getLogger("celery.utils.timer2").setLevel(logging.WARNING)
    logging.getLogger("celery.utils.functional").setLevel(logging.WARNING)


@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    _logger.error(
        "Celery task FAILED | task=%s | task_id=%s | error=%s",
        sender, task_id, exception,
        exc_info=True,
    )


@task_retry.connect
def on_task_retry(sender=None, reason=None, **kwargs):
    _logger.warning("Celery task RETRY | task=%s | reason=%s", sender, reason)

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
    "broker_connection_retry_on_startup": True,
})

celery_app.autodiscover_tasks(["app.services.extraction"])
