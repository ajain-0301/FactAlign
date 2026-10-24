"""Database layer. SQLite by default; any SQLAlchemy URL (e.g. PostgreSQL) works."""
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
SessionLocal: sessionmaker | None = None


def init_db(url: str) -> None:
    global _engine, SessionLocal
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        path = url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url, **kwargs)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    from app import models  # noqa: F401  (register tables)

    Base.metadata.create_all(_engine)


def get_session() -> Iterator[Session]:
    assert SessionLocal is not None, "Database not initialised"
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def ping() -> bool:
    assert _engine is not None
    with _engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
