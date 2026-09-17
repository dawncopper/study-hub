"""公共辅助函数：学生信息、积分、规则、勋章检查。"""
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import (
    Badge,
    DailyRecord,
    ErrorItem,
    PointTransaction,
    RewardConfig,
    Setting,
    Student,
)

# 勋章定义（文档 4.10）
BADGE_DEFS = [
    ("streak7", "连续打卡7天", "🔥"),
    ("streak30", "连续打卡30天", "🌟"),
    ("err10", "错题猎人", "🎯"),
    ("err50", "错题大师", "🏆"),
    ("pt500", "积分新星", "⭐"),
    ("pt2000", "积分达人", "👑"),
]


def get_student(db: Session, student_id: int = 1) -> Student:
    return db.query(Student).get(student_id)


def get_settings_dict(db: Session) -> dict:
    return {s.key: s.value for s in db.query(Setting).all()}


def get_config_value(db: Session, key: str, default: int = 0) -> int:
    row = db.query(RewardConfig).filter_by(key=key).first()
    return row.value if row else default


def get_points_balance(db: Session, student_id: int = 1) -> int:
    total = (
        db.query(func.coalesce(func.sum(PointTransaction.amount), 0))
        .filter_by(student_id=student_id)
        .scalar()
    )
    return int(total or 0)


def add_points(
    db: Session,
    student_id: int,
    amount: int,
    category: str,
    reason: str,
    ref_id: int | None = None,
    parent_id: int | None = None,
) -> PointTransaction | None:
    """写一条积分流水（amount 为 0 时跳过）。"""
    if not amount:
        return None
    tx = PointTransaction(
        student_id=student_id,
        amount=amount,
        category=category,
        reason=reason,
        ref_id=ref_id,
        parent_id=parent_id,
    )
    db.add(tx)
    db.flush()
    return tx


def calc_streak(db: Session, student_id: int = 1) -> int:
    """连续打卡天数（从最近打卡日往前数）。"""
    today = date.today()
    d = today
    if not db.query(DailyRecord).filter_by(record_date=d, student_id=student_id).first():
        d = today - timedelta(days=1)
    streak = 0
    while True:
        if not db.query(DailyRecord).filter_by(record_date=d, student_id=student_id).first():
            break
        streak += 1
        d -= timedelta(days=1)
    return streak


def check_badges(db: Session, student_id: int = 1) -> list[Badge]:
    """检查并发放满足条件的未获得勋章。返回本次新发放列表。"""
    earned = {
        b.badge_key for b in db.query(Badge).filter_by(student_id=student_id).all()
    }
    mastered_count = (
        db.query(ErrorItem)
        .filter_by(student_id=student_id, status="mastered")
        .count()
    )
    balance = get_points_balance(db, student_id)
    streak = calc_streak(db, student_id)

    conditions = {
        "streak7": streak >= 7,
        "streak30": streak >= 30,
        "err10": mastered_count >= 10,
        "err50": mastered_count >= 50,
        "pt500": balance >= 500,
        "pt2000": balance >= 2000,
    }

    new_badges: list[Badge] = []
    for key, name, icon in BADGE_DEFS:
        if key not in earned and conditions.get(key):
            badge = Badge(
                student_id=student_id, badge_key=key, name=name, icon=icon
            )
            db.add(badge)
            new_badges.append(badge)
    if new_badges:
        db.flush()
    return new_badges
