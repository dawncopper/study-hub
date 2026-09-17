"""首次启动初始化：管理员/学生/科目/规则/设置。"""
from sqlalchemy.orm import Session

from .auth import hash_password
from .models import Parent, RewardConfig, Setting, Student, Subject

DEFAULT_SUBJECTS = [
    ("语文", "#E8543F", 1),
    ("数学", "#0071E3", 2),
    ("英语", "#3AA757", 3),
    ("科学", "#7A5AF8", 4),
    ("道法", "#B15CE6", 5),
    ("历史", "#C77A1F", 6),
    ("地理", "#2A9D8F", 7),
    ("生物", "#4FAE5A", 8),
]

DEFAULT_RULES = [
    ("points_homework", "完成校内作业", 10, "星", "每日每科"),
    ("points_preview", "完成预习", 5, "星", "每日每科"),
    ("points_extra", "完成课外练习", 8, "星", "每日每科"),
    ("points_quality", "作业质量满分额外奖励", 3, "星", "质量评 5 星时额外奖励"),
    ("points_difficulty", "难点/疑点解决", 15, "星", "标记已解决"),
    ("points_errorbook", "录入一道错题", 5, "星", "拍照录入"),
    ("points_error_mastered", "错题订正掌握", 15, "星", "标记已掌握"),
    ("points_continuous7", "连续打卡7天", 30, "星", "周期奖励（v1 通过勋章体现）"),
    ("deduct_undone", "未完成作业", -5, "星", "每日每科"),
    ("deduct_partial", "作业部分完成", -2, "星", "每日每科"),
    ("exchange_points", "兑换1分钟游戏时间所需星星", 3, "星", "默认 3 星=1 分钟"),
    ("daily_game_limit", "每日游戏时间上限", 60, "分钟", "家长线下把控参考"),
    ("weekly_game_limit", "每周游戏时间上限", 180, "分钟", "家长线下把控参考"),
]

DEFAULT_SETTINGS = [
    ("reminder_time", "19:00"),
    ("reminder_enabled", "1"),
    ("notify_wecom_webhook", ""),
    ("notify_wechat_webhook", ""),
    ("notify_email_smtp", ""),
    ("notify_email_port", "465"),
    ("notify_email_user", ""),
    ("notify_email_pass", ""),
    ("notify_email_to", ""),
    ("student_name", "小明"),
    ("student_grade", "初一"),
    ("student_gender", "男"),
    ("school_notice", "欢迎来到学习小站，一起加油！"),
    ("openrouter_api_key", ""),
    ("openrouter_enabled", "0"),
]


def seed(db: Session) -> None:
    """幂等初始化。"""
    if not db.query(Parent).filter_by(username="admin").first():
        db.add(
            Parent(
                username="admin",
                password_hash=hash_password("123456"),
                nickname="管理员",
                role="admin",
            )
        )

    if db.query(Student).count() == 0:
        db.add(Student())

    if db.query(Subject).count() == 0:
        for name, color, order in DEFAULT_SUBJECTS:
            db.add(Subject(name=name, color=color, sort_order=order))

    if db.query(RewardConfig).count() == 0:
        for key, name, value, unit, desc in DEFAULT_RULES:
            db.add(
                RewardConfig(
                    key=key, name=name, value=value, unit=unit, description=desc
                )
            )

    if db.query(Setting).count() == 0:
        for key, value in DEFAULT_SETTINGS:
            db.add(Setting(key=key, value=value))

    db.commit()
