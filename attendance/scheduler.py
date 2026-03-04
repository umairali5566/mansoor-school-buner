from apscheduler.schedulers.background import BackgroundScheduler
from .auto_absent import mark_auto_absent


def start():

    scheduler = BackgroundScheduler()

    # run daily at 10:01 AM
    scheduler.add_job(
        mark_auto_absent,
        'cron',
        hour=10,
        minute=1
    )

    scheduler.start()