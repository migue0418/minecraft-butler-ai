import asyncio
import json as json_lib
import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from app.core.limiter import limiter
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
@limiter.limit("20/minute")
async def ask(
    req: AskRequest,
    request: Request,
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
@limiter.limit("20/minute")
async def ask_voice(
    request: Request,
    audio: UploadFile = File(...),
    session_id: str | None = Form(None),
    world_context: str | None = Form(None),
    _user: User = Depends(get_authenticated_user),
    service: ButlerService = Depends(get_butler_service),
) -> list[ButlerAction]:
    audio_bytes = await audio.read()
    try:
        transcript = await asyncio.to_thread(transcribe_audio, audio_bytes)
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


def _sse(data: str) -> str:
    return f"data: {data}\n\n"


@router.post("/ask-stream")
@limiter.limit("20/minute")
async def ask_stream(
    req: AskRequest,
    request: Request,
    _user: User = Depends(get_authenticated_user),
    service: ButlerService = Depends(get_butler_service),
) -> StreamingResponse:
    world_context = req.world_context.model_dump() if req.world_context else None

    async def generate():
        yield _sse(json_lib.dumps({"type": "echo", "message": f"[Tú] {req.message}"}))
        async for action in service.stream(
            req.message,
            req.session_id,
            input_mode="text",
            world_context=world_context,
        ):
            yield _sse(json_lib.dumps(action.model_dump(exclude_none=True)))
        yield _sse("[DONE]")

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/ask-voice-stream")
@limiter.limit("20/minute")
async def ask_voice_stream(
    request: Request,
    audio: UploadFile = File(...),
    session_id: str | None = Form(None),
    world_context: str | None = Form(None),
    _user: User = Depends(get_authenticated_user),
    service: ButlerService = Depends(get_butler_service),
) -> StreamingResponse:
    audio_bytes = await audio.read()
    try:
        transcript = await asyncio.to_thread(transcribe_audio, audio_bytes)
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
            logger.warning("world_context malformado en ask-voice-stream, se ignora")

    async def generate():
        yield _sse(
            json_lib.dumps(
                {"type": "echo", "message": f"[Tú] \U0001f3a4 {transcript}"},
            ),
        )
        async for action in service.stream(
            transcript,
            session_id,
            input_mode="voice",
            world_context=ctx_dict,
        ):
            yield _sse(json_lib.dumps(action.model_dump(exclude_none=True)))
        yield _sse("[DONE]")

    return StreamingResponse(generate(), media_type="text/event-stream")
