from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class ButlerState(TypedDict):
    message: str
    intent: str
    doc_type: str
    retrieved_docs: list[dict]
    actions: list[dict]
    messages: Annotated[list[AnyMessage], add_messages]
    input_mode: str  # "text" | "voice"
    world_context: dict | None
    needs_world_context: bool
