"""
Источник Instituto Hidrografico de la Marina (Испания) -- координатор
NAVAREA III, которая покрывает Средиземное море, Чёрное море и Азовское
море целиком (самый актуальный источник для судов, работающих из
черноморских портов).

Рабочий адрес найден через официальный сайт (версия "для пользователей
с отключённым JavaScript"):

    https://armada.defensa.gob.es/ihm/XML/navareas_crudo.xml

ВАЖНО -- статус ЭКСПЕРИМЕНТАЛЬНЫЙ. В отличие от источников NGA и UKHO,
точную структуру тегов этого XML не удалось увидеть напрямую при
разработке (сайт отдаёт файл, но получить его сырые байты через
инструмент веб-поиска не вышло, только описание содержимого).
Файл существует, отвечает 200 OK и имеет тип application/xml -- то есть
адрес рабочий, но перед боевым использованием стоит:

  1. Запустить fetch_raw() и один раз распечатать результат целиком,
     посмотреть реальную структуру тегов.
  2. При необходимости поправить parse() под то, что увидишь.

Ниже -- рабочая заготовка: пробуем распарсить как XML, если не выходит --
достаём текст как есть и режем эвристикой на отдельные радиоавизо.
Содержимое двуязычное (испанский, затем английский), парсер пытается
взять именно английскую часть.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import httpx

from .base import ParsedWarning

URL = "https://armada.defensa.gob.es/ihm/XML/navareas_crudo.xml"

_IN_FORCE_LIST = re.compile(r"IN FORCE ON.*?UTC\.?\s*((?:\d{4}:[\d, ]+\s*)+)", re.IGNORECASE)

# Настоящий якорь одной записи: 6-значный код, номер/год, ISO-дата, дальше акватория.
# Например: "220124 0124/22 2022-03-23T00:00:00 MAR NEGRO BLACK SEA"
_RECORD_MARKER = re.compile(
    r"\d{6}\s+(\d+)[/-](\d{2,4})\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+[A-ZÁÉÍÓÚÑÜ /]{3,60}"
)
_CANCEL_REF = re.compile(r"CANCEL(?:AR)?\s+(?:NAVAREA\s*III\s*)?(\d+[/-]\d{2,4})", re.IGNORECASE)

_BOILERPLATE = (
    "ARE TRANSMITTED DAILY BY SAFETYNET",
    "ARE AVAILABLE ON THE WEBSITE",
    "ARE ALSO PUBLISHED IN THE WEEKLY GROUP",
)


def _strip_tags(raw: str) -> str:
    try:
        root = ET.fromstring(raw)
        text = " ".join(root.itertext())
    except ET.ParseError:
        # не well-formed XML (или это HTML-обёртка) -- грубо срезаем теги
        text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", text).strip()


def parse_messages(area_code: str, raw_text: str) -> list[ParsedWarning]:
    """
    Каждую отдельную запись подряд открывает узнаваемый маркер: шестизначный
    код, номер/год, ISO-дата и следом акватория заглавными буквами. Это
    надёжнее, чем резать по пронумерованным абзацам "N.-", потому что не
    путает испанскую и английскую версию одного и того же предупреждения
    между собой и не путает сноски-примечания с отдельными сообщениями.

    Само содержимое между двумя маркерами по-прежнему двуязычное (испанский
    и английский текст вперемешку) -- разделять его чисто не получилось
    без доступа к сырым тегам XML, поэтому оба языка остаются в одном
    сообщении. Не идеально, но статус "experimental" в реестре и так
    предупреждает об этом.
    """
    text = _strip_tags(raw_text)
    results: list[ParsedWarning] = []

    force_match = _IN_FORCE_LIST.search(text)
    if force_match:
        results.append(
            ParsedWarning(
                area_code=area_code,
                msg_number=None,
                category="IN_FORCE_LIST",
                issued_at_raw=None,
                region="MEDITERRANEAN / BLACK SEA / AZOV SEA",
                raw_text=text[force_match.start():force_match.end()],
                cancels=[],
            )
        )

    matches = list(_RECORD_MARKER.finditer(text))
    seen: set[str] = set()
    for i, m in enumerate(matches):
        msgnum = f"{m.group(1)}/{m.group(2)}"
        if msgnum in seen:
            continue
        seen.add(msgnum)

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if len(body) < 15 or any(phrase in body.upper() for phrase in _BOILERPLATE):
            continue

        cancels = [c.replace("-", "/") for c in _CANCEL_REF.findall(body)]
        results.append(
            ParsedWarning(
                area_code=area_code,
                msg_number=msgnum,
                category=None,
                issued_at_raw=m.group(3),
                region="MEDITERRANEAN / BLACK SEA / AZOV SEA",
                raw_text=body,
                cancels=cancels,
            )
        )
    return results


class SpainIhmSource:
    source_id = "ihm_es"
    covers_areas = ["III"]
    experimental = True  # см. предупреждение в докстринге модуля

    def __init__(self, timeout: float = 20.0):
        self._timeout = timeout

    async def fetch_raw(self, area_code: str) -> str:
        headers = {"User-Agent": "navarea-bot/1.0 (personal non-commercial NAVAREA warnings monitor)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(URL)
            resp.raise_for_status()
            # сайт .es часто отдаёт latin-1/windows-1252 несмотря на заголовок
            try:
                return resp.content.decode("utf-8")
            except UnicodeDecodeError:
                return resp.content.decode("windows-1252", errors="replace")

    def parse(self, area_code: str, raw_text: str) -> list[ParsedWarning]:
        return parse_messages(area_code, raw_text)
