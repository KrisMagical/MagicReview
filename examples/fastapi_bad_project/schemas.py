from typing import Optional

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    username: str
    age: int = Field(...)
    nickname: Optional[str]
    tags: list[str] = []
    metadata = {}
