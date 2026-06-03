from collections.abc import AsyncIterator
from uuid import uuid4

from langchain_core.messages import HumanMessage

from app.features.butler.graph.graph import get_compiled_graph
from app.features.butler.schemas import ButlerAction


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
        sent = 0
        async for state in graph.astream(initial_state, config, stream_mode="values"):
            actions = state.get("actions", [])
            for action in actions[sent:]:
                yield ButlerAction(**action)
                sent += 1


def get_butler_service() -> ButlerService:
    return ButlerService()
