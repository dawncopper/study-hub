"""StudyHub 学习小站 - FastAPI 主入口。

启动：uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import os
from datetime import date, timedelta

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import scheduler
from .auth import (
    create_session,
    destroy_session,
    get_current_parent,
    get_parent_id,
    verify_password,
)
from .common import (
    check_badges,
    get_config_value,
    get_points_balance,
    get_settings_dict,
    get_student,
)
from .database import Base, SessionLocal, engine, get_db
from .models import (
    DailyRecord,
    Difficulty,
    ErrorItem,
    GameTimeOrder,
    Parent,
    PointTransaction,
    Subject,
)
from .report import CATEGORY_LABELS, CATEGORY_ICONS
from .routes_daily import router as daily_router
from .routes_difficulty import router as difficulty_router
from .routes_errorbook import router as errorbook_router
from .routes_rewards import router as rewards_router
from .routes_settings import router as settings_router
from .routes_stats import router as stats_router
from .seed import seed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="StudyHub 学习小站")
app.state.templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

app.include_router(daily_router)
app.include_router(difficulty_router)
app.include_router(errorbook_router)
app.include_router(rewards_router)
app.include_router(stats_router)
app.include_router(settings_router)

# ---------------- 认证 ----------------

@app.get("/login")
def login_page(request: Request, error: str = ""):
    if get_parent_id(request):
        return RedirectResponse("/dashboard", status_code=303)
    return request.app.state.templates.TemplateResponse(
        request, "login.html", {"error": error, "hide_nav": True}
    )


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    parent = db.query(Parent).filter_by(username=username.strip()).first()
    if parent is None or not verify_password(password, parent.password_hash):
        return RedirectResponse(
            url="/login?error=用户名或密码错误", status_code=303
        )
    token = create_session(parent.id)
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("studyhub_sid", token, max_age=7 * 86400, httponly=True, samesite="lax")
    return resp


@app.post("/logout")
def logout_submit(request: Request):
    destroy_session(get_parent_id(request))
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("studyhub_sid")
    return resp


# ---------------- 页面 ----------------

@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    if get_parent_id(request):
        return RedirectResponse("/dashboard", status_code=303)
    return RedirectResponse("/login", status_code=303)


@app.get("/dashboard")
def dashboard(
    request: Request,
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    today = date.today()

    # 新勋章检查
    new_badges = check_badges(db, student.id)
    db.commit()
    if new_badges and not msg:
        msg = f"🎉 获得新勋章：{'、'.join(b.name for b in new_badges)}"

    balance = get_points_balance(db, student.id)
    exchange_rule = get_config_value(db, "exchange_points", 3)

    # 今日打卡（按科目 × 类别矩阵）
    subjects = db.query(Subject).order_by(Subject.sort_order).all()
    records = (
        db.query(DailyRecord)
        .filter_by(record_date=today, student_id=student.id)
        .all()
    )
    record_map = {
        (r.subject_id, r.category): r for r in records
    }
    matrix = []
    for s in subjects:
        row = {"subject": s, "cells": {}}
        for cat in ("homework", "preview", "extra"):
            row["cells"][cat] = record_map.get((s.id, cat))
        matrix.append(row)

    # 今日完成数 / 未完成提醒
    done_count = sum(1 for r in records if r.status == "done")
    undone = [r for r in records if r.status != "done"]

    # 进行中难点 / 待订正错题
    open_difficulties = (
        db.query(Difficulty)
        .filter_by(student_id=student.id, status="open")
        .order_by(Difficulty.created_at.desc())
        .limit(5)
        .all()
    )
    pending_errors = (
        db.query(ErrorItem)
        .filter(ErrorItem.student_id == student.id, ErrorItem.status != "mastered")
        .order_by(ErrorItem.created_at.desc())
        .limit(5)
        .all()
    )

    # 最近流水
    transactions = (
        db.query(PointTransaction)
        .filter_by(student_id=student.id)
        .order_by(PointTransaction.created_at.desc())
        .limit(10)
        .all()
    )

    # 待使用游戏时间
    pending_minutes = (
        db.query(GameTimeOrder)
        .filter_by(student_id=student.id, status="approved")
        .all()
    )
    pending_game = sum(o.minutes for o in pending_minutes)

    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "parent": parent,
            "student": student,
            "balance": balance,
            "exchange_rule": exchange_rule,
            "matrix": matrix,
            "records": records,
            "done_count": done_count,
            "undone": undone,
            "open_difficulties": open_difficulties,
            "pending_errors": pending_errors,
            "transactions": transactions,
            "pending_game": pending_game,
            "today": today,
            "categories": [
                {"key": "homework", "label": CATEGORY_LABELS["homework"], "icon": CATEGORY_ICONS["homework"]},
                {"key": "preview", "label": CATEGORY_LABELS["preview"], "icon": CATEGORY_ICONS["preview"]},
                {"key": "extra", "label": CATEGORY_LABELS["extra"], "icon": CATEGORY_ICONS["extra"]},
            ],
            "msg": msg,
            "error": error,
            "active_nav": "dashboard",
        },
    )


@app.get("/kid")
def kid_page(request: Request, db: Session = Depends(get_db)):
    """儿童端：公开页面，无需登录（孩子不操作账号，由家长投屏展示）。"""
    student = get_student(db)
    balance = get_points_balance(db, student.id)
    exchange_rule = get_config_value(db, "exchange_points", 3)

    today = date.today()
    done_count = (
        db.query(DailyRecord)
        .filter_by(record_date=today, student_id=student.id, status="done")
        .count()
    )
    total_count = (
        db.query(DailyRecord).filter_by(record_date=today, student_id=student.id).count()
    )

    # 勋章（含未获得灰态）
    from .common import BADGE_DEFS
    from .models import Badge

    earned_keys = {
        b.badge_key
        for b in db.query(Badge).filter_by(student_id=student.id).all()
    }
    badges = [
        {"key": k, "name": n, "icon": i, "earned": k in earned_keys}
        for k, n, i in BADGE_DEFS
    ]

    level = balance // 100 + 1
    progress = balance % 100
    tree_emoji = "🌳" if level >= 20 else "🌲" if level >= 10 else "🌿" if level >= 5 else "🌱"

    # 最近奖励流水（正数）
    recent = (
        db.query(PointTransaction)
        .filter(PointTransaction.student_id == student.id, PointTransaction.amount > 0)
        .order_by(PointTransaction.created_at.desc())
        .limit(5)
        .all()
    )

    settings_notice = get_config_value(db, "school_notice", "")

    return request.app.state.templates.TemplateResponse(
        request,
        "kid.html",
        {
            "student": student,
            "balance": balance,
            "exchange_rule": exchange_rule,
            "done_count": done_count,
            "total_count": total_count,
            "badges": badges,
            "level": level,
            "progress": progress,
            "tree_emoji": tree_emoji,
            "recent": recent,
            "today": today,
            "settings_notice": settings_notice,
            "hide_nav": True,
        },
    )


# ---------------- 启动初始化 ----------------

def _migrate_errorbook_ocr_source():
    """旧库兼容：为 error_items 表补充 ocr_source 列（SQLite，新库由 create_all 直接创建）。"""
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(error_items)"))]
            if cols and "ocr_source" not in cols:
                conn.execute(
                    text("ALTER TABLE error_items ADD COLUMN ocr_source VARCHAR(20) DEFAULT 'tesseract'")
                )
                conn.commit()
    except Exception:  # noqa: BLE001
        pass


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    _migrate_errorbook_ocr_source()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    scheduler.start()
    db = SessionLocal()
    try:
        settings = get_settings_dict(db)
    finally:
        db.close()
    scheduler.reschedule(
        settings.get("reminder_time", "19:00"),
        enabled=settings.get("reminder_enabled", "1") == "1",
    )
