import re
from html import unescape
from typing import Any

import httpx


class WebFetchTool:
    name = "web_fetch"
    description = (
        "Lit une page web publique via une URL HTTP ou HTTPS et retourne son "
        "contenu texte tronque."
    )
    args_schema = {
        "url": "URL HTTP ou HTTPS a consulter.",
    }
    return_direct = True
    trigger_words: tuple[str, ...] = (
        "internet",
        "web",
        "url",
        "site",
        "page",
        "http://",
        "https://",
        "consulte",
        "cherche",
    )

    _max_response_bytes = 500_000
    _max_output_chars = 4_000

    async def execute(self, **kwargs: Any) -> str:
        url = str(kwargs.get("url", "")).strip()
        if not url:
            return "URL manquante."
        if not url.startswith(("http://", "https://")):
            return "URL refusee: utilise http:// ou https://."

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=10.0,
                headers={"User-Agent": "agent-platform/0.1"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return f"Erreur HTTP {exc.response.status_code}: {url}"
        except httpx.RequestError as exc:
            return f"Erreur reseau: {exc}"

        content = response.content[: self._max_response_bytes]
        content_type = response.headers.get("content-type", "")
        text = content.decode(response.encoding or "utf-8", errors="replace")

        if "html" in content_type.lower() or "<html" in text[:500].lower():
            text = self._html_to_text(text)

        return self._truncate(text.strip())

    def _html_to_text(self, html: str) -> str:
        without_scripts = re.sub(
            r"(?is)<(script|style).*?>.*?</\1>",
            " ",
            html,
        )
        without_tags = re.sub(r"(?s)<[^>]+>", " ", without_scripts)
        normalized = re.sub(r"\s+", " ", unescape(without_tags))
        return normalized.strip()

    def _truncate(self, text: str) -> str:
        if not text:
            return "Page vide."
        if len(text) <= self._max_output_chars:
            return text
        return f"{text[: self._max_output_chars]}\n...[sortie tronquee]"
