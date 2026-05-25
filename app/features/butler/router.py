import re

from fastapi import APIRouter, Depends

from app.features.auth.dependencies import get_authenticated_user
from app.features.butler.schemas import AskRequest, ButlerAction
from app.features.users.models import User

router = APIRouter(prefix="/api/butler", tags=["Butler"])

_COORD_RE = re.compile(r"(-?\d+)\s+(-?\d+)\s+(-?\d+)")


@router.post(
    "/ask",
    response_model=list[ButlerAction],
    response_model_exclude_none=True,
)
async def ask(
    req: AskRequest,
    _user: User = Depends(get_authenticated_user),
) -> list[ButlerAction]:
    match = _COORD_RE.search(req.message)
    if match:
        x, y, z = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return [
            ButlerAction(
                type="move_to_position",
                message="Me dirijo allí.",
                x=x,
                y=y,
                z=z,
            ),
        ]
    return [ButlerAction(type="speak", message=f"Hola! Recibí: {req.message}")]
