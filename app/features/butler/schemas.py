from pydantic import BaseModel


class AskRequest(BaseModel):
    message: str
    session_id: str | None = None


class ButlerAction(BaseModel):
    type: str
    message: str
    x: int | None = None
    y: int | None = None
    z: int | None = None
