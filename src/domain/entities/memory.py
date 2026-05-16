from pydantic import BaseModel

class MemoryFact(BaseModel):
    """Entité représentant un fait stocké en mémoire long terme."""
    key: str
    value: str
    text: str