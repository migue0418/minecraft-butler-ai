from app.features.butler.graph.state import ButlerState

_INTENT_TO_NODE: dict[str, str] = {
    "question": "retrieve_context",
    "move": "move_action",
    "speak": "speak_action",
}


def route_intent(state: ButlerState) -> str:
    return _INTENT_TO_NODE.get(state["intent"], "speak_action")
