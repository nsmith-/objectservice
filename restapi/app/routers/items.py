import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, NoResultFound

from ..db import Item, session_factory

router = APIRouter(
    prefix="/items",
    tags=["items"],
    # dependencies=[Depends(active_user)],
)


class ItemIn(BaseModel):
    id: int
    type: str


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    create_date: datetime.datetime


@router.get("/{item_id}", response_model=ItemOut)
async def read_item(item_id: int, q: str | None = None):
    stmt = select(Item).where(Item.id == item_id)
    async with session_factory() as session:
        res = await session.scalars(stmt)
        try:
            return res.one()
        except NoResultFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No item")


@router.post("/", response_model=ItemOut)
async def create_item(item: ItemIn):
    obj = Item(**item.model_dump())
    async with session_factory() as session:
        session.add(obj)
        try:
            await session.commit()
        except IntegrityError:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="item id exists")
    return obj
