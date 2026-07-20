"""
Источник UKHO (United Kingdom Hydrographic Office) -- координатор NAVAREA I
(северо-восточная Атлантика, Северное море, Ла-Манш).

Страница отдаёт готовый HTML со таблицей предупреждений, без блокировки
в robots.txt и без обязательного JS для получения данных:

    https://msi.admiralty.co.uk/RadioNavigationalWarnings

На той же странице вместе с NAVAREA I идут и британские прибрежные
предупреждения "UK Coastal" (WZ nnn/yy) -- полезно, если судно работает
у берегов Британии, поэтому парсер отдаёт оба типа с пометкой series.

ВАЖНО: сам UKHO прямо пишет, что этот сайт не заменяет получение MSI через
штатное оборудование GMDSS/NAVTEX -- бот должен использовать эту информацию
только как дополнительное удобство.
"""
from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from .base import ParsedWarning

URL = "https://msi.admiralty.co.uk/RadioNavigationalWarnings"

# Совмещённая строка таблицы после схлопывания тегов выглядит примерно так:
#   "NAVAREA 1NAVAREA I 143/26141602 UTC Jul 26 GMDSS. SOUTHWEST ... CANCEL THIS MSG 151800 UTC JUL 2026."
#   "UK CoastalWZ 437/26131307 UTC Jul 26 SOLE. PLYMOUTH. ... CANCEL THIS MSG 161800 UTC JUL 2026."
_ROW_HEADER = re.compile(
    r"""^\s*
    (?P<series>NAVAREA\s*1|UK\s*Coastal)\s*
    (?P<label>NAVAREA\s*[I1]+\s*\d+/\d{2,4}|WZ\s*\d+/\d{2,4})
    \s*(?P<dtg>\d{6}\s*UTC\s*[A-Za-z]{3}\s*\d{2,4})\s*
    """,
    re.VERBOSE | re.IGNORECASE,
)

_CANCEL_REF = re.compile(r"CANCEL\s+(?:NAVAREA\s*[I1]+\s*|WZ\s*)?(\d+/\d{2,4})", re.IGNORECASE)

_REGION = re.compile(r"^([A-Z][A-Z0-9 ,.\-]{2,70}?)\.\s")


def parse_rows(row_texts: list[str]) -> list[ParsedWarning]:
    """row_texts -- список текстов уже схлопнутых строк таблицы (одна строка = один <tr>.get_text())."""
    results: list[ParsedWarning] = []
    for row in row_texts:
        row = " ".join(row.split())  # нормализуем пробелы/переносы
        m = _ROW_HEADER.match(row)
        if not m:
            continue

        body = row[m.end():].strip()
        if not body:
            continue

        series = m.group("series").upper().replace(" ", "")
        area_code = "I" if series == "NAVAREA1" else "I-COASTAL"

        label = re.sub(r"\s+", " ", m.group("label")).strip()
        msgnum_match = re.search(r"(\d+/\d{2,4})", label)
        msgnum = msgnum_match.group(1) if msgnum_match else None

        region_match = _REGION.match(body)
        region = region_match.group(1).strip() if region_match else None

        cancels = _CANCEL_REF.findall(body)

        results.append(
            ParsedWarning(
                area_code=area_code,
                msg_number=msgnum,
                category=None,
                issued_at_raw=m.group("dtg"),
                region=region,
                raw_text=row,
                cancels=cancels,
            )
        )
    return results


class UkhoSource:
    source_id = "ukho"
    covers_areas = ["I", "I-COASTAL"]

    def __init__(self, timeout: float = 20.0):
        self._timeout = timeout

    async def fetch_raw(self, area_code: str) -> str:
        headers = {"User-Agent": "navarea-bot/1.0 (personal non-commercial NAVAREA warnings monitor)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(URL)
            resp.raise_for_status()
            return resp.text

    def parse(self, area_code: str, raw_html: str) -> list[ParsedWarning]:
        soup = BeautifulSoup(raw_html, "lxml")
        row_texts = [tr.get_text(" ", strip=True) for tr in soup.find_all("tr")]
        all_parsed = parse_rows(row_texts)
        return [w for w in all_parsed if w.area_code == area_code]
