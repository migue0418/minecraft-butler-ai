from typing import Literal

from langchain_core.messages import AIMessage
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
    needs_world_context: bool = False


def format_world_context(ctx: dict) -> str:
    lines = ["Contexto del mundo del jugador:"]

    player = ctx.get("player", {})
    if player:
        lines.append(
            f"- Posición: ({player.get('x', '?')}, {player.get('y', '?')}, {player.get('z', '?')})",
        )
        inv = sorted(
            player.get("inventory", []),
            key=lambda e: e.get("count", 0),
            reverse=True,
        )
        if inv:
            top = inv[:10]
            inv_str = ", ".join(f"{e['count']}× {e['item']}" for e in top)
            if len(inv) > 10:
                inv_str += f" (y {len(inv) - 10} tipos más)"
            lines.append(f"- Inventario: {inv_str}")

    for chest in ctx.get("chests", []):
        items = sorted(
            chest.get("items", []),
            key=lambda e: e.get("count", 0),
            reverse=True,
        )[:5]
        if items:
            items_str = ", ".join(f"{i['count']}× {i['item']}" for i in items)
            lines.append(f'- Cofre "{chest["name"]}": {items_str}')
        else:
            lines.append(f'- Cofre "{chest["name"]}": vacío')

    nearby = ctx.get("nearby", {})
    monsters = nearby.get("monsters", [])[:5]
    if monsters:
        lines.append(
            "- Monstruos cercanos: "
            + ", ".join(f"{m['count']} {m['type']}" for m in monsters),
        )
    animals = nearby.get("animals", [])[:5]
    if animals:
        lines.append(
            "- Animales cercanos: "
            + ", ".join(f"{a['count']} {a['type']}" for a in animals),
        )

    crops = nearby.get("crops", [])
    if crops:
        crops_str = ", ".join(
            f"{c['type']} ({c['mature']} maduros, {c['growing']} creciendo)"
            for c in crops
        )
        lines.append(f"- Cultivos cercanos: {crops_str}")

    return "\n".join(lines)


def _build_system_prompt(base_prompt: str, state: ButlerState) -> str:
    if state.get("needs_world_context") and state.get("world_context"):
        ctx_text = format_world_context(state["world_context"])
        return base_prompt + "\n\n" + ctx_text
    return base_prompt


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
                    "- none: si la intención no es 'question' o no aplica ningún tipo anterior\n\n"
                    "También determina `needs_world_context`: true si la pregunta se refiere al estado "
                    "actual del mundo del jugador (su inventario, cofres, animales cercanos, cultivos), "
                    "false si es una pregunta general de conocimiento sobre Minecraft.\n"
                    "Ejemplos needs_world_context=true: '¿tengo hierro?', '¿qué hay en mis cofres?', "
                    "'¿están listos los cultivos?'\n"
                    "Ejemplos needs_world_context=false: '¿cómo crafteo una espada?', '¿qué dropea una vaca?'"
                ),
            },
            {"role": "user", "content": state["message"]},
        ],
    )
    return {
        "intent": result.intent,
        "doc_type": result.doc_type,
        "needs_world_context": result.needs_world_context,
    }


async def retrieve_context(state: ButlerState) -> dict:
    from app.features.butler.rag import get_retriever

    retriever = get_retriever()

    # No filtramos por doc_type. El clasificador (un LLM) infiere el tipo a partir
    # de palabras de la consulta y se equivoca en casos como "¿qué items dropea
    # una vaca?" (lo marca como item), donde el documento correcto es el del mob
    # Cow y un filtro duro lo excluiría. El retriever denso es cross-lingual y
    # selecciona el tipo correcto por semántica, así que confiamos en su ranking.
    retrieved = retriever(state["message"])
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
        base_system = _MINECRAFT_SYSTEM_PROMPT_WITH_CONTEXT.format(context=context)
    else:
        base_system = _MINECRAFT_SYSTEM_PROMPT

    system_prompt = _build_system_prompt(base_system, state)

    # Usar el historial acumulado de mensajes para dar contexto multi-turn al LLM.
    history = state.get("messages", [])
    response = await llm.ainvoke(
        [{"role": "system", "content": system_prompt}, *history],
    )
    ai_msg = AIMessage(content=str(response.content))
    return {
        "messages": [ai_msg],
        "actions": [{"type": "speak", "message": str(response.content)}],
    }


async def speak_action(state: ButlerState) -> dict:
    llm = get_llm("responder")
    history = state.get("messages", [])
    system = _build_system_prompt(_MINECRAFT_SYSTEM_PROMPT, state)
    response = await llm.ainvoke(
        [{"role": "system", "content": system}, *history],
    )
    ai_msg = AIMessage(content=str(response.content))
    return {
        "messages": [ai_msg],
        "actions": [{"type": "speak", "message": str(response.content)}],
    }


async def move_action(state: ButlerState) -> dict:
    import re

    pattern = re.compile(r"(-?\d+)\s+(-?\d+)\s+(-?\d+)")
    match = pattern.search(state["message"])
    if match:
        x, y, z = int(match.group(1)), int(match.group(2)), int(match.group(3))
        msg = "Me dirijo allí."
        return {
            "messages": [AIMessage(content=msg)],
            "actions": [
                {
                    "type": "move_to_position",
                    "message": msg,
                    "x": x,
                    "y": y,
                    "z": z,
                },
            ],
        }
    msg = "No he podido detectar las coordenadas."
    return {
        "messages": [AIMessage(content=msg)],
        "actions": [{"type": "speak", "message": msg}],
    }
