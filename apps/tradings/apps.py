import logging
import os

from django.apps import AppConfig
from django.conf import settings

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

        # Start the scheduler exactly once, in the single serving process.
        # Two valid cases:
        #   - runserver WITH the autoreloader: only the worker child sets
        #     RUN_MAIN=true; the reloader parent doesn't — skip the parent so we
        #     don't get two schedulers (the parent's shutdown also races the
        #     child's thread pool, which surfaced as "cannot schedule new futures
        #     after shutdown" churn).
        #   - runserver WITH --noreload: a single process, no RUN_MAIN is set at
        #     all — start here. (We run --noreload in Docker for exactly this: a
        #     scheduler-driven bot doesn't want the reloader restarting it.)
        is_reloader_child = os.environ.get("RUN_MAIN") == "true"
        is_noreload_server = "runserver" in sys.argv and "--noreload" in sys.argv
        if not (is_reloader_child or is_noreload_server):
            logger.info("⏭️  Skipping scheduler initialization (not the serving process)")
            return

        # Dynamic cadence: the scheduler fires once immediately and each run
        # self-schedules the next one at the agent-chosen (clamped) delay.
        from apps.tradings.scheduler import scheduler, start_event_listener, start_scheduler, stop_event_listener

        start_scheduler()
        logger.info("✅ APScheduler started - trading workflow self-schedules each run")

        # Event-driven wake-ups: Binance fills (entry / stop-loss / take-profit)
        # trigger an immediate run instead of waiting for the next timer.
        start_event_listener()

        # Shutdown on exit
        import atexit

        atexit.register(stop_event_listener)
        atexit.register(lambda: scheduler.shutdown())
