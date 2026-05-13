from typing import Any


class TextStatsTool:
    name = "text_stats"
    description = (
        "Compte les caracteres, mots et lignes d'un texte fourni par "
        "l'utilisateur."
    )
    args_schema = {
        "text": "Texte a analyser.",
    }
    return_direct = True
    trigger_words: tuple[str, ...] = (
        "compte",
        "nombre de mots",
        "nombre de caracteres",
        "nombre de caractères",
        "statistiques",
        "longueur",
    )

    async def execute(self, **kwargs: Any) -> str:
        text = str(kwargs.get("text", ""))
        words = text.split()
        lines = text.splitlines() or ([text] if text else [])

        return (
            f"Caracteres: {len(text)}; "
            f"Mots: {len(words)}; "
            f"Lignes: {len(lines)}"
        )
