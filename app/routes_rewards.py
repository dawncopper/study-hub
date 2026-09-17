"""积分兑换勋章路由（F4/F5/F7，文档 5.6/5.7）。"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import get_current_parent
from .common import (
    BADGE_DEFS,
    add_points,
    calc_streak,
    check_badges,
    get_config_value,
    get_points_balance,
    get_student,
)
from .database import get_db
from .models import (
    Badge,
    GameTimeOrder,
    PointTransaction,
    RewardConfig,
    Subject,
)

router = APIRouter(prefix="/rewards", tags=["rewards"])


def _level(balance: int) -> tuple[int, int]:
    """成长等级 = 每 100 星升 1 级。返回 (level, progress)。"""
    level = balance // 100 + 1
    progress = balance % 100
    return level, progress


def _tree_emoji(level: int) -> str:
    if level >= 20:
        return "🌳"
    if level >= 10:
        return "🌲"
    if level >= 5:
        return "🌿"
    return "🌱"


@router.get("/")
def rewards_page(
    request: Request,
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)

    # 检查并发放新勋章
    new_badges = check_badges(db, student.id)
    db.commit()
    if new_badges and not msg:
        msg = f"🎉 获得新勋章：{'、'.join(b.name for b in new_badges)}"

    balance = get_points_balance(db, student.id)
    level, progress = _level(balance)

    rules = db.query(RewardConfig).order_by(RewardConfig.id).all()
    exchange_rule = get_config_value(db, "exchange_points", 3)
    daily_limit = get_config_value(db, "daily_game_limit", 60)
    weekly_limit = get_config_value(db, "weekly_game_limit", 180)

    today = date.today()
    today_used = (
        db.query(func.coalesce(func.sum(GameTimeOrder.minutes), 0))
        .filter(
            GameTimeOrder.student_id == student.id,
            func.date(GameTimeOrder.created_at) == today.isoformat(),
        )
        .scalar()
        or 0
    )
    week_start = today - timedelta(days=today.weekday())
    week_used = (
        db.query(func.coalesce(func.sum(GameTimeOrder.minutes), 0))
        .filter(
            GameTimeOrder.student_id == student.id,
            func.date(GameTimeOrder.created_at) >= week_start.isoformat(),
        )
        .scalar()
        or 0
    )

    orders = (
        db.query(GameTimeOrder)
        .filter_by(student_id=student.id)
        .order_by(GameTimeOrder.created_at.desc())
        .limit(30)
        .all()
    )
    transactions = (
        db.query(PointTransaction)
        .filter_by(student_id=student.id)
        .order_by(PointTransaction.created_at.desc())
        .limit(20)
        .all()
    )
    badges = db.query(Badge).filter_by(student_id=student.id).all()
    earned_keys = {b.badge_key for b in badges}
    badge_view = [
        {
            "key": key,
            "name": name,
            "icon": icon,
            "earned": key in earned_keys,
        }
        for key, name, icon in BADGE_DEFS
    ]
    streak = calc_streak(db, student.id)

    return request.app.state.templates.TemplateResponse(
        request,
        "rewards.html",
        {
            "parent": parent,
            "student": student,
            "balance": balance,
            "level": level,
            "progress": progress,
            "tree_emoji": _tree_emoji(level),
            "rules": rules,
            "exchange_rule": exchange_rule,
            "daily_limit": daily_limit,
            "weekly_limit": weekly_limit,
            "today_used": int(today_used),
            "week_used": int(week_used),
            "orders": orders,
            "transactions": transactions,
            "badges": badge_view,
            "streak": streak,
            "msg": msg,
            "error": error,
            "active_nav": "rewards",
        },
    )


@router.post("/exchange")
def rewards_exchange(
    request: Request,
    minutes: int = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    minutes = max(1, min(240, minutes))
    cost = minutes * get_config_value(db, "exchange_points", 3)
    balance = get_points_balance(db, student.id)

    if balance < cost:
        return RedirectResponse(
            url=f"/rewards/?error=星星不足：需要 {cost} 星，当前 {balance} 星", status_code=303
        )

    add_points(
        db,
        student.id,
        -cost,
        "reward",
        f"兑换游戏时间 {minutes} 分钟",
        parent_id=parent.id,
    )
    order = GameTimeOrder(
        student_id=student.id,
        points_cost=cost,
        minutes=minutes,
        status="approved",
        note=note.strip()[:200],
        parent_id=parent.id,
    )
    db.add(order)
    db.commit()
    return RedirectResponse(
        url=f"/rewards/?msg=兑换成功：{minutes} 分钟游戏时间，消耗 {cost} 星", status_code=303
    )


@router.post("/order/{order_id}/used")
def rewards_order_used(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    order = db.query(GameTimeOrder).get(order_id)
    if order is None:
        return RedirectResponse(url="/rewards/?error=记录不存在", status_code=303)
    order.status = "used"
    db.commit()
    return RedirectResponse(url="/rewards/?msg=已标记为使用完成", status_code=303)


@router.post("/adjust")
def rewards_adjust(
    request: Request,
    amount: int = Form(...),
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    parent = get_current_parent(request, db)
    student = get_student(db)
    if amount == 0:
        return RedirectResponse(url="/rewards/?error=调整数量不能为 0", status_code=303)
    amount = max(-5000, min(5000, amount))
    add_points(
        db,
        student.id,
        amount,
        "adjust",
        (reason or "家长手动调整").strip()[:200],
        parent_id=parent.id,
    )
    check_badges(db, student.id)
    db.commit()
    return RedirectResponse(url="/rewards/?msg=积分已调整", status_code=303)


@router.post("/refresh-badges")
def rewards_refresh_badges(
    request: Request,
    db: Session = Depends(get_db),
):
    get_current_parent(request, db)
    student = get_student(db)
    new_badges = check_badges(db, student.id)
    db.commit()
    if new_badges:
        return RedirectResponse(
            url=f"/rewards/?msg=🎉 获得新勋章：{'、'.join(b.name for b in new_badges)}",
            status_code=303,
        )
    return RedirectResponse(url="/rewards/?msg=暂无新的勋章可领取", status_code=303)
