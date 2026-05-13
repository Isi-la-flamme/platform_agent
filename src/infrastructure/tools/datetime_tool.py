from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class DateTimeTool:
    name = "datetime"
    description = (
        "Donne la date et l'heure actuelles. Utilise UTC par defaut ou un "
        "timezone IANA comme Europe/Paris si fourni."
    )
    args_schema = {
        "timezone": "Optionnel. Timezone IANA, exemple: UTC ou Europe/Paris.",
    }
    return_direct = True
    trigger_words: tuple[str, ...] = (
        "heure",
        "date",
        "aujourd'hui",
        "maintenant",
        "today",
        "time",
    )

    async def execute(self, **kwargs: Any) -> str:
        timezone_name = str(kwargs.get("timezone", "UTC") or "UTC").strip()

        try:
            tz = UTC if timezone_name.upper() == "UTC" else ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return f"Timezone inconnue: {timezone_name}"

        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z")
