from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass


def make_engine(database_url: str):
    return create_async_engine(database_url, echo=False)


def make_session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)
