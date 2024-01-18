import datetime
from contextlib import asynccontextmanager

import sqlalchemy.exc
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from .db import Item, ORMBase, dbengine, session_factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    # async with dbengine.begin() as conn:
    #     await conn.run_sync(ORMBase.metadata.create_all)
    yield
    await dbengine.dispose()


app = FastAPI(
    title="objectservice",
    lifespan=lifespan,
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


class ItemIn(BaseModel):
    id: int
    type: str


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    create_date: datetime.datetime


@app.get("/items/{item_id}", response_model=ItemOut)
async def read_item(item_id: int, q: str | None = None):
    stmt = select(Item).where(Item.id == item_id)
    async with session_factory() as session:
        res = await session.scalars(stmt)
        try:
            return res.one()
        except sqlalchemy.exc.NoResultFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No item")


@app.post("/items/", response_model=ItemOut)
async def create_item(item: ItemIn):
    obj = Item(**item.model_dump())
    async with session_factory() as session:
        session.add(obj)
        try:
            await session.commit()
        except sqlalchemy.exc.IntegrityError:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="item id exists")
    return obj
