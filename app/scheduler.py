"""APScheduler 定时提醒调度（文档 5.10）。

每日 reminder_time 执行：检查当天是否有未完成打卡记录，有则按已配置渠道推送。
"""
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
_job = None


def _daily_reminder_job() -> None:
    """每日提醒：检查未完成打卡并推送。"""
    from .common import get_settings_dict
    from .database import SessionLocal
    from .models import DailyRecord
    from .notify import build_reminder_text, send_notification
    from .report import CATEGORY_LABELS

    db = SessionLocal()
    try:
        today = date.today()
        records = (
            db.query(DailyRecord)
            .filter(DailyRecord.record_date == today, DailyRecord.status != "done")
            .all()
        )
        if not records:
            return
        settings = get_settings_dict(db)
        has_channel = any(
            settings.get(k)
            for k in (
                "notify_wecom_webhook",
                "notify_wechat_webhook",
                "notify_email_smtp",
            )
        )
        if not has_channel:
            return
        rows = [
            (CATEGORY_LABELS.get(r.category, r.category), r.subject.name if r.subject else "")
            for r in records
        ]
        text = build_reminder_text(rows)
        send_notification(settings, text)
    finally:
        db.close()


def reschedule(reminder_time: str = "19:00", enabled: bool = True) -> None:
    """按设置重排每日提醒任务。"""
    global _job
    if _job is not None:
        try:
            _job.remove()
        except Exception:  # noqa: BLE001
            pass
        _job = None
    if not enabled:
        return
    try:
        hour_s, minute_s = reminder_time.split(":")
        hour = int(hour_s)
        minute = int(minute_s)
    except Exception:  # noqa: BLE001
        hour, minute = 19, 0
    _job = scheduler.add_job(
        _daily_reminder_job, "cron", hour=hour, minute=minute, id="daily_reminder"
    )


def start() -> None:
    if not scheduler.running:
        scheduler.start()
