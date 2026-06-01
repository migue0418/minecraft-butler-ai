import json as json_lib
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.features.auth.dependencies import get_authenticated_user
from app.features.butler.schemas import AskRequest, ButlerAction
from app.features.butler.service import ButlerService, get_butler_service
from app.features.butler.stt import transcribe_audio
from app.features.users.models import User

logger = logging.getLogger(__name__)

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
    world_context = req.world_context.model_dump() if req.world_context else None
    return await service.run(
        req.message,
        req.session_id,
        input_mode="text",
        world_context=world_context,
    )


@router.post(
    "/ask-voice",
    response_model=list[ButlerAction],
    response_model_exclude_none=True,
)
async def ask_voice(
    audio: UploadFile = File(...),
    session_id: str | None = Form(None),
    world_context: str | None = Form(None),
    _user: User = Depends(get_authenticated_user),
    service: ButlerService = Depends(get_butler_service),
) -> list[ButlerAction]:
    audio_bytes = await audio.read()
    try:
        transcript = transcribe_audio(audio_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    ctx_dict: dict | None = None
    if world_context:
        try:
            ctx_dict = json_lib.loads(world_context)
        except (json_lib.JSONDecodeError, ValueError):
            logger.warning("world_context malformado en ask-voice, se ignora")
    return await service.run(
        transcript,
        session_id,
        input_mode="voice",
        world_context=ctx_dict,
    )
