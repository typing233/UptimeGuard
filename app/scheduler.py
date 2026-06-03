import logging
from datetime import datetime, timezone, time as dtime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from .database import async_session
from .models import Monitor, CheckResult, AlertPolicy, AlertChannel, Incident
from .checker import run_check
from .notifier import send_alert, build_context

logger = logging.getLogger("uptimeguard.scheduler")
scheduler = AsyncIOScheduler()


def _in_silence_window(policy: AlertPolicy) -> bool:
    if not policy.silence_start or not policy.silence_end:
        return False
    now = datetime.now(timezone.utc).time()
    start = dtime.fromisoformat(policy.silence_start)
    end = dtime.fromisoformat(policy.silence_end)
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


async def _process_alert(monitor: Monitor, result_status: str, error: str,
                         latency: float, session):
    try:
        stmt = select(AlertPolicy).where(AlertPolicy.monitor_id == monitor.id)
        res = await session.execute(stmt)
        policy = res.scalar_one_or_none()
        if not policy:
            return

        if result_status == "down":
            policy.consecutive_failures += 1

            if policy.consecutive_failures >= policy.failure_threshold:
                if _in_silence_window(policy):
                    return

                should_send = False
                if not policy.alerted:
                    should_send = True
                    policy.alerted = True
                elif policy.repeat_interval > 0 and policy.last_alert_time:
                    elapsed = (datetime.now(timezone.utc) - policy.last_alert_time).total_seconds() / 60
                    if elapsed >= policy.repeat_interval:
                        should_send = True

                if should_send:
                    policy.last_alert_time = datetime.now(timezone.utc)
                    context = build_context(
                        monitor_name=monitor.name, target=monitor.target,
                        status="down", failure_count=policy.consecutive_failures,
                        error=error or "", latency=latency or 0
                    )
                    await _send_to_channels(policy.channel_ids or [], context, session)

        elif result_status == "up" and policy.alerted:
            if policy.recovery_notify:
                context = build_context(
                    monitor_name=monitor.name, target=monitor.target,
                    status="up", failure_count=policy.consecutive_failures,
                    recovery_time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                )
                await _send_to_channels(policy.channel_ids or [], context, session)
            policy.consecutive_failures = 0
            policy.alerted = False
            policy.last_alert_time = None

    except Exception as e:
        logger.error(f"Alert processing failed for monitor {monitor.id}: {e}")


async def _send_to_channels(channel_ids: list, context: dict, session):
    for cid in channel_ids:
        try:
            channel = await session.get(AlertChannel, cid)
            if channel and channel.enabled:
                await send_alert(channel.channel_type, channel.config, context)
        except Exception as e:
            logger.error(f"Failed to send alert to channel {cid}: {e}")


async def _manage_incident(monitor: Monitor, result_status: str, error: str, session):
    try:
        stmt = select(Incident).where(
            Incident.monitor_id == monitor.id,
            Incident.resolved_at.is_(None)
        )
        res = await session.execute(stmt)
        open_incident = res.scalar_one_or_none()

        if result_status == "down" and not open_incident:
            incident = Incident(
                monitor_id=monitor.id,
                started_at=datetime.now(timezone.utc),
                error=error
            )
            session.add(incident)
        elif result_status == "up" and open_incident:
            open_incident.resolved_at = datetime.now(timezone.utc)
    except Exception as e:
        logger.error(f"Incident tracking failed for monitor {monitor.id}: {e}")


async def execute_check(monitor_id: int) -> dict | None:
    async with async_session() as session:
        monitor = await session.get(Monitor, monitor_id)
        if not monitor:
            return None

        result = await run_check(
            monitor_type=monitor.monitor_type,
            target=monitor.target,
            port=monitor.port,
            timeout=monitor.timeout,
            expected_status=monitor.expected_status or 200,
            keyword=monitor.keyword,
            method=monitor.http_method or "GET",
        )

        check_result = CheckResult(
            monitor_id=monitor.id,
            status=result.status,
            latency=result.latency,
            error=result.error,
        )
        session.add(check_result)

        monitor.status = result.status
        monitor.last_check = datetime.now(timezone.utc)

        await _process_alert(monitor, result.status, result.error or "", result.latency or 0, session)
        await _manage_incident(monitor, result.status, result.error or "", session)

        await session.commit()

        return {
            "monitor_id": monitor.id,
            "status": result.status,
            "latency": result.latency,
            "error": result.error,
            "timestamp": monitor.last_check.isoformat(),
        }


def schedule_monitor(monitor_id: int, interval_seconds: int):
    job_id = f"monitor_{monitor_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        execute_check, IntervalTrigger(seconds=interval_seconds),
        id=job_id, args=[monitor_id], replace_existing=True
    )


def unschedule_monitor(monitor_id: int):
    job_id = f"monitor_{monitor_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


async def init_scheduler():
    async with async_session() as session:
        result = await session.execute(select(Monitor).where(Monitor.active == True))
        monitors = result.scalars().all()
        for m in monitors:
            schedule_monitor(m.id, m.interval)
    scheduler.start()
    logger.info(f"Scheduler started with {len(monitors)} monitors")
