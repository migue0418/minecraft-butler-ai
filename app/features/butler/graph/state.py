from typing import TypedDict


class ButlerState(TypedDict):
    message: str
    intent: str
    doc_type: str
    retrieved_docs: list[dict]
    actions: list[dict]
