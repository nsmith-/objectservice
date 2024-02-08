import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Security, status
from pydantic import BaseModel, ConfigDict
from pydantic.types import Json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import User, authorized_user
from ..db import Item
from ..db import User as DBUser
from ..db import session_factory

router = APIRouter(
    prefix="/items",
    tags=["items"],
    # dependencies=[Depends(active_user)],
)


class ItemIn(BaseModel):
    type: str
    data: Json[Any]


class OwnerOut(BaseModel):
    # attributes read from db.User
    model_config = ConfigDict(from_attributes=True)

    name: str
    username: str
    email: str


class ItemOut(BaseModel):
    # attributes read from db.Item
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner: OwnerOut
    create_date: datetime.datetime
    type: str
    data: Any


@router.get("/", response_model=list[ItemOut])
async def read_items(
    user: Annotated[User, Depends(authorized_user)], offset: int = 0, limit: int = 100
):
    async with session_factory() as session:
        if "admin" in user.scopes:
            statement = select(Item)
        else:
            statement = select(Item).where(Item.owner_id == user.sub)
        statement = (
            statement.offset(offset).limit(limit).options(selectinload(Item.owner))
        )
        rows = await session.execute(statement)
        items = [ItemOut.model_validate(item) for item, in rows]
        return items


async def _get_item(session: AsyncSession, item_id: int, user: User) -> Item:
    item = await session.get(Item, item_id, options=(selectinload(Item.owner),))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No item")
    if "admin" in user.scopes or item.owner.id == user.sub:
        return item
    raise HTTPException(
        status.HTTP_404_NOT_FOUND, detail="No item"
    )  # alt. not authorized


@router.get("/{item_id}", response_model=ItemOut)
async def read_item(item_id: int, user: Annotated[User, Depends(authorized_user)]):
    async with session_factory() as session:
        return ItemOut.model_validate(await _get_item(session, item_id, user))


@router.post("/", response_model=ItemOut)
async def create_item(
    item_in: ItemIn, user: Annotated[User, Security(authorized_user, scopes=["admin"])]
):
    async with session_factory() as session:
        dbuser = await session.merge(
            DBUser(
                id=user.sub, username=user.username, email=user.email, name=user.name
            )
        )
        item = Item(owner=dbuser, **item_in.model_dump())
        session.add(item)
        await session.commit()
        return ItemOut.model_validate(item)


@router.put("/{item_id}", response_model=ItemOut)
async def update_item(
    item_in: ItemIn,
    item_id: int,
    user: Annotated[User, Security(authorized_user, scopes=["admin"])],
):
    async with session_factory() as session:
        item = await _get_item(session, item_id, user)
        for key, value in item_in.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await session.commit()
        return ItemOut.model_validate(item)


@router.delete("/{item_id}", response_model=ItemOut)
async def delete_item(
    item_id: int, user: Annotated[User, Security(authorized_user, scopes=["admin"])]
):
    async with session_factory() as session:
        item = await _get_item(session, item_id, user)
        await session.delete(item)
        await session.commit()
        return ItemOut.model_validate(item)
