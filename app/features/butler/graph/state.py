from typing import TypedDict


class ButlerState(TypedDict):
    message: str
    intent: str
    actions: list[dict]
