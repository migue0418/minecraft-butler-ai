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

_MINECRAFT_SYSTEM_PROMPT_WITH_CONTEXT = (
    "Eres un asistente experto en Minecraft. "
    "Responde en español de forma concisa y útil. "
    "Usa el siguiente contexto recuperado de la base de conocimiento oficial de Minecraft "
    "para responder la pregunta. Si el contexto no es suficiente, responde con tu conocimiento general.\n\n"
    "{context}"
)


class IntentOutput(BaseModel):
    intent: Literal["question", "move", "speak"]
    doc_type: Literal["item", "mob", "mechanic", "none"] = "none"


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
                    "- speak: cualquier otro mensaje, saludos o conversación general\n\n"
                    "Además, si la intención es 'question', clasifica el tipo de documento más relevante:\n"
                    "- item: preguntas sobre ítems, objetos, herramientas, armaduras, recetas de crafteo\n"
                    "- mob: preguntas sobre mobs, criaturas, enemigos, animales\n"
                    "- mechanic: preguntas sobre mecánicas del juego, sistemas, survival, redstone\n"
                    "- none: si la intención no es 'question' o no aplica ningún tipo anterior"
                ),
            },
            {"role": "user", "content": state["message"]},
        ],
    )
    return {"intent": result.intent, "doc_type": result.doc_type}


async def retrieve_context(state: ButlerState) -> dict:
    from app.features.butler.rag import get_retriever

    retriever = get_retriever()
    doc_type_filter = state.get("doc_type", "none")
    if doc_type_filter == "none":
        doc_type_filter = None

    retrieved = retriever(state["message"], doc_type_filter=doc_type_filter)
    docs_as_dicts = [doc.model_dump() for doc in retrieved]
    return {"retrieved_docs": docs_as_dicts}


async def answer_question(state: ButlerState) -> dict:
    llm = get_llm("responder")

    retrieved_docs = state.get("retrieved_docs", [])
    if retrieved_docs:
        from app.features.butler.rag.retriever import build_context
        from app.features.butler.rag.schemas import RetrievedDoc

        docs = [RetrievedDoc(**d) for d in retrieved_docs]
        context = build_context(docs)
        system_prompt = _MINECRAFT_SYSTEM_PROMPT_WITH_CONTEXT.format(context=context)
    else:
        system_prompt = _MINECRAFT_SYSTEM_PROMPT

    response = await llm.ainvoke(
        [
            {"role": "system", "content": system_prompt},
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
