"""
Общий интерфейс для источника предупреждений NAVAREA/HYDRO.

Каждый источник умеет: fetch_raw() -- скачать сырой текст, и
parse(raw) -- превратить его в список отдельных сообщений.
Регистр источников (registry.py) знает какой источник отвечает
за какой район.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class ParsedWarning:
    area_code: str
    msg_number: Optional[str]      # например "392/25"
    category: Optional[str]        # например "GEN" или "16"
    issued_at_raw: Optional[str]   # например "242359Z JUN 25" (как в тексте, без парсинга в datetime)
    region: Optional[str]          # например "NORTH PACIFIC"
    raw_text: str                  # полный текст сообщения целиком
    cancels: list[str]             # номера сообщений, которые это сообщение отменяет
    # Готовая геометрия от источника (Sealagom отдаёт размеченные полигоны и
    # полосы). None -- источник геометрию не даёт, разбираем текст сами.
    shapes: list[dict] | None = None


class WarningSource(Protocol):
    """Протокол, которому должен соответствовать любой источник."""

    source_id: str          # короткое имя источника, например "nga"
    covers_areas: list[str]  # какие NAVAREA/HYDRO коды отдаёт этот источник

    async def fetch_raw(self, area_code: str) -> str:
        """Скачать сырой текст для данного района."""
        ...

    def parse(self, area_code: str, raw_text: str) -> list[ParsedWarning]:
        """Разобрать сырой текст на отдельные сообщения."""
        ...


class FallbackSource:
    """Пробует primary; если он прямо сейчас недоступен (сеть, 4xx/5xx,
    что угодно) -- прозрачно переходит на fallback. parse() потом
    использует тот же источник, который реально ответил на fetch_raw()."""

    def __init__(self, primary: WarningSource, fallback: WarningSource):
        self._primary = primary
        self._fallback = fallback
        self._last_used: WarningSource = primary
        self.source_id = f"{primary.source_id}(+{fallback.source_id} fallback)"
        self.covers_areas = primary.covers_areas

    async def fetch_raw(self, area_code: str) -> str:
        try:
            raw = await self._primary.fetch_raw(area_code)
            self._last_used = self._primary
            return raw
        except Exception:
            raw = await self._fallback.fetch_raw(area_code)
            self._last_used = self._fallback
            return raw

    def parse(self, area_code: str, raw_text: str) -> list[ParsedWarning]:
        return self._last_used.parse(area_code, raw_text)
