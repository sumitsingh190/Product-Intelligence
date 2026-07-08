from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "productos_ai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.ingestion_tasks",
        "app.tasks.analysis_tasks",
        "app.tasks.reporting_tasks",
        "app.tasks.embedding_tasks",
    ]
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.ingestion_tasks.*": {"queue": "ingestion"},
        "app.tasks.analysis_tasks.*": {"queue": "analysis"},
        "app.tasks.reporting_tasks.*": {"queue": "reporting"},
        "*": {"queue": "default"},
    },
    beat_schedule={
#Ingest all active data sources every 15 minutes (real-time posture).
# Matches the autonomous-behavior spec: "Every 15 minutes: sync Jira,
#GitHub, support tickets, analytics."
        "ingest-all-sources": {
            "task": "app.tasks.ingestion_tasks.ingest_all_active_sources",
            "schedule": crontab(minute="*/15"),
        },
# Sync PG DuckDB every 15 minutes, offset by 5 min so ingestion has
# a head-start before the analytical mirror runs.

        "etl-sync": {
            "task": "app.tasks.ingestion_tasks.run_etl_sync",
            "schedule": crontab(minute="5,20,35,50"),
        },
#Daily analysis run at 6 AM UTC

        "daily-analysis": {
            "task": "app.tasks.analysis_tasks.run_daily_analysis",
            "schedule": crontab(hour=6, minute=0),
        },
# Weekly executive report on Monday at 7 AM UTC
        "weekly-executive-report": {
            "task": "app.tasks.reporting_tasks.generate_weekly_executive_reports",
            "schedule": crontab(hour=7, minute=0, day_of_week=1),
        },
#Nightly KPI snapshot for trend charts (5 AM UTC, before daily analysis)
        "nightly-kpi-snapshot": {
            "task": "app.tasks.ingestion_tasks.snapshot_all_workspaces",
            "schedule": crontab(hour=5, minute=0),
        },
#Competitor intelligence daily scrape at 4 AM UTC
        "daily-competitor-scrape": {
            "task": "app.tasks.ingestion_tasks.scrape_competitors",
            "schedule": crontab(hour=4, minute=0),
        },
#Anomaly scan every 15 minutes; fires event-driven analysis when signals spike
        "anomaly-scan": {
            "task": "app.tasks.analysis_tasks.scan_all_workspaces_for_anomalies",
            "schedule": crontab(minute="*/15"),
        }, 
#Overnight briefing 08:00 UTC, one Markdown digest per workspace
        "overnight-briefing": {
            "task": "app.tasks.reporting_tasks.generate_overnight_briefings",
            "schedule": crontab(hour=8, minute=0),
        },
    },
)