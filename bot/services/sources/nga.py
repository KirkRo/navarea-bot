"""
Источник NGA (National Geospatial-Intelligence Agency, США).

NGA официально координирует NAVAREA IV и NAVAREA XII, плюс публикует
свои региональные HYDROLANT/HYDROPAC предупреждения, через "Daily
Memorandum" файлы:

    https://msi.nga.mil/api/publications/download?type=view&key=16694640/SFH00000/DailyMemIV.txt
    https://msi.nga.mil/api/publications/download?type=view&key=16694640/SFH00000/DailyMemXII.txt
    https://msi.nga.mil/api/publications/download?type=view&key=16694640/SFH00000/DailyMemLAN.txt   (HYDROLANT)
    https://msi.nga.mil/api/publications/download?type=view&key=16694640/SFH00000/DailyMemPAC.txt   (HYDROPAC)

Реальный формат файла (уточнён по фрагменту, который прислал пользователь,
после чего парсер был переписан и перепроверен на нём):

    NAVAREA IV 700/2026 (11)


    191320Z JUL 26
    NAVAREA IV 700/26.
    GULF OF AMERICA.
    1. SURVEY OPERATIONS IN PROGRESS UNTIL 30 SEP
       BY M/V ISLAND FRONTIER IN AREA BOUND BY
       ...
    2. CANCEL THIS MSG 010001Z OCT 26.


    /
    NAVAREA IV 699/2026 (null)
    ...

То есть каждое сообщение открывается строкой-заголовком вида
"NAVAREA <район> <номер>/<год> (<категория или null>)" на отдельной
строке, дальше идёт сам текст (дата, повторно номер, регион, пункты),
и заканчивается блок одиночной "/" на отдельной строке перед следующим
заголовком. Категория бывает числом, списком чисел через запятую или
словом "null". У части сообщений 2021-2022 годов перед номером идёт
служебная шапка "MSGID/GENADMIN/..." -- это не мешает, парсер ищет
нужные строки по содержимому, а не по номеру строки.

Сообщение вида "NAVAREA IV WARNINGS IN FORCE AS OF ..." -- служебная
сводка со списком всех номеров, а не отдельное предупреждение, поэтому
не сохраняется как предупреждение (иначе выглядело бы как стена из
полутора сотен номеров вместо конкретной опасности).

ВАЖНО: это неофициальный, разобранный вручную формат. Он может немного
поменяться на стороне NGA. Официальный способ получения предупреждений
для мореплавания -- штатное оборудование GMDSS/NAVTEX на судне. Этот бот
даёт только дополнительное удобство (push-уведомление и быстрый поиск),
как и написано в самом файле NGA.
"""
from __future__ import annotations

import re
from typing import Optional

import httpx

from .base import ParsedWarning

_DAILY_MEMO_KEYS = {
    "IV": "16694640/SFH00000/DailyMemIV.txt",
    "XII": "16694640/SFH00000/DailyMemXII.txt",
    "HYDROLANT": "16694640/SFH00000/DailyMemLAN.txt",
    "HYDROPAC": "16694640/SFH00000/DailyMemPAC.txt",
}

_BASE_URL = "https://msi.nga.mil/api/publications/download"

# Заголовок блока -- ОБЯЗАТЕЛЬНО в начале строки (MULTILINE), например:
#   "NAVAREA IV 700/2026 (11)"
#   "NAVAREA IV 699/2026 (null)"
#   "HYDROPAC 1234/2026 (16, 17)"
_BLOCK_HEADER = re.compile(
    r"^(?:NAVAREA\s+(?P<series>[IVXLCDM]+)|(?P<hydro>HYDROLANT|HYDROPAC|HYDROARC))\s+"
    r"(?P<msgnum>\d+)/(?P<year>\d{4})\s*\((?P<category>[^)]*)\)\s*$",
    re.MULTILINE,
)

# Строка с номером и точкой внутри текста, например "NAVAREA IV 700/26." или "NAVAREA IV 496/26(24)."
_REF_WITH_PERIOD = re.compile(r"NAVAREA\s+[IVXLCDM]+\s+\d+/\d{2,4}(?:\([^)]*\))?\.")

# Дата-время внутри текста, например "191320Z JUL 26" или "171706 JUL 26" (изредка без Z)
_INLINE_DATETIME = re.compile(r"\b\d{6}Z?\s+[A-Z]{3}\s+\d{2}\b")

# Ссылки на отменённые номера, например "CANCEL NAVAREA IV 674/26"
_CANCEL_REF = re.compile(r"CANCEL\s+(?:NAVAREA\s+[IVXLCDM]+\s+|HYDROLANT\s+|HYDROPAC\s+)?(\d+/\d{2,4})")

_TRAILING_SEPARATOR = re.compile(r"\n\s*/\s*$")
_NUMBERED_CLAUSE = re.compile(r"^\d+\.")
_COORDS = re.compile(r"\d{1,3}-\d{2}")


def build_url(area_code: str) -> str:
    key = _DAILY_MEMO_KEYS.get(area_code)
    if not key:
        raise ValueError(f"NGA источник не поддерживает район {area_code!r}")
    return f"{_BASE_URL}?type=view&key={key}"


def _extract_region(block: str) -> Optional[str]:
    ref_match = _REF_WITH_PERIOD.search(block)
    if not ref_match:
        return None
    after = block[ref_match.end():]
    lines = [ln.strip() for ln in after.splitlines() if ln.strip()]
    region_lines: list[str] = []
    for line in lines:
        if _NUMBERED_CLAUSE.match(line) or _COORDS.search(line):
            break
        region_lines.append(line.rstrip("."))
        if len(region_lines) >= 2:
            break
    return ", ".join(region_lines) if region_lines else None


def parse_messages(area_code: str, raw_text: str) -> list[ParsedWarning]:
    """Разбить сырой .txt на отдельные сообщения (реальный, многострочный формат NGA)."""
    matches = list(_BLOCK_HEADER.finditer(raw_text))
    results: list[ParsedWarning] = []
    seen: set[str] = set()

    for i, m in enumerate(matches):
        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        block = raw_text[block_start:block_end]
        block = _TRAILING_SEPARATOR.sub("", block).strip()
        if not block:
            continue

        msgnum = f"{m.group('msgnum')}/{m.group('year')}"
        if msgnum in seen:
            continue  # на всякий случай, если один номер как-то попался дважды в одной выгрузке
        seen.add(msgnum)

        category_raw = (m.group("category") or "").strip()
        category = None if category_raw.lower() == "null" else category_raw or None

        # сводка "какие номера сейчас в силе" -- не отдельное предупреждение, пропускаем показ
        upper = block.upper()
        if "WARNINGS IN FORCE AS OF" in upper and "LISTED HERE" in upper:
            continue

        dt_match = _INLINE_DATETIME.search(block)
        issued_at_raw = dt_match.group(0) if dt_match else None
        region = _extract_region(block)
        cancels = _CANCEL_REF.findall(block)

        results.append(
            ParsedWarning(
                area_code=area_code,
                msg_number=msgnum,
                category=category,
                issued_at_raw=issued_at_raw,
                region=region,
                raw_text=block,
                cancels=cancels,
            )
        )
    return results


def normalize_msgnum(msgnum: str) -> Optional[str]:
    """"296/26" и "296/2026" должны считаться одним и тем же номером."""
    m = re.match(r"(\d+)/(\d{2,4})", msgnum)
    if not m:
        return None
    num, year = m.group(1), m.group(2)
    if len(year) == 2:
        year = "20" + year
    return f"{num}/{year}"


class NgaSource:
    source_id = "nga"
    covers_areas = list(_DAILY_MEMO_KEYS.keys())

    def __init__(self, timeout: float = 20.0):
        self._timeout = timeout

    async def fetch_raw(self, area_code: str) -> str:
        url = build_url(area_code)
        headers = {"User-Agent": "navarea-bot/1.0 (personal non-commercial NAVAREA warnings monitor)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

    def parse(self, area_code: str, raw_text: str) -> list[ParsedWarning]:
        return parse_messages(area_code, raw_text)
