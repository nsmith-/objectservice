import datetime
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..auth import AuthorizedUser
from ..db import DBSession, Item, User
from ..shared.models.item import ItemIn, ItemOut

router = APIRouter(
    prefix="/items",
    tags=["items"],
)


@router.get("/", response_model=list[ItemOut])
async def read_items(
    session: DBSession, user: AuthorizedUser, offset: int = 0, limit: int = 100
):
    if "admin" in user.scopes:
        statement = select(Item)
    else:
        statement = select(Item).where(Item.owner_id == user.sub)
    statement = statement.offset(offset).limit(limit).options(selectinload(Item.owner))
    rows = await session.execute(statement)
    items = [ItemOut.model_validate(item) for (item,) in rows]
    return items


async def _get_item(session: DBSession, item_id: int, user: AuthorizedUser) -> Item:
    item = await session.get(Item, item_id, options=(selectinload(Item.owner),))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No item")
    if "admin" in user.scopes or item.owner.id == user.sub:
        return item
    raise HTTPException(
        status.HTTP_404_NOT_FOUND, detail="No item"
    )  # alt. not authorized


@router.get("/{item_id}", response_model=ItemOut)
async def read_item(session: DBSession, item_id: int, user: AuthorizedUser):
    return ItemOut.model_validate(await _get_item(session, item_id, user))


@router.post("/", response_model=ItemOut)
async def create_item(session: DBSession, item_in: ItemIn, user: AuthorizedUser):
    dbuser = await session.merge(
        User(id=user.sub, username=user.username, email=user.email, name=user.name)
    )
    item = Item(owner=dbuser, **item_in.model_dump())
    session.add(item)
    await session.commit()
    return ItemOut.model_validate(item)


@router.put("/{item_id}", response_model=ItemOut)
async def update_item(
    session: DBSession,
    item_in: ItemIn,
    item_id: int,
    user: AuthorizedUser,
):
    item = await _get_item(session, item_id, user)
    for key, value in item_in.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.commit()
    return ItemOut.model_validate(item)


@router.delete("/{item_id}", response_model=ItemOut)
async def delete_item(session: DBSession, item_id: int, user: AuthorizedUser):
    item = await _get_item(session, item_id, user)
    await session.delete(item)
    await session.commit()
    return ItemOut.model_validate(item)
