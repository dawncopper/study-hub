"""设置路由（F9，文档 5.10）：积分规则、通知推送、家长/学生/科目管理。"""
import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .auth import get_current_parent, hash_password
from .common import get_settings_dict, get_student
from .database import UPLOAD_DIR, get_db
from .models import Parent, RewardConfig, Setting, Student, Subject
from .notify import send_notification
from .ocr import openrouter_recognize
from .scheduler import reschedule

router = APIRouter(prefix="/settings", tags=["settings"])

WEBHOOK_KEYS = ["notify_wecom_webhook", "notify_wechat_webhook"]
EMAIL_KEYS = [
    "notify_email_smtp",
    "notify_email_port",
    "notify_email_user",
    "notify_email_pass",
    "notify_email_to",
]
STUDENT_KEYS = ["student_name", "student_grade", "student_gender", "school_notice"]


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(Setting).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))


@router.get("/")
def settings_page(
    request: Request,
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    settings = get_settings_dict(db)
    rules = db.query(RewardConfig).order_by(RewardConfig.id).all()
    subjects = db.query(Subject).order_by(Subject.sort_order).all()
    parents = db.query(Parent).order_by(Parent.id).all()

    return request.app.state.templates.TemplateResponse(
        request,
        "settings.html",
        {
            "parent": parent,
            "student": student,
            "settings": settings,
            "rules": rules,
            "subjects": subjects,
            "parents": parents,
            "msg": msg,
            "error": error,
            "active_nav": "settings",
        },
    )


@router.post("/config")
def settings_config(
    request: Request,
    key: str = Form(...),
    value: int = Form(0),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    row = db.query(RewardConfig).filter_by(key=key).first()
    if row is None:
        return RedirectResponse(url="/settings/?error=规则不存在", status_code=303)
    value = max(-5000, min(5000, value))
    row.value = value
    db.commit()
    return RedirectResponse(url="/settings/?msg=积分规则已更新", status_code=303)


@router.post("/notify")
def settings_notify(
    request: Request,
    reminder_time: str = Form("19:00"),
    reminder_enabled: str = Form("0"),
    notify_wecom_webhook: str = Form(""),
    notify_wechat_webhook: str = Form(""),
    notify_email_smtp: str = Form(""),
    notify_email_port: str = Form("465"),
    notify_email_user: str = Form(""),
    notify_email_pass: str = Form(""),
    notify_email_to: str = Form(""),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    for key, value in [
        ("reminder_time", reminder_time.strip()),
        ("reminder_enabled", "1" if reminder_enabled == "1" else "0"),
        ("notify_wecom_webhook", notify_wecom_webhook.strip()),
        ("notify_wechat_webhook", notify_wechat_webhook.strip()),
        ("notify_email_smtp", notify_email_smtp.strip()),
        ("notify_email_port", notify_email_port.strip() or "465"),
        ("notify_email_user", notify_email_user.strip()),
        ("notify_email_pass", notify_email_pass),
        ("notify_email_to", notify_email_to.strip()),
    ]:
        _set_setting(db, key, value)
    db.commit()

    # 重排定时任务
    try:
        reschedule(
            reminder_time.strip() or "19:00",
            enabled=(reminder_enabled == "1"),
        )
    except Exception:  # noqa: BLE001
        pass
    return RedirectResponse(url="/settings/?msg=提醒与通知设置已保存", status_code=303)


@router.post("/test-notify")
def settings_test_notify(
    request: Request,
    reminder_time: str = Form("19:00"),
    reminder_enabled: str = Form("0"),
    notify_wecom_webhook: str = Form(""),
    notify_wechat_webhook: str = Form(""),
    notify_email_smtp: str = Form(""),
    notify_email_port: str = Form("465"),
    notify_email_user: str = Form(""),
    notify_email_pass: str = Form(""),
    notify_email_to: str = Form(""),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    settings = {
        "notify_wecom_webhook": notify_wecom_webhook.strip(),
        "notify_wechat_webhook": notify_wechat_webhook.strip(),
        "notify_email_smtp": notify_email_smtp.strip(),
        "notify_email_port": notify_email_port.strip() or "465",
        "notify_email_user": notify_email_user.strip(),
        "notify_email_pass": notify_email_pass,
        "notify_email_to": notify_email_to.strip(),
    }
    results = send_notification(settings, "【学习小站】这是一条测试推送：提醒与通知已配置成功！")
    if not results:
        return RedirectResponse(url="/settings/?error=尚未配置任何推送渠道", status_code=303)
    return RedirectResponse(
        url=f"/settings/?msg=测试推送结果：{'；'.join(results)}", status_code=303
    )


@router.post("/openrouter")
def settings_openrouter(
    request: Request,
    openrouter_enabled: str = Form("0"),
    openrouter_api_key: str = Form(""),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    _set_setting(db, "openrouter_enabled", "1" if openrouter_enabled == "1" else "0")
    # 密码框留空表示保留原 Key；填写新值才更新
    if openrouter_api_key.strip():
        _set_setting(db, "openrouter_api_key", openrouter_api_key.strip())
    db.commit()
    return RedirectResponse(url="/settings/?msg=OpenRouter 配置已保存", status_code=303)


@router.post("/openrouter-test")
def settings_openrouter_test(
    request: Request,
    openrouter_enabled: str = Form("0"),
    openrouter_api_key: str = Form(""),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    settings = get_settings_dict(db)
    key = openrouter_api_key.strip() or settings.get("openrouter_api_key", "")
    enabled = (openrouter_enabled == "1") or settings.get("openrouter_enabled", "0") == "1"
    if not enabled:
        return RedirectResponse(url="/settings/?error=OpenRouter 未启用，请先启用并保存", status_code=303)
    if not key:
        return RedirectResponse(url="/settings/?error=尚未配置 OpenRouter API Key", status_code=303)

    # 生成一张白底黑字的测试图
    test_path = os.path.join(UPLOAD_DIR, "_openrouter_test.png")
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (640, 200), "white")
        draw = ImageDraw.Draw(img)
        draw.text((40, 80), "StudyHub OCR Test: 3 + 5 = 8", fill="black")
        img.save(test_path)
    except Exception:  # noqa: BLE001
        return RedirectResponse(url="/settings/?error=测试图生成失败，请检查 Pillow 依赖", status_code=303)

    result = openrouter_recognize(test_path, key)
    if not result:
        return RedirectResponse(
            url="/settings/?error=测试识别失败：请求超时或返回格式异常（请检查 API Key、网络与模型可用性）",
            status_code=303,
        )
    msg = f"测试识别成功：题目「{result['question'][:50]}」｜答案「{result['answer'][:50]}」"
    return RedirectResponse(url=f"/settings/?msg={msg}", status_code=303)


@router.post("/student")
def settings_student(
    request: Request,
    student_name: str = Form("小明"),
    student_grade: str = Form("初一"),
    student_gender: str = Form("男"),
    school_notice: str = Form(""),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    student = get_student(db)
    student.name = student_name.strip()[:20] or "小明"
    student.grade = student_grade.strip()[:20] or "初一"
    student.gender = student_gender.strip()[:10] or "男"
    db.commit()
    _set_setting(db, "student_name", student.name)
    _set_setting(db, "student_grade", student.grade)
    _set_setting(db, "student_gender", student.gender)
    _set_setting(db, "school_notice", school_notice.strip()[:200])
    db.commit()
    return RedirectResponse(url="/settings/?msg=学生信息已更新", status_code=303)


@router.post("/subject")
def settings_subject(
    request: Request,
    name: str = Form(...),
    color: str = Form("#007AFF"),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=科目名不能为空", status_code=303)
    if db.query(Subject).filter_by(name=name).first():
        return RedirectResponse(url="/settings/?error=科目已存在", status_code=303)
    max_order = (
        db.query(Subject).order_by(Subject.sort_order.desc()).first().sort_order
        if db.query(Subject).count()
        else 0
    )
    db.add(Subject(name=name[:20], color=color, sort_order=max_order + 1))
    db.commit()
    return RedirectResponse(url="/settings/?msg=科目已添加", status_code=303)


@router.post("/subject/{subject_id}/delete")
def settings_subject_delete(
    subject_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    subject = db.query(Subject).get(subject_id)
    if subject is None:
        return RedirectResponse(url="/settings/?error=科目不存在", status_code=303)
    db.delete(subject)
    db.commit()
    return RedirectResponse(url="/settings/?msg=科目已删除", status_code=303)


@router.post("/parent")
def settings_parent(
    request: Request,
    username: str = Form(...),
    nickname: str = Form(""),
    password: str = Form(...),
    role: str = Form("member"),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    username = username.strip()
    if not username or len(password) < 6:
        return RedirectResponse(url="/settings/?error=用户名不能为空，密码至少 6 位", status_code=303)
    if db.query(Parent).filter_by(username=username).first():
        return RedirectResponse(url="/settings/?error=用户名已存在", status_code=303)
    db.add(
        Parent(
            username=username[:50],
            nickname=nickname.strip()[:50],
            password_hash=hash_password(password),
            role="admin" if role == "admin" else "member",
        )
    )
    db.commit()
    return RedirectResponse(url="/settings/?msg=家长账号已添加", status_code=303)


@router.post("/parent/{parent_id}/password")
def settings_parent_password(
    parent_id: int,
    request: Request,
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    if len(password) < 6:
        return RedirectResponse(url="/settings/?error=密码至少 6 位", status_code=303)
    target = db.query(Parent).get(parent_id)
    if target is None:
        return RedirectResponse(url="/settings/?error=账号不存在", status_code=303)
    target.password_hash = hash_password(password)
    db.commit()
    return RedirectResponse(url="/settings/?msg=密码已重置", status_code=303)


@router.post("/parent/{parent_id}/delete")
def settings_parent_delete(
    parent_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    current = get_current_parent(request, db)
    if current.id == parent_id:
        return RedirectResponse(url="/settings/?error=不能删除自己", status_code=303)
    target = db.query(Parent).get(parent_id)
    if target is None:
        return RedirectResponse(url="/settings/?error=账号不存在", status_code=303)
    db.delete(target)
    db.commit()
    return RedirectResponse(url="/settings/?msg=家长账号已删除", status_code=303)
