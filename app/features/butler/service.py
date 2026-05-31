from uuid import uuid4

from langchain_core.messages import HumanMessage

from app.features.butler.graph.graph import get_compiled_graph
from app.features.butler.schemas import ButlerAction


class ButlerService:
    async def run(
        self,
        message: str,
        session_id: str | None = None,
    ) -> list[ButlerAction]:
        graph = await get_compiled_graph()
        thread_id = session_id or f"ephemeral-{uuid4()}"
        config = {"configurable": {"thread_id": thread_id}}
        state = await graph.ainvoke(
            {
                "message": message,
                "messages": [HumanMessage(content=message)],
                "intent": "",
                "doc_type": "none",
                "retrieved_docs": [],
                "actions": [],
            },
            config=config,
        )
        return [ButlerAction(**action) for action in state["actions"]]


def get_butler_service() -> ButlerService:
    return ButlerService()
