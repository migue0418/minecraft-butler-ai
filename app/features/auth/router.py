from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.features.auth.dependencies import get_authenticated_user
from app.features.auth.schemas import (
    AuthenticatedUserResponse,
    LoginRequest,
    SessionInfo,
    TokenResponse,
)
from app.features.auth.service import (
    AuthService,
    get_auth_service,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await service.login(payload, response, request)


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
async def token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await service.login(
        LoginRequest(
            username=form_data.username,
            password=form_data.password,
            remember_me=False,
        ),
        response,
        request,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await service.refresh(request, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> None:
    await service.logout(request, response)


@router.get("/me", response_model=AuthenticatedUserResponse)
async def me(
    user=Depends(get_authenticated_user),
    service: AuthService = Depends(get_auth_service),
) -> AuthenticatedUserResponse:
    return await service.me(user)


@router.get("/sessions", response_model=list[SessionInfo])
async def sessions(
    request: Request,
    user=Depends(get_authenticated_user),
    service: AuthService = Depends(get_auth_service),
) -> list[SessionInfo]:
    return await service.get_sessions(user, request)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: int,
    request: Request,
    response: Response,
    user=Depends(get_authenticated_user),
    service: AuthService = Depends(get_auth_service),
) -> None:
    await service.revoke_session(session_id, user, request, response)
