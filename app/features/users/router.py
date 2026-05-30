from fastapi import APIRouter, Depends, Path, Response, status

from app.features.auth.dependencies import get_authenticated_user, require_roles
from app.features.users.schemas import (
    AdminResetPasswordRequest,
    ChangeOwnPasswordRequest,
    CreateUserRequest,
    UpdateUserRequest,
    UserDetailResponse,
    UserResponse,
)
from app.features.users.service import UsersService, get_users_service

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    _: object = Depends(require_roles("admin")),
    service: UsersService = Depends(get_users_service),
) -> list[UserResponse]:
    return await service.list_users()


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int = Path(..., gt=0),
    _: object = Depends(require_roles("admin")),
    service: UsersService = Depends(get_users_service),
) -> UserDetailResponse:
    return await service.get_user(user_id)


@router.post(
    "",
    response_model=UserDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: CreateUserRequest,
    _: object = Depends(require_roles("admin")),
    service: UsersService = Depends(get_users_service),
) -> UserDetailResponse:
    return await service.create_user(payload)


@router.put("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: int = Path(..., gt=0),
    payload: UpdateUserRequest = ...,
    _: object = Depends(require_roles("admin")),
    service: UsersService = Depends(get_users_service),
) -> UserDetailResponse:
    return await service.update_user(user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int = Path(..., gt=0),
    _: object = Depends(require_roles("admin")),
    service: UsersService = Depends(get_users_service),
) -> Response:
    await service.delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_own_password(
    payload: ChangeOwnPasswordRequest,
    current_user=Depends(get_authenticated_user),
    service: UsersService = Depends(get_users_service),
) -> Response:
    await service.change_own_password(current_user, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: int = Path(..., gt=0),
    payload: AdminResetPasswordRequest = ...,
    _: object = Depends(require_roles("admin")),
    service: UsersService = Depends(get_users_service),
) -> Response:
    await service.reset_password(user_id, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
