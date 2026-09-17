"""错题管理路由（F3，文档 5.5）。"""
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .auth import get_current_parent
from .common import add_points, check_badges, get_config_value, get_settings_dict, get_student
from .database import UPLOAD_DIR, get_db
from .models import ErrorItem, Subject
from .ocr import ocr_image, openrouter_recognize, save_upload
from .report import export_errorbook_pdf

router = APIRouter(prefix="/errorbook", tags=["errorbook"])


def _apply_filters(
    db: Session,
    subject_id: str | None,
    knowledge: str | None,
    tag: str | None,
    status: str | None,
):
    q = db.query(ErrorItem)
    if subject_id and subject_id.isdigit():
        q = q.filter_by(subject_id=int(subject_id))
    if knowledge:
        q = q.filter(ErrorItem.knowledge_point.contains(knowledge))
    if tag:
        q = q.filter(ErrorItem.tags.contains(tag))
    if status in ("pending", "reviewed", "mastered"):
        q = q.filter_by(status=status)
    return q.order_by(ErrorItem.created_at.desc()).limit(200).all()


@router.get("/")
def errorbook_page(
    request: Request,
    subject_id: str = "",
    knowledge: str = "",
    tag: str = "",
    status: str = "",
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    subjects = db.query(Subject).order_by(Subject.sort_order).all()
    items = _apply_filters(db, subject_id or None, knowledge or None, tag or None, status or None)

    settings = get_settings_dict(db)
    ocr_mode = (
        "openrouter"
        if settings.get("openrouter_enabled") == "1" and settings.get("openrouter_api_key")
        else "tesseract"
    )

    return request.app.state.templates.TemplateResponse(
        request,
        "errorbook.html",
        {
            "parent": parent,
            "student": student,
            "subjects": subjects,
            "items": items,
            "filter": {"subject_id": subject_id, "knowledge": knowledge, "tag": tag, "status": status},
            "has_filter": bool(subject_id or knowledge or tag or status),
            "ocr_mode": ocr_mode,
            "msg": msg,
            "error": error,
            "active_nav": "errorbook",
        },
    )


@router.post("/upload")
async def errorbook_upload(
    request: Request,
    subject_id: int = Form(...),
    knowledge_point: str = Form(""),
    tags: str = Form(""),
    error_reason: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)

    if not file or not file.filename:
        return RedirectResponse(url="/errorbook/?error=请选择要上传的图片", status_code=303)

    filename = save_upload(file)
    full_path = os.path.join(UPLOAD_DIR, filename)

    # 识别来源：OpenRouter 视觉 AI 优先（仅当启用且已配置 key），失败/未配置回退 Tesseract
    source = "tesseract"
    question, answer = "", ""
    settings = get_settings_dict(db)
    if settings.get("openrouter_enabled") == "1" and settings.get("openrouter_api_key"):
        result = await run_in_threadpool(
            openrouter_recognize, full_path, settings.get("openrouter_api_key", "")
        )
        if result and result["question"].strip():
            question, answer, source = result["question"], result["answer"], "openrouter"
    if not question.strip():
        question, answer = await run_in_threadpool(ocr_image, full_path)
        source = "tesseract"

    item = ErrorItem(
        student_id=student.id,
        subject_id=subject_id,
        knowledge_point=knowledge_point.strip()[:100],
        tags=tags.strip()[:200],
        question_text=question,
        answer_text=answer,
        error_reason=error_reason.strip()[:300],
        image_path=filename,
        status="pending",
        ocr_source=source,
        parent_id=parent.id,
    )
    db.add(item)
    db.flush()

    points = get_config_value(db, "points_errorbook", 5)
    if points:
        add_points(
            db,
            student.id,
            points,
            "task",
            f"录入错题：{item.knowledge_point or question[:20]}",
            ref_id=item.id,
            parent_id=parent.id,
        )
    check_badges(db, student.id)
    db.commit()
    return RedirectResponse(
        url="/errorbook/?msg=错题已录入，OCR 识别完成，可在编辑页补充修正", status_code=303
    )


@router.post("/update/{item_id}")
def errorbook_update(
    item_id: int,
    request: Request,
    question_text: str = Form(""),
    answer_text: str = Form(""),
    error_reason: str = Form(""),
    knowledge_point: str = Form(""),
    tags: str = Form(""),
    status: str = Form("pending"),
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    item = db.query(ErrorItem).get(item_id)
    if item is None:
        return RedirectResponse(url="/errorbook/?error=记录不存在", status_code=303)

    was_mastered = item.status == "mastered"
    item.question_text = question_text.strip()
    item.answer_text = answer_text.strip()
    item.error_reason = error_reason.strip()[:300]
    item.knowledge_point = knowledge_point.strip()[:100]
    item.tags = tags.strip()[:200]
    item.status = status

    # 状态改为 mastered 且原状态非 mastered 时发放积分
    if status == "mastered" and not was_mastered:
        points = get_config_value(db, "points_error_mastered", 15)
        if points:
            add_points(
                db,
                student.id,
                points,
                "task",
                f"错题订正掌握：{item.knowledge_point or item.question_text[:20]}",
                ref_id=item.id,
                parent_id=parent.id,
            )
        check_badges(db, student.id)
    db.commit()
    return RedirectResponse(url="/errorbook/?msg=错题已更新", status_code=303)


@router.post("/delete/{item_id}")
def errorbook_delete(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    item = db.query(ErrorItem).get(item_id)
    if item is None:
        return RedirectResponse(url="/errorbook/?error=记录不存在", status_code=303)
    if item.image_path:
        try:
            os.remove(os.path.join(UPLOAD_DIR, os.path.basename(item.image_path)))
        except OSError:
            pass
    db.delete(item)
    db.commit()
    return RedirectResponse(url="/errorbook/?msg=错题已删除", status_code=303)


@router.get("/export")
def errorbook_export(
    request: Request,
    subject_id: str = "",
    knowledge: str = "",
    tag: str = "",
    status: str = "",
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    items = _apply_filters(db, subject_id or None, knowledge or None, tag or None, status or None)
    if not items:
        return RedirectResponse(url="/errorbook/?error=当前筛选下没有可导出的错题", status_code=303)
    path = export_errorbook_pdf(db, items)
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")


@router.get("/image/{name}")
def errorbook_image(name: str):
    """查看原图（防路径穿越：仅取 basename）。"""
    safe = os.path.basename(name)
    path = os.path.join(UPLOAD_DIR, safe)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(path, media_type="image/jpeg")
