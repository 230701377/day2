"""Celery application for background processing (AI analysis, notifications).

The system is fully functional without Celery (analysis runs synchronously
via the /ai/analyze endpoint), but Celery is used when REDIS_URL is
configured to run long tasks asynchronously and schedule renewal/overdue
notifications.
"""
import os

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "contracts",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="contracts",
    timezone="UTC",
)

celery_app.conf.beat_schedule = {
    "renewal-sweep-daily": {
        "task": "app.workers.tasks.renewal_sweep",
        "schedule": crontab(hour=7, minute=0),
    },
    "approval-overdue-sweep-hourly": {
        "task": "app.workers.tasks.approval_overdue_sweep",
        "schedule": crontab(minute=0),
    },
}
