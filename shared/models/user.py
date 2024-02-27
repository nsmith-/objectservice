from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    # attributes read from db.User
    model_config = ConfigDict(from_attributes=True)

    sub: str = Field(description="Subject (user unique ID)")
    username: str
    email: str | None = None
    name: str | None = None


class CurrentUser(UserOut):
    scopes: list[str] = []
