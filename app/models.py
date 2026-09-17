"""SQLAlchemy 数据模型（11 张表）。"""
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class Parent(Base):
    """家长账号（F8 多方参与）。"""
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    nickname = Column(String(50), default="")
    role = Column(String(20), default="member")  # admin / member
    subjects = Column(String(200), default="")  # 分工科目 ID，逗号分隔；空=全科
    created_at = Column(DateTime, default=datetime.now)


class Student(Base):
    """学生。"""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), default="小明")
    gender = Column(String(10), default="男")
    grade = Column(String(50), default="初一")
    avatar = Column(String(20), default="🎒")
    created_at = Column(DateTime, default=datetime.now)


class Subject(Base):
    """科目。"""
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(20), default="#007AFF")
    sort_order = Column(Integer, default=0)


class DailyRecord(Base):
    """每日打卡（F1）。"""
    __tablename__ = "daily_records"
    __table_args__ = (
        UniqueConstraint("record_date", "category", "subject_id", name="uq_daily_record"),
    )

    id = Column(Integer, primary_key=True)
    record_date = Column(Date, nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), default=1)
    category = Column(String(20), nullable=False)  # homework / preview / extra
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    content = Column(String(500), default="")
    status = Column(String(20), default="done")  # done / partial / undone
    quality = Column(Integer, default=0)  # 0-5
    note = Column(String(300), default="")
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True)
    points_granted = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    subject = relationship("Subject")


class Difficulty(Base):
    """难点疑点（F2）。"""
    __tablename__ = "difficulties"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), default=1)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    status = Column(String(20), default="open")  # open / solved
    solution = Column(Text, default="")
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    solved_at = Column(DateTime, nullable=True)

    subject = relationship("Subject")


class ErrorItem(Base):
    """错题（F3）。"""
    __tablename__ = "error_items"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), default=1)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    knowledge_point = Column(String(100), default="")
    tags = Column(String(200), default="")  # 逗号分隔
    question_text = Column(Text, default="")
    answer_text = Column(Text, default="")
    error_reason = Column(String(300), default="")
    image_path = Column(String(300), default="")  # data/uploads/ 下文件名
    status = Column(String(20), default="pending")  # pending / reviewed / mastered
    ocr_source = Column(String(20), default="tesseract")  # openrouter / tesseract / manual
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    subject = relationship("Subject")


class RewardConfig(Base):
    """积分规则（参数化，F4）。"""
    __tablename__ = "reward_configs"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    value = Column(Integer, default=0)
    unit = Column(String(20), default="星")
    description = Column(String(200), default="")


class PointTransaction(Base):
    """积分流水。"""
    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), default=1)
    amount = Column(Integer, default=0)  # 正=收入，负=支出
    category = Column(String(20), default="task")  # task / reward / deduct / adjust
    reason = Column(String(200), default="")
    ref_id = Column(Integer, nullable=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class GameTimeOrder(Base):
    """游戏时间兑换单（F5）。"""
    __tablename__ = "game_time_orders"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), default=1)
    points_cost = Column(Integer, default=0)
    minutes = Column(Integer, default=0)
    status = Column(String(20), default="approved")  # approved 待使用 / used 已使用
    note = Column(String(200), default="")
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class Badge(Base):
    """成就勋章（F7）。"""
    __tablename__ = "badges"
    __table_args__ = (
        UniqueConstraint("student_id", "badge_key", name="uq_badge"),
    )

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), default=1)
    badge_key = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    icon = Column(String(20), default="🏅")
    earned_at = Column(DateTime, default=datetime.now)


class Setting(Base):
    """系统设置（F9）。"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(Text, default="")
