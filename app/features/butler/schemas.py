from pydantic import BaseModel


class AskRequest(BaseModel):
    message: str


class ButlerAction(BaseModel):
    type: str
    message: str
