from __future__ import annotations

import asyncio

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.features.butler.graph.nodes import (
    answer_question,
    classify_intent,
    move_action,
    retrieve_context,
    speak_action,
)
from app.features.butler.graph.routing import route_intent
from app.features.butler.graph.state import ButlerState

_compiled_graph = None
_graph_lock = asyncio.Lock()


def compile_graph(checkpointer: BaseCheckpointSaver | None = None):
    builder = StateGraph(ButlerState)

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("answer_question", answer_question)
    builder.add_node("speak_action", speak_action)
    builder.add_node("move_action", move_action)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_intent,
        {
            "retrieve_context": "retrieve_context",
            "speak_action": "speak_action",
            "move_action": "move_action",
        },
    )
    builder.add_edge("retrieve_context", "answer_question")
    builder.add_edge("answer_question", END)
    builder.add_edge("speak_action", END)
    builder.add_edge("move_action", END)

    return builder.compile(checkpointer=checkpointer)


async def get_compiled_graph():
    """Devuelve el grafo compilado con checkpointer Redis, inicializándolo una vez.

    Usa un asyncio.Lock para evitar doble inicialización bajo concurrencia.
    En tests se puede sustituir llamando a compile_graph(MemorySaver()) directamente.
    """
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph
    async with _graph_lock:
        if _compiled_graph is None:
            from app.core.settings import get_settings

            settings = get_settings()
            from langgraph.checkpoint.redis.aio import AsyncRedisSaver

            ttl_minutes = max(1, settings.redis_session_ttl_seconds // 60)
            saver = AsyncRedisSaver(
                redis_url=settings.redis_url,
                ttl={"default_ttl": ttl_minutes, "refresh_on_read": True},
            )
            await saver.asetup()
            _compiled_graph = compile_graph(checkpointer=saver)
    return _compiled_graph


def reset_compiled_graph() -> None:
    """Limpia el singleton. Solo para uso en tests."""
    global _compiled_graph
    _compiled_graph = None
