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

# "1.- DRILLING OPERATIONS BY FATIH ... 2.- CANCEL THIS MESSAGE ... 3.- CANCEL NAVAREA III 0037/26"
_ES_EN_SPLIT = re.compile(r"NAVAREA III IN FORCE ON", re.IGNORECASE)
_PARAGRAPH = re.compile(r"(?:^|\s)(\d+)\.-\s")
_CANCEL_REF = re.compile(r"CANCEL(?:AR)?\s+(?:NAVAREA\s*III\s*)?(\d+/\d{2,4})", re.IGNORECASE)
_IN_FORCE_LIST = re.compile(r"IN FORCE ON.*?UTC\.?\s*((?:\d{4}:[\d, ]+\s*)+)", re.IGNORECASE)

# Стандартные сноски, которые повторяются в каждом дайджесте -- не настоящие
# предупреждения, отсеиваем по подстроке.
_BOILERPLATE = (
    "ARE TRANSMITTED DAILY BY SAFETYNET",
    "ARE AVAILABLE ON THE WEBSITE",
    "ARE ALSO PUBLISHED IN THE WEEKLY GROUP",
    "CANCEL THIS MESSAGE ON",
)


def _strip_tags(raw: str) -> str:
    try:
        root = ET.fromstring(raw)
        return " ".join(root.itertext())
    except ET.ParseError:
        # не well-formed XML (или это HTML-обёртка) -- грубо срезаем теги
        return re.sub(r"<[^>]+>", " ", raw)


def parse_english_text(raw: str) -> str:
    """Документ двуязычный: испанский блок, потом английский. Берём английский."""
    text = _strip_tags(raw)
    text = re.sub(r"\s+", " ", text).strip()
    m = _ES_EN_SPLIT.search(text)
    return text[m.start():] if m else text


def parse_messages(area_code: str, raw_text: str) -> list[ParsedWarning]:
    """
    Эвристический разбор: ищем список номеров из блока "IN FORCE ON ...",
    затем режем оставшийся текст на пронумерованные абзацы "N.- ...".
    Это не даёт чистого msg_number на каждое сообщение (в отличие от NGA/UKHO),
    поэтому raw_text каждого фрагмента стоит целиком отдавать в Q&A/уведомление,
    а не полагаться на msg_number для дедупликации -- для этого есть text_hash в БД.
    """
    text = parse_english_text(raw_text)
    results: list[ParsedWarning] = []

    # 1) сводка "какие номера сейчас действуют" -- отдаём отдельным служебным сообщением
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

    # 2) пронумерованные абзацы с конкретными опасностями
    matches = list(_PARAGRAPH.finditer(text))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if len(body) < 20:
            continue
        if any(phrase in body.upper() for phrase in _BOILERPLATE):
            continue
        cancels = _CANCEL_REF.findall(body)
        results.append(
            ParsedWarning(
                area_code=area_code,
                msg_number=None,
                category=None,
                issued_at_raw=None,
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
        headers = {"User-Agent": "navarea-bot/1.0 (личный бот для мониторинга NAVAREA, некоммерческий)"}
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
