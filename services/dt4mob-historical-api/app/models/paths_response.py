from pydantic import BaseModel
from app.models.util import Action



class PathResponseObject(BaseModel):
    path: str
    action: Action

    model_config = {"from_attributes": True}