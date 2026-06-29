from fastapi import APIRouter, Depends

from app.api.dependencies import get_user_service
from app.api.schemas.user import UserCreate, UserResponse
from app.services.user import UserService

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
)


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
)
async def create_user(
    data: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Регистрация пользователя или получение существующего"""
    user = await service.get_or_create_user(
        chat_id=data.chat_id,
        username=data.username,
    )
    return UserResponse.model_validate(user)
