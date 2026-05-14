import os

from celery import Celery

celery_app = Celery(
    "digidentity",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
)
celery_app.conf.task_always_eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() == "true"
celery_app.conf.task_eager_propagates = True
