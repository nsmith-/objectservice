import datetime
import os

from sqlalchemy import func
from sqlalchemy.ext.asyncio import (AsyncAttrs, AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ORMBase(AsyncAttrs, DeclarativeBase):
    pass


class Item(ORMBase):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str]
    create_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now())


def get_dburl() -> str:
    user = os.environ["POSTGRES_USER"]
    pw = os.environ["POSTGRES_PASSWORD"]
    db = os.environ["POSTGRES_DB"]
    return f"postgresql+asyncpg://{user}:{pw}@db/{db}"


dbengine = create_async_engine(get_dburl(), echo=True)
session_factory = async_sessionmaker(dbengine, expire_on_commit=False)