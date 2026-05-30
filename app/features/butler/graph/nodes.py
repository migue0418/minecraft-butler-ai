from typing import Literal

from pydantic import BaseModel

from app.features.butler.graph.state import ButlerState
from app.features.butler.llm import get_llm

_MINECRAFT_SYSTEM_PROMPT = (
    "Eres un asistente experto en Minecraft. "
    "Responde en español de forma concisa y útil. "
    "Cuando el usuario pregunte sobre crafteo, mecánicas, objetos o estrategias, "
    "proporciona respuestas precisas y directas."
)


class IntentOutput(BaseModel):
    intent: Literal["question", "move", "speak"]


async def classify_intent(state: ButlerState) -> dict:
    llm = get_llm("classifier").with_structured_output(IntentOutput)
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
    llm = get_llm("responder")
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
