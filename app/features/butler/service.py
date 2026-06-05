import asyncio
import contextlib
import re
from collections.abc import AsyncIterator
from uuid import uuid4

from langchain_core.messages import HumanMessage

from app.features.butler.graph.graph import get_compiled_graph
from app.features.butler.schemas import ButlerAction

_BOUNDARY = re.compile(r"(?<=[.!?])\s+|(?<=\n)")

_RESPONDER_NODES = {"speak_action", "answer_question"}

# Centinela de fin de stream y tamaño de la cola productor→consumidor.
_STREAM_DONE = object()
_QUEUE_MAXSIZE = 32


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

    async def _run_graph_to_queue(
        self,
        queue: asyncio.Queue,
        message: str,
        session_id: str | None,
        input_mode: str,
        world_context: dict | None,
    ) -> None:
        """Productor: ejecuta el grafo en su propia task y empuja ButlerAction a la cola.

        Ejecutar astream_events íntegramente dentro de una sola task mantiene estable el
        contextvar del run padre de LangSmith, de modo que los nodos hijos del grafo quedan
        anidados en la traza en lugar de desvincularse (ver langsmith-sdk #817). El generador
        de StreamingResponse solo drena la cola, sin tocar el contexto de tracing.

        El troceado por frases es idéntico al original; solo cambia `yield` por `queue.put`.
        Las excepciones se propagan al consumidor a través de la cola; un centinela marca el fin.
        """
        try:
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

            async for event in graph.astream_events(
                initial_state,
                config,
                version="v2",
            ):
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
                            await queue.put(
                                ButlerAction(type="speak", message=chunk.strip()),
                            )
                    token_buffer = [remainder] if remainder else []

                # Vaciar buffer al terminar el nodo
                elif etype == "on_chain_end" and node in _RESPONDER_NODES:
                    rest = "".join(token_buffer).strip()
                    if rest:
                        await queue.put(ButlerAction(type="speak", message=rest))
                    token_buffer = []

                # Acciones no-LLM (move_to_position) desde el estado de salida del nodo
                elif etype == "on_chain_end" and node == "move_action":
                    output = event.get("data", {}).get("output", {})
                    for action in output.get("actions", []):
                        await queue.put(ButlerAction(**action))
        except Exception as exc:  # noqa: BLE001 - se propaga al consumidor por la cola
            await queue.put(exc)
        # CancelledError (BaseException) no se captura: propaga y omite el centinela,
        # evitando un await bloqueante en una cola llena durante la cancelación.
        await queue.put(_STREAM_DONE)

    async def stream(
        self,
        message: str,
        session_id: str | None = None,
        input_mode: str = "text",
        world_context: dict | None = None,
    ) -> AsyncIterator[ButlerAction]:
        """Consumidor: drena la cola que alimenta la task productora del grafo.

        Mantener la ejecución del grafo fuera de este generador (que consume
        StreamingResponse) preserva el árbol de nodos en las trazas de LangSmith.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        producer = asyncio.create_task(
            self._run_graph_to_queue(
                queue,
                message,
                session_id,
                input_mode,
                world_context,
            ),
        )
        try:
            while True:
                item = await queue.get()
                if item is _STREAM_DONE:
                    break
                if isinstance(item, BaseException):
                    raise item
                yield item
        finally:
            if not producer.done():
                producer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await producer


def get_butler_service() -> ButlerService:
    return ButlerService()
