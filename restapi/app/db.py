import datetime
import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy import ForeignKey, func, types
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class ORMBase(AsyncAttrs, DeclarativeBase):
    pass


class Item(ORMBase):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    create_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    type: Mapped[str]
    data: Mapped[dict | list] = mapped_column(type_=types.JSON)

    owner: Mapped["User"] = relationship(back_populates="items")


class User(ORMBase):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str]
    email: Mapped[str]
    name: Mapped[str]

    items: Mapped[list[Item]] = relationship(back_populates="owner")

    @property
    def sub(self):
        return self.id


def get_dburl() -> str:
    user = os.environ["POSTGRES_USER"]
    pw = os.environ["POSTGRES_PASSWORD"]
    db = os.environ["POSTGRES_DB"]
    return f"postgresql+asyncpg://{user}:{pw}@db/{db}"


dbengine = create_async_engine(get_dburl(), echo=True)
session_factory = async_sessionmaker(dbengine, expire_on_commit=False)


async def get_session():
    async with session_factory() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_session)]


async def check_revision():
    # TODO: check alembic version somehow?
    pass
