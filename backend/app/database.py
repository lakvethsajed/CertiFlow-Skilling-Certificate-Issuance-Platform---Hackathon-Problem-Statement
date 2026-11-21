from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError("CertiFlow requires a PostgreSQL database URL.")
    return create_engine(url.set(drivername="postgresql+psycopg"), pool_pre_ping=True)
