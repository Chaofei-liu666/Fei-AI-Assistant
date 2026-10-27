from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def create_database_engine(url: str | None = None):
    return create_engine(url or get_settings().database_url, pool_pre_ping=True)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
