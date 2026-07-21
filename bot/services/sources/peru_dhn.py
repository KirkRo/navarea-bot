"""
Источник Direccion de Hidrografia y Navegacion, Peru -- координатор
NAVAREA XVI (юго-восточная часть Тихого океана, побережье Перу и Чили).

Рабочий адрес (старый на hydrobharat.nic.in -- опечатка, на самом деле
это про Индию -- у Перу свой домен):

    https://www.dhn.mil.pe/portal/navarea/radioavisos-warnings

Отдаёт чистый английский текст без JS, без блокировки. Особенность
формата: одно и то же предупреждение повторяется в КАЖДОМ цикле
трансляции (обычно дважды в сутки, 0500 и 1700 UTC), пока действует --
то есть один текст встречается по 10-20 раз подряд в одной выгрузке.
Поэтому парсер отдаёт только ОДНУ копию на каждый уникальный номер
NAVAREA XVI NNN/YY за один вызов (используем первую встреченную --
благодаря дедупликации по тексту в БД повторные вызовы дальше тоже
не создают дублей).

Блоки без порядкового номера (просто "NONE" вместо "SERIE:NNN") --
это пустые циклы трансляции без нового содержания, пропускаются.
"""
from __future__ import annotations

import html
import re

import httpx

from .base import ParsedWarning

URL = "https://www.dhn.mil.pe/portal/navarea/radioavisos-warnings"

_BLOCK_HEADER = re.compile(r"\d+-\d{4}\s+MESSAGE IN FORCE", re.IGNORECASE)
_MSG_REF = re.compile(r"NAVAREA\s+XVI\s+(\d+/\d{2,4})")
_END_MARK = re.compile(r"\bNNNN\b")
_CANCEL_REF = re.compile(r"CANCEL(?:\s+THIS\s+MESSAGE)?\s+(?:NAVAREA\s+XVI\s+)?(\d+/\d{2,4})?", re.IGNORECASE)
_BR_TAG = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")


def _clean_html(raw: str) -> str:
    """Сайт иногда отдаёт текст с <br /> вместо переносов строк -- превращаем
    обратно в переносы, остальные теги (если попадутся) вырезаем целиком."""
    text = _BR_TAG.sub("\n", raw)
    text = _ANY_TAG.sub("", text)
    return html.unescape(text)


def parse_messages(area_code: str, raw_text: str) -> list[ParsedWarning]:
    raw_text = _clean_html(raw_text)
    blocks = _BLOCK_HEADER.split(raw_text)[1:]  # первый кусок до первого блока -- мусор/шапка
    seen_msgnums: set[str] = set()
    results: list[ParsedWarning] = []

    for block in blocks:
        ref_match = _MSG_REF.search(block)
        if not ref_match:
            continue  # блок "NONE" -- пустой цикл трансляции, нового содержания нет

        msgnum = ref_match.group(1)
        if msgnum in seen_msgnums:
            continue  # то же предупреждение уже встречалось в этой выгрузке (повтор трансляции)
        seen_msgnums.add(msgnum)

        end_match = _END_MARK.search(block, ref_match.end())
        body_raw = block[ref_match.start():end_match.start() if end_match else len(block)]
        body = "\n".join(line.strip() for line in body_raw.strip().splitlines() if line.strip())

        # первая строка после номера обычно страна/акватория, вторая -- конкретное место
        lines = body.splitlines()
        region = " ".join(lines[1:3]).strip() if len(lines) > 1 else None

        cancels = [m for m in _CANCEL_REF.findall(body) if m]

        results.append(
            ParsedWarning(
                area_code=area_code,
                msg_number=msgnum,
                category=None,
                issued_at_raw=None,
                region=region,
                raw_text=body,
                cancels=cancels,
            )
        )
    return results


class PeruDhnSource:
    source_id = "dhn_peru"
    covers_areas = ["XVI"]

    def __init__(self, timeout: float = 20.0):
        self._timeout = timeout

    async def fetch_raw(self, area_code: str) -> str:
        headers = {"User-Agent": "navarea-bot/1.0 (personal non-commercial NAVAREA warnings monitor)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(URL)
            resp.raise_for_status()
            return resp.text

    def parse(self, area_code: str, raw_text: str) -> list[ParsedWarning]:
        return parse_messages(area_code, raw_text)
