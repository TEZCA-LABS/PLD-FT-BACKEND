from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.task_routes = {
    "app.services.etl.tasks.*": {"queue": "main-queue"},
    "app.tasks.sanctions_tasks.*": {"queue": "main-queue"},
}

# Import tasks to ensure registration
import app.tasks.sanctions_tasks

celery_app.conf.beat_schedule = {
    "sync-un-sanctions-monthly": {
        "task": "sync_un_sanctions_task",
        "schedule": crontab(day_of_month="1", hour=0, minute=0), # Run at midnight on the 1st of every month
    },
    "sync-mex-sanctions-monthly": {
        "task": "sync_mex_sanctions_task",
        "schedule": crontab(day_of_month="1", hour=0, minute=30), # Run at 00:30 on the 1st of every month
    },
    "sync-sat-sanctions-monthly": {
        "task": "sync_sat_sanctions_task",
        "schedule": crontab(day_of_month="1", hour=1, minute=0), # Run at 01:00 on the 1st of every month
    },
}
