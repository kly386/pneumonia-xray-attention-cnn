"""SQLite 数据库配置、ORM 基类及业务表定义。"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

logger = logging.getLogger(__name__)

# 数据库文件统一放在项目根目录的 data 目录中，避免受启动目录影响。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

if DATABASE_URL.startswith("sqlite"):
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite 默认不强制外键，连接建立后显式开启。"""

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _utc_now_naive() -> datetime:
    """SQLite 不保留时区，统一存储无时区的 UTC 时间。"""

    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """系统用户表。"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(64), nullable=True)
    title = Column(String(64), nullable=True)
    department = Column(String(128), nullable=True)
    hospital = Column(String(255), nullable=True)
    license_no = Column(String(64), nullable=True)
    phone = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now_naive)

    history_records = relationship(
        "HistoryRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class HistoryRecord(Base):
    """一次 AI 辅助筛查的历史记录。"""

    __tablename__ = "history_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = Column(String(255), nullable=False)
    prediction = Column(String(16), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    prob_pneumonia = Column(Float, nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(16), nullable=True)
    temperature = Column(Float, nullable=True)
    cough_days = Column(Integer, nullable=True)
    original_url = Column(String(512), nullable=True)
    heatmap_url = Column(String(512), nullable=True)
    doctor_label = Column(String(16), nullable=True)
    use_ai_judgement = Column(Boolean, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    user = relationship("User", back_populates="history_records")


def _migrate_legacy_history_table() -> None:
    """处理旧版 history_records 表结构，避免启动后查询缺列。

    旧表为空时直接重建；旧表有数据时先重命名备份，绝不静默删除历史数据。
    """

    inspector = inspect(engine)
    if not inspector.has_table(HistoryRecord.__tablename__):
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(HistoryRecord.__tablename__)
    }
    required_columns = {
        "id",
        "user_id",
        "filename",
        "prediction",
        "confidence",
        "prob_pneumonia",
        "created_at",
    }
    if required_columns.issubset(existing_columns):
        return

    with engine.begin() as connection:
        row_count = connection.execute(
            text("SELECT COUNT(*) FROM history_records")
        ).scalar_one()

        if row_count == 0:
            connection.execute(text("DROP TABLE history_records"))
            logger.warning("已删除空的旧版 history_records 表，将按新结构重建")
        else:
            backup_name = (
                "history_records_legacy_"
                + datetime.now().strftime("%Y%m%d%H%M%S")
            )
            connection.execute(
                text(f'ALTER TABLE history_records RENAME TO "{backup_name}"')
            )
            logger.warning(
                "检测到不兼容的旧版 history_records 表，已备份为 %s；"
                "新表将重新创建，旧数据未删除",
                backup_name,
            )


def _ensure_optional_history_columns() -> None:
    """为已有的 history_records 表补加新增临床字段，保留历史数据。"""

    inspector = inspect(engine)
    if not inspector.has_table(HistoryRecord.__tablename__):
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(HistoryRecord.__tablename__)
    }
    additions = {
        "age": "INTEGER",
        "gender": "VARCHAR(16)",
        "temperature": "FLOAT",
        "cough_days": "INTEGER",
        "original_url": "VARCHAR(512)",
        "heatmap_url": "VARCHAR(512)",
        "doctor_label": "VARCHAR(16)",
        "use_ai_judgement": "BOOLEAN",
    }

    with engine.begin() as connection:
        for column_name, column_type in additions.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(
                    f"ALTER TABLE history_records "
                    f"ADD COLUMN {column_name} {column_type}"
                )
            )
            logger.info("已为 history_records 补充字段：%s", column_name)


def _ensure_user_profile_columns() -> None:
    """为已有的 users 表补加医生个人资料字段，保留既有账号。"""

    inspector = inspect(engine)
    if not inspector.has_table(User.__tablename__):
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(User.__tablename__)
    }
    additions = {
        "full_name": "VARCHAR(64)",
        "title": "VARCHAR(64)",
        "department": "VARCHAR(128)",
        "hospital": "VARCHAR(255)",
        "license_no": "VARCHAR(64)",
        "phone": "VARCHAR(32)",
    }

    with engine.begin() as connection:
        for column_name, column_type in additions.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(
                    f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
                )
            )
            logger.info("已为 users 补充字段：%s", column_name)


def init_db() -> None:
    """迁移旧表并创建当前版本所需数据库表。"""

    _migrate_legacy_history_table()
    Base.metadata.create_all(bind=engine)
    _ensure_optional_history_columns()
    _ensure_user_profile_columns()


def get_db() -> Generator[Session, None, None]:
    """为每个请求提供独立的 SQLAlchemy 会话。"""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()