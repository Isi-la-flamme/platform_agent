import os
import httpx
from typing import Any

class GoogleSearchTool:
    """
    Outil de recherche Google utilisant l'API SerpApi.
    Necessite une clef API SERPAPI_API_KEY dans les variables d'environnement.
    """
    name = "google_search"
    description = (
        "Effectue une recherche sur Google pour trouver des informations d'actualite, "
        "des faits ou des donnees recentes. Retourne une liste de resultats avec titres et extraits."
    )
    args_schema = {
        "query": "La requete de recherche (mots-cles).",
    }
    return_direct = False  # L'agent doit traiter les resultats avant de repondre
    trigger_words: tuple[str, ...] = ("cherche", "google", "recherche", "search", "trouve")

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")

    async def execute(self, **kwargs: Any) -> str:
        query = str(kwargs.get("query", "")).strip()
        if not query:
            return "Erreur : Requete vide."

        if not self.api_key:
            return "Erreur : Clef API SerpApi manquante (SERPAPI_API_KEY non configuree)."

        params = {
            "q": query,
            "api_key": self.api_key,
            "engine": "google",
            "num": 5
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("https://serpapi.com/search", params=params)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            return f"Echec de la recherche : {str(e)}"

        results = []
        
        # Gestion de la 'Answer Box' (reponse directe Google si disponible)
        if "answer_box" in data:
            ab = data["answer_box"]
            answer = ab.get("answer") or ab.get("snippet") or ab.get("title")
            if answer:
                results.append(f"REPONSE DIRECTE : {answer}")

        # Resultats organiques
        organic = data.get("organic_results", [])
        for i, res in enumerate(organic[:5]):
            title = res.get("title", "Sans titre")
            snippet = res.get("snippet", "")
            link = res.get("link", "")
            results.append(f"[{i+1}] {title}\nExtrait : {snippet}\nSource : {link}")

        if not results:
            return f"Aucun resultat trouve pour '{query}'."

        return "\n\n".join(results)