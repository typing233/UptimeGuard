from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.database import SessionLocal, Monitor
from app.checker import run_check

scheduler = AsyncIOScheduler()


def get_job_id(monitor_id: int) -> str:
    return f"monitor_{monitor_id}"


async def schedule_monitor(monitor_id: int, interval: int):
    job_id = get_job_id(monitor_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        run_check,
        trigger=IntervalTrigger(seconds=interval),
        id=job_id,
        args=[monitor_id],
        replace_existing=True,
        max_instances=1,
    )


async def unschedule_monitor(monitor_id: int):
    job_id = get_job_id(monitor_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


async def init_scheduler():
    db = SessionLocal()
    try:
        monitors = db.query(Monitor).filter(Monitor.active == True).all()
        for monitor in monitors:
            await schedule_monitor(monitor.id, monitor.interval)
    finally:
        db.close()

    if not scheduler.running:
        scheduler.start()
