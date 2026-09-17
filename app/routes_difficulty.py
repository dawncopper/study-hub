"""难点疑点路由（F2，文档 5.4）。"""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .auth import get_current_parent
from .common import add_points, get_config_value, get_student
from .database import get_db
from .models import Difficulty, Subject

router = APIRouter(prefix="/difficulty", tags=["difficulty"])


@router.get("/")
def difficulty_page(
    request: Request,
    status: str = "",
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    subjects = db.query(Subject).order_by(Subject.sort_order).all()

    q = db.query(Difficulty).filter_by(student_id=student.id)
    if status in ("open", "solved"):
        q = q.filter_by(status=status)
    items = q.order_by(Difficulty.created_at.desc()).all()

    return request.app.state.templates.TemplateResponse(
        request,
        "difficulty.html",
        {
            "parent": parent,
            "student": student,
            "subjects": subjects,
            "items": items,
            "filter_status": status,
            "msg": msg,
            "error": error,
            "active_nav": "difficulty",
        },
    )


@router.post("/add")
def difficulty_add(
    request: Request,
    subject_id: int = Form(...),
    title: str = Form(...),
    content: str = Form(""),
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    title = title.strip()
    if not title:
        return RedirectResponse(url="/difficulty/?error=标题不能为空", status_code=303)
    item = Difficulty(
        student_id=student.id,
        subject_id=subject_id,
        title=title[:200],
        content=content,
        parent_id=parent.id,
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url="/difficulty/?msg=难点已记录", status_code=303)


@router.post("/solve/{item_id}")
def difficulty_solve(
    item_id: int,
    request: Request,
    solution: str = Form(""),
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    item = db.query(Difficulty).get(item_id)
    if item is None:
        return RedirectResponse(url="/difficulty/?error=记录不存在", status_code=303)
    if item.status == "open":
        item.status = "solved"
        item.solution = solution
        item.solved_at = datetime.now()
        item.parent_id = parent.id
        points = get_config_value(db, "points_difficulty", 15)
        if points:
            add_points(
                db,
                student.id,
                points,
                "task",
                f"解决难点：{item.title[:50]}",
                ref_id=item.id,
                parent_id=parent.id,
            )
        db.commit()
        return RedirectResponse(
            url="/difficulty/?status=solved&msg=难点已解决，+15 星已入账", status_code=303
        )
    db.commit()
    return RedirectResponse(url="/difficulty/?error=该难点已解决", status_code=303)


@router.post("/reopen/{item_id}")
def difficulty_reopen(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    item = db.query(Difficulty).get(item_id)
    if item is None:
        return RedirectResponse(url="/difficulty/?error=记录不存在", status_code=303)
    item.status = "open"
    item.solved_at = None
    db.commit()
    return RedirectResponse(url="/difficulty/?msg=难点已重新打开", status_code=303)


@router.post("/delete/{item_id}")
def difficulty_delete(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    item = db.query(Difficulty).get(item_id)
    if item is None:
        return RedirectResponse(url="/difficulty/?error=记录不存在", status_code=303)
    db.delete(item)
    db.commit()
    return RedirectResponse(url="/difficulty/?msg=难点已删除", status_code=303)
