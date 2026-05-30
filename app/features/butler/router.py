from fastapi import APIRouter, Depends

from app.features.auth.dependencies import get_authenticated_user
from app.features.butler.schemas import AskRequest, ButlerAction
from app.features.butler.service import ButlerService, get_butler_service
from app.features.users.models import User

router = APIRouter(prefix="/api/butler", tags=["Butler"])


@router.post(
    "/ask",
    response_model=list[ButlerAction],
    response_model_exclude_none=True,
)
async def ask(
    req: AskRequest,
    _user: User = Depends(get_authenticated_user),
    service: ButlerService = Depends(get_butler_service),
) -> list[ButlerAction]:
    return await service.run(req.message)
