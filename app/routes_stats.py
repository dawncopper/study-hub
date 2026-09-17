"""统计报表路由（F6，文档 5.6）。"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .auth import get_current_parent
from .common import get_student
from .database import get_db
from .report import build_report, build_trend

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/")
def stats_page(
    request: Request,
    period: str = "week",
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    if period not in ("week", "month", "7d"):
        period = "week"

    report = build_report(db, student.id, period)
    trend = build_trend(db, student.id, 30)

    return request.app.state.templates.TemplateResponse(
        request,
        "stats.html",
        {
            "parent": parent,
            "student": student,
            "report": report,
            "trend": trend,
            "period": period,
            "msg": msg,
            "error": error,
            "active_nav": "stats",
        },
    )


@router.post("/report")
def stats_report(
    request: Request,
    period: str = Form("week"),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    if period not in ("week", "month", "7d"):
        period = "week"
    return RedirectResponse(url=f"/stats/?period={period}", status_code=303)
