import logging
import os
import sys

from django.apps import AppConfig


LOGGER = logging.getLogger(__name__)
_SCHEDULER_STARTED = False


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'

    def ready(self):
        import attendance.signals

        global _SCHEDULER_STARTED
        if _SCHEDULER_STARTED:
            return

        if os.getenv("ENABLE_AUTO_ABSENT_SCHEDULER", "true").lower() != "true":
            return

        if "runserver" not in sys.argv:
            return

        # Django autoreload bootstraps twice; start scheduler only in the reloader child.
        if os.environ.get("RUN_MAIN") != "true":
            return

        try:
            from attendance.scheduler import start as start_scheduler

            start_scheduler()
            _SCHEDULER_STARTED = True
        except Exception:
            LOGGER.exception("Failed to start attendance auto-absent scheduler.")
