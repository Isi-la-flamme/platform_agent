from typing import List, Optional
from pydantic import BaseModel, Field

class Task(BaseModel):
    """Une étape spécifique d'un plan complexe."""
    description: str = Field(..., description="Description de la tâche")
    status: str = Field("pending", pattern="^(pending|in_progress|completed|failed)$")
    result: Optional[str] = None

class Plan(BaseModel):
    """Un ensemble de tâches pour atteindre un objectif persistant."""
    goal: str = Field(..., description="Objectif final de l'agent")
    tasks: List[Task] = Field(default_factory=list)
    current_step: int = 0