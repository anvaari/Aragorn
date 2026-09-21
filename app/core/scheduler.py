from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import app_settings
from log.logger import get_app_logger
from services.digest_service import send_events_digest

logger = get_app_logger(__name__)

# If the app was down when a slot passed, still send once if it restarts within this window.
_MISFIRE_GRACE_SECONDS = 3600

def _run_digest(day_offset: int) -> None:
    try:
        send_events_digest(day_offset)
    except Exception:
        logger.error(f"Digest job failed (day_offset={day_offset})",exc_info=True)

def build_digest_scheduler() -> BackgroundScheduler | None:
    if not app_settings.digest_enabled:
        logger.info("Digest scheduler disabled (digest_enabled=false)")
        return None

    scheduler = BackgroundScheduler(timezone=app_settings.digest_timezone)
    seen: set[tuple[str, int]] = set()
    for sched in app_settings.digest_schedules:
        key = (sched.time, sched.day_offset)
        if key in seen:
            logger.warning(f"Duplicate digest schedule {key}, skipping")
            continue
        seen.add(key)
        hour, minute = (int(part) for part in sched.time.split(":"))
        scheduler.add_job(
            _run_digest,
            trigger=CronTrigger(hour=hour, minute=minute,
                                timezone=app_settings.digest_timezone),
            args=[sched.day_offset],
            id=f"digest-{sched.time.replace(':', '')}-{sched.day_offset}",
            name=f"telegram digest {sched.time} day_offset={sched.day_offset}",
            misfire_grace_time=_MISFIRE_GRACE_SECONDS,
            coalesce=True,
            replace_existing=True,
        )
    return scheduler

def start_digest_scheduler() -> BackgroundScheduler | None:
    scheduler = build_digest_scheduler()
    if scheduler is not None:
        scheduler.start()
        logger.info(f"Digest scheduler started with {len(scheduler.get_jobs())} job(s)")
    return scheduler

def shutdown_digest_scheduler(scheduler: BackgroundScheduler | None) -> None:
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
