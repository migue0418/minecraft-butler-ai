from app.features.butler.graph import compile_graph
from app.features.butler.schemas import ButlerAction

_graph = compile_graph()


class ButlerService:
    async def run(self, message: str) -> list[ButlerAction]:
        state = await _graph.ainvoke(
            {
                "message": message,
                "intent": "",
                "doc_type": "none",
                "retrieved_docs": [],
                "actions": [],
            },
        )
        return [ButlerAction(**action) for action in state["actions"]]


def get_butler_service() -> ButlerService:
    return ButlerService()
