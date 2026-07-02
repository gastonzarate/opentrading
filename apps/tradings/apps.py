import logging
import os

from django.apps import AppConfig
from django.conf import settings

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


class TradingsConfig(AppConfig):
    name = "tradings"
    label = "tradings"  # Django uses this as the app label
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """
        Initialize APScheduler when Django starts.

        The scheduler must NEVER start during tests or management commands, and
        only ever runs in the single "main" process of the dev server (Django's
        autoreloader spawns a parent process we must skip). It also stays behind
        the DEBUG flag as before.
        """
        import sys

        # Hard stop under tests / any non-serving management command. Importing
        # Django (e.g. via pytest, migrate, shell) must not launch live trading.
        if getattr(settings, "ENVIRONMENT", None) == "test" or "pytest" in sys.modules:
            return
        if "test" in sys.argv:
            return

        # Keep the scheduler behind DEBUG (production is disabled for now).
        if not settings.DEBUG:
            return

        # Prevent the scheduler from starting twice under the dev-server reloader.
        # The reloader's parent process does not set RUN_MAIN=true; only its
        # worker child does. Skipping the parent avoids duplicate schedulers.
        if os.environ.get("RUN_MAIN") != "true":
            logger.info("⏭️  Skipping scheduler initialization (not in main process)")
            return

        from apps.tradings.scheduler import run_trading_workflow

        scheduler = BackgroundScheduler()

        # Schedule the trading workflow. A single source of truth for the cadence
        # so the scheduler, the log line and the agent prompt cannot drift apart.
        from datetime import datetime, timezone

        from apps.tradings.scheduler import EXECUTION_INTERVAL_MINUTES

        scheduler.add_job(
            run_trading_workflow,
            "interval",
            minutes=EXECUTION_INTERVAL_MINUTES,
            id="trading_futures_workflow",
            name="Trading Futures Workflow",
            replace_existing=True,
            misfire_grace_time=30,  # Allow 30s grace for missed executions
            coalesce=True,  # Combine missed executions into one
            max_instances=1,  # Only one instance at a time
            next_run_time=datetime.now(timezone.utc),  # Execute immediately on startup
        )

        scheduler.start()
        logger.info(f"✅ APScheduler started - Trading workflow will run every {EXECUTION_INTERVAL_MINUTES} minutes")

        # Shutdown scheduler when Django exits
        import atexit

        atexit.register(lambda: scheduler.shutdown())
