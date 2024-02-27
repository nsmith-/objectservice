import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.types import Json

from .user import UserOut


class ItemIn(BaseModel):
    type: str
    data: Json[Any]


class ItemOut(BaseModel):
    # attributes read from db.Item
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner: UserOut
    create_date: datetime.datetime
    type: str
    data: Any
