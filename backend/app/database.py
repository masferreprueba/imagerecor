from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import get_settings


class Base(DeclarativeBase):
    pass


class JobRecord(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    total_images: Mapped[int] = mapped_column(Integer, default=0)
    processed_images: Mapped[int] = mapped_column(Integer, default=0)
    failed_images: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    if settings.database_url.startswith("sqlite"):
        Path("data").mkdir(exist_ok=True)
    Base.metadata.create_all(engine)


def update_job(job_id: str, **values) -> None:
    values["updated_at"] = datetime.now(timezone.utc)
    with SessionLocal.begin() as session:
        record = session.get(JobRecord, job_id)
        if record:
            for key, value in values.items():
                setattr(record, key, value)
