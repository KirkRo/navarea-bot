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
