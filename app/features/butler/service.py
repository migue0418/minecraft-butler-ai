import re
from collections.abc import AsyncIterator
from uuid import uuid4

from langchain_core.messages import HumanMessage

from app.features.butler.graph.graph import get_compiled_graph
from app.features.butler.schemas import ButlerAction

_BOUNDARY = re.compile(r"(?<=[.!?])\s+|(?<=\n)")

_RESPONDER_NODES = {"speak_action", "answer_question"}


def _flush_at_boundaries(text: str) -> tuple[list[str], str]:
    """Divide text en chunks en fronteras naturales (fin de frase, salto de línea).

    Devuelve (chunks_completos, resto_sin_frontera).
    Si no hay frontera, devuelve ([], text).
    """
    parts = _BOUNDARY.split(text)
    if len(parts) <= 1:
        return [], text
    return parts[:-1], parts[-1]


class ButlerService:
    async def run(
        self,
        message: str,
        session_id: str | None = None,
        input_mode: str = "text",
        world_context: dict | None = None,
    ) -> list[ButlerAction]:
        graph = await get_compiled_graph()
        thread_id = session_id or f"ephemeral-{uuid4()}"
        config = {"configurable": {"thread_id": thread_id}}
        state = await graph.ainvoke(
            {
                "message": message,
                "messages": [
                    HumanMessage(content=message, metadata={"input_mode": input_mode}),
                ],
                "intent": "",
                "doc_type": "none",
                "retrieved_docs": [],
                "actions": [],
                "input_mode": input_mode,
                "world_context": world_context,
                "needs_world_context": False,
            },
            config=config,
        )
        return [ButlerAction(**action) for action in state["actions"]]

    async def stream(
        self,
        message: str,
        session_id: str | None = None,
        input_mode: str = "text",
        world_context: dict | None = None,
    ) -> AsyncIterator[ButlerAction]:
        graph = await get_compiled_graph()
        thread_id = session_id or f"ephemeral-{uuid4()}"
        config = {
            "configurable": {"thread_id": thread_id},
            "run_name": f"butler-{input_mode}-stream",
            "metadata": {"session_id": thread_id, "input_mode": input_mode},
        }
        initial_state = {
            "message": message,
            "messages": [
                HumanMessage(content=message, metadata={"input_mode": input_mode}),
            ],
            "intent": "",
            "doc_type": "none",
            "retrieved_docs": [],
            "actions": [],
            "input_mode": input_mode,
            "world_context": world_context,
            "needs_world_context": False,
        }

        token_buffer: list[str] = []

        async for event in graph.astream_events(initial_state, config, version="v2"):
            etype: str = event.get("event", "")
            node: str = event.get("metadata", {}).get("langgraph_node", "")

            # Resetear buffer si el nodo responder reintenta (protección ante retry)
            if etype == "on_chain_start" and node in _RESPONDER_NODES:
                token_buffer = []

            # Capturar tokens del LLM de los nodos que generan texto
            elif etype == "on_chat_model_stream" and node in _RESPONDER_NODES:
                content: str = event["data"]["chunk"].content
                if not content:
                    continue
                token_buffer.append(content)
                chunks, remainder = _flush_at_boundaries("".join(token_buffer))
                for chunk in chunks:
                    if chunk.strip():
                        yield ButlerAction(type="speak", message=chunk.strip())
                token_buffer = [remainder] if remainder else []

            # Vaciar buffer al terminar el nodo
            elif etype == "on_chain_end" and node in _RESPONDER_NODES:
                rest = "".join(token_buffer).strip()
                if rest:
                    yield ButlerAction(type="speak", message=rest)
                token_buffer = []

            # Acciones no-LLM (move_to_position) desde el estado de salida del nodo
            elif etype == "on_chain_end" and node == "move_action":
                output = event.get("data", {}).get("output", {})
                for action in output.get("actions", []):
                    yield ButlerAction(**action)


def get_butler_service() -> ButlerService:
    return ButlerService()
