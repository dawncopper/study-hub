"""每日打卡路由（F1，文档 5.3）。"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .auth import get_current_parent
from .common import add_points, get_config_value, get_student
from .database import get_db
from .models import DailyRecord, Parent, Subject
from .report import CATEGORY_LABELS

router = APIRouter(prefix="/daily", tags=["daily"])

CATEGORIES = ["homework", "preview", "extra"]


def calc_points(db: Session, category: str, status: str, quality: int) -> int:
    """积分计算逻辑（文档 5.3）。"""
    value = 0
    if status == "done":
        key = {
            "homework": "points_homework",
            "preview": "points_preview",
            "extra": "points_extra",
        }[category]
        value = get_config_value(db, key, 0)
        if category == "homework" and quality >= 5:
            value += get_config_value(db, "points_quality", 0)
    elif status == "partial":
        value = -abs(get_config_value(db, "deduct_partial", 0))
    elif status == "undone":
        value = -abs(get_config_value(db, "deduct_undone", 0))
    return value


def points_reason(category: str, subject_name: str, status: str, quality: int) -> str:
    cat = CATEGORY_LABELS.get(category, category)
    if status == "done":
        r = f"完成{cat}·{subject_name}"
        if category == "homework" and quality >= 5:
            r += "（含质量奖励）"
        return r
    if status == "partial":
        return f"部分完成{cat}·{subject_name}"
    return f"未完成{cat}·{subject_name}"


def _parse_date(s: str | None) -> date:
    if s:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


@router.get("/")
def daily_page(
    request: Request,
    d: str | None = None,
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    current = _parse_date(d)
    subjects = db.query(Subject).order_by(Subject.sort_order).all()

    groups = {}
    for cat in CATEGORIES:
        records = (
            db.query(DailyRecord)
            .filter_by(record_date=current, category=cat)
            .order_by(DailyRecord.subject_id)
            .all()
        )
        groups[cat] = {
            "label": CATEGORY_LABELS[cat],
            "records": records,
        }

    return request.app.state.templates.TemplateResponse(
        request,
        "daily.html",
        {
            "parent": parent,
            "student": student,
            "subjects": subjects,
            "groups": groups,
            "current": current,
            "today": date.today(),
            "prev_day": current - __import__("datetime").timedelta(days=1),
            "next_day": current + __import__("datetime").timedelta(days=1),
            "msg": msg,
            "error": error,
            "active_nav": "daily",
        },
    )


@router.post("/add")
def daily_add(
    request: Request,
    d: str = Form(""),
    category: str = Form(...),
    subject_id: int = Form(...),
    content: str = Form(""),
    status: str = Form("done"),
    quality: int = Form(0),
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    current = _parse_date(d)
    subject = db.query(Subject).get(subject_id)

    if category not in CATEGORIES or subject is None:
        return RedirectResponse(
            url=f"/daily/?d={current.isoformat()}&error=参数不正确", status_code=303
        )

    quality = max(0, min(5, quality or 0))
    new_points = calc_points(db, category, status, quality)
    reason = points_reason(category, subject.name, status, quality)

    existing = (
        db.query(DailyRecord)
        .filter_by(record_date=current, category=category, subject_id=subject_id)
        .first()
    )

    if existing:
        # 更新：先回滚旧积分，再发放新积分
        if existing.points_granted:
            add_points(
                db,
                student.id,
                -existing.points_granted,
                "adjust",
                f"更新打卡记录回滚积分（{reason}）",
                ref_id=existing.id,
                parent_id=parent.id,
            )
        existing.content = content
        existing.status = status
        existing.quality = quality
        existing.parent_id = parent.id
        existing.points_granted = new_points
        if new_points:
            add_points(
                db,
                student.id,
                new_points,
                "task" if new_points > 0 else "deduct",
                reason,
                ref_id=existing.id,
                parent_id=parent.id,
            )
        db.commit()
        return RedirectResponse(
            url=f"/daily/?d={current.isoformat()}&msg=已更新打卡记录", status_code=303
        )

    record = DailyRecord(
        record_date=current,
        student_id=student.id,
        category=category,
        subject_id=subject_id,
        content=content,
        status=status,
        quality=quality,
        parent_id=parent.id,
        points_granted=new_points,
    )
    db.add(record)
    db.flush()
    if new_points:
        add_points(
            db,
            student.id,
            new_points,
            "task" if new_points > 0 else "deduct",
            reason,
            ref_id=record.id,
            parent_id=parent.id,
        )
    db.commit()
    return RedirectResponse(
        url=f"/daily/?d={current.isoformat()}&msg=打卡已保存", status_code=303
    )


@router.post("/delete/{record_id}")
def daily_delete(
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    record = db.query(DailyRecord).get(record_id)
    if record is None:
        return RedirectResponse(url="/daily/?error=记录不存在", status_code=303)
    current = record.record_date
    if record.points_granted:
        add_points(
            db,
            student.id,
            -record.points_granted,
            "adjust",
            "删除打卡记录回滚积分",
            ref_id=record.id,
            parent_id=parent.id,
        )
    db.delete(record)
    db.commit()
    return RedirectResponse(
        url=f"/daily/?d={current.isoformat()}&msg=打卡记录已删除", status_code=303
    )
