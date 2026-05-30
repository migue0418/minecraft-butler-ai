from typing import Literal

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from app.core.settings import get_settings
from app.features.butler.graph.state import ButlerState

_CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
_RESPONDER_MODEL = "claude-sonnet-4-6"

_MINECRAFT_SYSTEM_PROMPT = (
    "Eres un asistente experto en Minecraft. "
    "Responde en español de forma concisa y útil. "
    "Cuando el usuario pregunte sobre crafteo, mecánicas, objetos o estrategias, "
    "proporciona respuestas precisas y directas."
)


class IntentOutput(BaseModel):
    intent: Literal["question", "move", "speak"]


def _get_llm(model: str) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=model,
        api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
    )


async def classify_intent(state: ButlerState) -> dict:
    llm = _get_llm(_CLASSIFIER_MODEL).with_structured_output(IntentOutput)
    result: IntentOutput = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "Clasifica la intención del usuario de Minecraft en una de estas categorías:\n"
                    "- question: preguntas sobre el juego, crafteo, mecánicas, objetos, estrategias\n"
                    "- move: instrucciones de movimiento o desplazamiento con coordenadas\n"
                    "- speak: cualquier otro mensaje, saludos o conversación general"
                ),
            },
            {"role": "user", "content": state["message"]},
        ],
    )
    return {"intent": result.intent}


async def answer_question(state: ButlerState) -> dict:
    llm = _get_llm(_RESPONDER_MODEL)
    response = await llm.ainvoke(
        [
            {"role": "system", "content": _MINECRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": state["message"]},
        ],
    )
    return {
        "actions": [{"type": "speak", "message": str(response.content)}],
    }


async def speak_action(state: ButlerState) -> dict:
    return {
        "actions": [{"type": "speak", "message": state["message"]}],
    }


async def move_action(state: ButlerState) -> dict:
    import re

    pattern = re.compile(r"(-?\d+)\s+(-?\d+)\s+(-?\d+)")
    match = pattern.search(state["message"])
    if match:
        x, y, z = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return {
            "actions": [
                {
                    "type": "move_to_position",
                    "message": "Me dirijo allí.",
                    "x": x,
                    "y": y,
                    "z": z,
                },
            ],
        }
    return {
        "actions": [
            {"type": "speak", "message": "No he podido detectar las coordenadas."},
        ],
    }
