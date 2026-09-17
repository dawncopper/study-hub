"""周报/月报数据 + 错题本 PDF 导出（ReportLab，文档 5.5/5.7）。"""
import os
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import EXPORT_DIR
from .models import DailyRecord, Difficulty, ErrorItem, PointTransaction

CATEGORY_LABELS = {"homework": "校内作业", "preview": "预习", "extra": "课外练习"}
CATEGORY_ICONS = {"homework": "📝", "preview": "📖", "extra": "✏️"}
CATEGORIES = ["homework", "preview", "extra"]


def parse_period(period: str) -> tuple[date, date]:
    today = date.today()
    if period == "week":
        start = today - timedelta(days=today.weekday())
        end = today
    elif period == "month":
        start = today.replace(day=1)
        end = today
    else:  # 7d
        start = today - timedelta(days=6)
        end = today
    return start, end


def build_report(db: Session, student_id: int, period: str) -> dict:
    """周报/月报/近7天统计。"""
    start, end = parse_period(period)
    days = (end - start).days + 1
    records = (
        db.query(DailyRecord)
        .filter(
            DailyRecord.student_id == student_id,
            DailyRecord.record_date >= start,
            DailyRecord.record_date <= end,
        )
        .all()
    )

    modules = {}
    for cat in CATEGORIES:
        items = [r for r in records if r.category == cat]
        modules[cat] = {
            "label": CATEGORY_LABELS[cat],
            "icon": CATEGORY_ICONS[cat],
            "total": len(items),
            "done": sum(1 for r in items if r.status == "done"),
            "partial": sum(1 for r in items if r.status == "partial"),
            "undone": sum(1 for r in items if r.status == "undone"),
            "points": sum(r.points_granted or 0 for r in items),
        }

    done_count = sum(1 for r in records if r.status == "done")
    total = len(records)

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    solved = (
        db.query(Difficulty)
        .filter(
            Difficulty.student_id == student_id,
            Difficulty.status == "solved",
            Difficulty.solved_at >= start_dt,
            Difficulty.solved_at <= end_dt,
        )
        .count()
    )
    mastered = (
        db.query(ErrorItem)
        .filter(
            ErrorItem.student_id == student_id,
            ErrorItem.status == "mastered",
            ErrorItem.created_at >= start_dt,
            ErrorItem.created_at <= end_dt,
        )
        .count()
    )
    points = (
        db.query(func.coalesce(func.sum(PointTransaction.amount), 0))
        .filter(
            PointTransaction.student_id == student_id,
            PointTransaction.created_at >= start_dt,
            PointTransaction.created_at <= end_dt,
        )
        .scalar()
        or 0
    )

    return {
        "start": start,
        "end": end,
        "days": days,
        "total": total,
        "done": done_count,
        "completion": round(done_count / total * 100) if total else 0,
        "modules": modules,
        "solved": solved,
        "mastered": mastered,
        "points": int(points),
    }


def build_trend(db: Session, student_id: int, days: int = 30) -> list[dict]:
    """近 N 天每日净积分柱状图数据。"""
    today = date.today()
    start = today - timedelta(days=days - 1)
    rows = (
        db.query(
            func.date(PointTransaction.created_at).label("d"),
            func.sum(PointTransaction.amount).label("s"),
        )
        .filter(
            PointTransaction.student_id == student_id,
            func.date(PointTransaction.created_at) >= start.isoformat(),
        )
        .group_by("d")
        .all()
    )
    by_date = {r.d: int(r.s or 0) for r in rows}
    items = []
    for i in range(days):
        d = start + timedelta(days=i)
        items.append({"date": d, "value": by_date.get(d.isoformat(), 0)})
    return items


def _register_cjk_font() -> str:
    """注册中文字体，返回字体名。Windows 回退 msyh/simhei。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        ("NotoSansCJK", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("NotoSansCJK", "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf", None),
        ("msyh", "C:/Windows/Fonts/msyh.ttc", 0),
        ("msyh", "C:/Windows/Fonts/msyh.ttf", None),
        ("simhei", "C:/Windows/Fonts/simhei.ttf", None),
    ]
    for name, path, idx in candidates:
        if os.path.exists(path):
            try:
                if idx is not None:
                    pdfmetrics.registerFont(TTFont("CJK", path, subfontIndex=idx))
                else:
                    pdfmetrics.registerFont(TTFont("CJK", path))
                return "CJK"
            except Exception:  # noqa: BLE001
                continue
    return "Helvetica"


def _wrap_text(text: str, width: int = 58) -> list[str]:
    """按显示宽度近似切行（中文按 2 宽计）。"""
    if not text:
        return []
    lines = []
    cur = ""
    cur_w = 0
    for ch in text:
        w = 2 if ord(ch) > 0x2E7F else 1
        if cur_w + w > width * 2:
            lines.append(cur)
            cur = ch
            cur_w = w
        else:
            cur += ch
            cur_w += w
    if cur:
        lines.append(cur)
    return lines


_STATUS_CN = {"pending": "待订正", "reviewed": "已订正", "mastered": "已掌握"}


def export_errorbook_pdf(
    db: Session, items: list[ErrorItem], filename: str | None = None
) -> str:
    """导出错题本 PDF，返回文件绝对路径。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    font = _register_cjk_font()
    if not filename:
        filename = f"错题本_{date.today().isoformat()}.pdf"
    path = os.path.join(EXPORT_DIR, filename)

    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    margin = 18 * mm

    c.setFont(font, 20)
    c.drawString(margin, h - 25 * mm, "错题本")
    c.setFont(font, 10)
    c.drawString(
        margin,
        h - 32 * mm,
        f"导出日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}    共 {len(items)} 题",
    )
    y = h - 42 * mm

    for i, item in enumerate(items, 1):
        if y < 40 * mm:
            c.showPage()
            y = h - 25 * mm
        subject = item.subject.name if item.subject else ""
        c.setFont(font, 12)
        c.drawString(
            margin,
            y,
            f"{i}. 【{subject}】{item.knowledge_point or '无知识点'}    [{_STATUS_CN.get(item.status, item.status)}]",
        )
        y -= 6 * mm

        c.setFont(font, 10)
        for line in _wrap_text(item.question_text or ""):
            c.drawString(margin + 4 * mm, y, line)
            y -= 4.5 * mm

        if item.answer_text:
            y -= 1 * mm
            for line in _wrap_text("答案：" + item.answer_text):
                c.drawString(margin + 4 * mm, y, line)
                y -= 4.5 * mm

        if item.error_reason:
            y -= 1 * mm
            for line in _wrap_text("错因：" + item.error_reason):
                c.drawString(margin + 4 * mm, y, line)
                y -= 4.5 * mm

        y -= 5 * mm

    c.save()
    return path
