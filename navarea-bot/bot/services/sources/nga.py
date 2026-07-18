"""
Источник NGA (National Geospatial-Intelligence Agency, США).

NGA официально координирует NAVAREA IV и NAVAREA XII, плюс публикует
свои региональные HYDROLANT/HYDROPAC предупреждения. В отличие от
большинства других национальных сайтов, NGA отдаёт готовый простой
текст (.txt) без JavaScript-рендеринга и без блокировки в robots.txt,
через "Daily Memorandum" файлы:

    https://msi.nga.mil/api/publications/download?type=view&key=16694640/SFH00000/DailyMemIV.txt
    https://msi.nga.mil/api/publications/download?type=view&key=16694640/SFH00000/DailyMemXII.txt
    https://msi.nga.mil/api/publications/download?type=view&key=16694640/SFH00000/DailyMemLAN.txt   (HYDROLANT)
    https://msi.nga.mil/api/publications/download?type=view&key=16694640/SFH00000/DailyMemPAC.txt   (HYDROPAC)

Формат сообщения внутри файла (реальный пример):

    242359Z JUN 25 NAVAREA XII 392/25(16). NORTH PACIFIC. M/V MORNING MIDAS
    SANK IN 45-16.88N 179-14.13W. VESSELS IN VICINITY REQUESTED TO ...

То есть: ДДЧЧММZ МЕС ГГ, тип и номер серии, номер/год(категория), точка,
дальше произвольный текст до начала следующего сообщения.

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

# ключи для msi.nga.mil/api/publications/download?type=view&key=...
_DAILY_MEMO_KEYS = {
    "IV": "16694640/SFH00000/DailyMemIV.txt",
    "XII": "16694640/SFH00000/DailyMemXII.txt",
    "HYDROLANT": "16694640/SFH00000/DailyMemLAN.txt",
    "HYDROPAC": "16694640/SFH00000/DailyMemPAC.txt",
}

_BASE_URL = "https://msi.nga.mil/api/publications/download"

# Заголовок отдельного сообщения, например:
#   "242359Z JUN 25 NAVAREA XII 392/25(16)."
#   "271808Z FEB 26 NAVAREA XII 133/26."
#   (для HYDROLANT/HYDROPAC вместо "NAVAREA XII" будет "HYDROLANT"/"HYDROPAC")
_MSG_HEADER = re.compile(
    r"""
    (?P<datetime>\d{6}Z\ [A-Z]{3}\ \d{2})\s+
    (?P<series>NAVAREA\ [IVXLCDM]+|HYDROLANT|HYDROPAC|HYDROARC)\s+
    (?P<msgnum>\d+)/(?P<year>\d{2,4})
    (?:\((?P<category>[A-Z0-9]+)\))?
    \.
    """,
    re.VERBOSE,
)

# Ссылки на отменённые номера внутри текста сообщения, например:
#   "CANCEL NAVAREA XII 270/26"
#   "CANCEL THIS MSG"
#   "CANCEL 0110/22"
_CANCEL_REF = re.compile(r"CANCEL\s+(?:NAVAREA\s+[IVXLCDM]+\s+|HYDROLANT\s+|HYDROPAC\s+)?(\d+/\d{2,4})")

# Регион идёт сразу после заголовка, до следующей точки с заглавных букв
_REGION = re.compile(r"^\s*([A-Z][A-Z0-9 ,.\-]{2,60}?)\.\s")


def build_url(area_code: str) -> str:
    key = _DAILY_MEMO_KEYS.get(area_code)
    if not key:
        raise ValueError(f"NGA источник не поддерживает район {area_code!r}")
    return f"{_BASE_URL}?type=view&key={key}"


def parse_messages(area_code: str, raw_text: str) -> list[ParsedWarning]:
    """Разбить сырой .txt на отдельные сообщения."""
    matches = list(_MSG_HEADER.finditer(raw_text))
    results: list[ParsedWarning] = []

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        body = raw_text[start:end].strip()
        after_header = raw_text[m.end():end]

        region_match = _REGION.match(after_header.strip())
        region = region_match.group(1).strip() if region_match else None

        cancels = _CANCEL_REF.findall(after_header)

        msgnum = f"{m.group('msgnum')}/{m.group('year')}"

        results.append(
            ParsedWarning(
                area_code=area_code,
                msg_number=msgnum,
                category=m.group("category"),
                issued_at_raw=m.group("datetime"),
                region=region,
                raw_text=body,
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
        headers = {"User-Agent": "navarea-bot/1.0 (личный бот для мониторинга NAVAREA, некоммерческий)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

    def parse(self, area_code: str, raw_text: str) -> list[ParsedWarning]:
        return parse_messages(area_code, raw_text)
