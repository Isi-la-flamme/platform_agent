import re
from datetime import UTC, datetime, timedelta, timezone, tzinfo
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
    optional_args = ("timezone",)
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
        tz = self._resolve_timezone(timezone_name)

        if tz is None:
            return f"Timezone inconnue: {timezone_name}"

        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z")

    def _resolve_timezone(self, timezone_name: str) -> tzinfo | None:
        if timezone_name.upper() == "UTC":
            return UTC

        offset_tz = self._parse_utc_offset(timezone_name)
        if offset_tz is not None:
            return offset_tz

        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return self._fallback_timezone(timezone_name)

    def _parse_utc_offset(self, timezone_name: str) -> timezone | None:
        normalized = timezone_name.strip().upper().replace(" ", "")
        match = re.fullmatch(r"(?:UTC|GMT)?([+-])(\d{1,2})(?::?(\d{2}))?", normalized)
        if not match:
            return None

        sign, hours_text, minutes_text = match.groups()
        hours = int(hours_text)
        minutes = int(minutes_text or "0")
        if hours > 14 or minutes > 59:
            return None

        delta = timedelta(hours=hours, minutes=minutes)
        if sign == "-":
            delta = -delta

        label = f"UTC{sign}{hours:02d}:{minutes:02d}"
        return timezone(delta, label)

    def _fallback_timezone(self, timezone_name: str) -> timezone | None:
        fallback_offsets = {
            "europe/paris": timezone(timedelta(hours=2), "UTC+02:00"),
        }
        return fallback_offsets.get(timezone_name.lower())
