from fastapi import APIRouter, Depends

from app.features.auth.dependencies import get_authenticated_user
from app.features.butler.schemas import AskRequest, ButlerAction
from app.features.users.models import User

router = APIRouter(prefix="/api/butler", tags=["Butler"])


@router.post("/ask", response_model=list[ButlerAction])
async def ask(
    req: AskRequest,
    _user: User = Depends(get_authenticated_user),
) -> list[ButlerAction]:
    return [ButlerAction(type="speak", message=f"Hola! Recibí: {req.message}")]
