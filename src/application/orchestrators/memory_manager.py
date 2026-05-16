import re
from src.domain.protocols.memory import LongTermMemory

class MemoryManager:
    """Gère l'extraction de faits et la récupération de données personnelles."""
    
    def __init__(self, memory: LongTermMemory | None) -> None:
        self.memory = memory
        self._patterns = (
            r"\bmon nom est\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '’-]{1,60})",
            r"\bje m'appelle\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '’-]{1,60})",
            r"\bappelle-moi\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '’-]{1,60})",
        )

    def learn_facts(self, user_input: str) -> None:
        if not self.memory:
            return

        for pattern in self._patterns:
            match = re.search(pattern, user_input, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(" .,!?:;")
                if name:
                    self.memory.remember(
                        key="user.name",
                        value=name,
                        text=f"Le nom de l'utilisateur est {name}."
                    )
                    return

    def answer_from_memory(self, user_input: str) -> str | None:
        if not self.memory:
            return None

        normalized = user_input.lower()
        asks_name = any(k in normalized for k in ["mon nom", "qui suis-je", "m'appelle comment"])
        
        if not asks_name:
            return None

        name = self.memory.get("user.name")
        if not name:
            return "Je ne connais pas encore ton nom."

        return f"Ton nom est {name.value}."