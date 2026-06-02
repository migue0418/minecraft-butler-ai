from pydantic import BaseModel


class ItemEntry(BaseModel):
    item: str
    count: int


class PlayerContext(BaseModel):
    inventory: list[ItemEntry] = []
    x: int
    y: int
    z: int


class ChestContext(BaseModel):
    name: str
    items: list[ItemEntry] = []


class AnimalGroup(BaseModel):
    type: str
    count: int


class MonsterGroup(BaseModel):
    type: str
    count: int


class CropGroup(BaseModel):
    type: str
    mature: int
    growing: int


class NearbyContext(BaseModel):
    animals: list[AnimalGroup] = []
    monsters: list[MonsterGroup] = []
    crops: list[CropGroup] = []


class WorldContextDTO(BaseModel):
    player: PlayerContext
    chests: list[ChestContext] = []
    nearby: NearbyContext


class AskRequest(BaseModel):
    message: str
    session_id: str | None = None
    world_context: WorldContextDTO | None = None


class ButlerAction(BaseModel):
    type: str
    message: str
    x: int | None = None
    y: int | None = None
    z: int | None = None
