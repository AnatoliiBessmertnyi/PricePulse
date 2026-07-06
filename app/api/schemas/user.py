from datetime import datetime

from pydantic import BaseModel


class UserCreate(BaseModel):
    chat_id: int
    username: str | None = None


class UserResponse(BaseModel):
    id: int
    chat_id: int
    username: str | None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
