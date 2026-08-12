"""
Источник Canadian Coast Guard -- координатор NAVAREA XVII и XVIII
(канадская Арктика, Гудзонов залив, море Бофорта, восточное побережье).

Адрес выглядит как REST, но отдаёт обычную страницу поиска целиком,
около 900 КБ вёрстки правительственного шаблона WET:

    https://nis.ccg-gcc.gc.ca/public/rest/messages/en/search-navareas
        ?navareas=2&status=PUBLISHED&sortBy=DATE&maxHits=50

Район выбирается числом в navareas: 2 -- это XVII, 4 -- это XVIII.
Экспорт в файл на сервере сломан (gridfile отвечает 500 с жалобой на
пустой exportType, и подобрать значение не вышло), поэтому разбираем саму
страницу. Данные в ней лежат ровно и однообразно: каждое сообщение это
вложенная таблица class="navarea-text-style", внутри ссылка с номером
вида "NAVAREA XVII 64/2026", затем район, номер карты и текст.

Сводки "WARNINGS IN FORCE AT" пропускаются. Это не предупреждение об
опасности, а служебный перечень действующих номеров, который выходит
заново каждые несколько дней. Если его пропустить в базу, человек будет
получать уведомление о том, что список опять переиздан.
"""
from __future__ import annotations

import html
import re

import httpx

from .base import ParsedWarning

URL = "https://nis.ccg-gcc.gc.ca/public/rest/messages/en/search-navareas"

# Номер района в запросе не совпадает с римским номером NAVAREA
AREA_QUERY = {"XVII": "2", "XVIII": "4"}

_BLOCK = re.compile(r'class="navarea-text-style"(.*?)</table>', re.S | re.I)
_MSG_REF = re.compile(r'/message/\d+"\s*>\s*NAVAREA\s+(XVII|XVIII)\s+(\d+/\d{2,4})', re.I)
_CELL = re.compile(r'class="(no-margin|no-margin-description)"[^>]*>(.*?)</td>', re.S | re.I)
_CANCEL = re.compile(r'CANCEL(?:S)?\s+NAVAREA\s+(?:XVII|XVIII)\s+(\d+/\d{2,4})', re.I)
_IN_FORCE = re.compile(r"WARNINGS\s+IN\s+FORCE\s+AT", re.I)
_BR = re.compile(r"<\s*br\s*/?\s*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_CHART = re.compile(r"^chart\b", re.I)


def _text(fragment: str) -> str:
    """Ячейку таблицы превращаем в обычный текст.

    Переносы в описании сделаны тегами <br>, а не переводом строки, и без
    этой замены весь текст предупреждения слипся бы в одну строку."""
    out = _BR.sub("\n", fragment)
    out = _TAG.sub("", out)
    out = html.unescape(out)
    # Вёрстка переносит и отбивает текст пробелами ради читаемости исходника,
    # из-за чего внутри строки попадаются провалы вида "Chart CHS      7685".
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip()
                     for line in out.splitlines() if line.strip())


def parse_messages(area_code: str, raw_text: str) -> list[ParsedWarning]:
    results: list[ParsedWarning] = []
    seen: set[str] = set()

    for block in _BLOCK.findall(raw_text):
        ref = _MSG_REF.search(block)
        if not ref:
            continue
        msgnum = ref.group(2)
        if msgnum in seen:
            continue
        seen.add(msgnum)

        cells = [_text(body) for _cls, body in _CELL.findall(block)]
        cells = [c for c in cells if c]
        if not cells or _IN_FORCE.search("\n".join(cells)):
            continue  # служебный перечень действующих номеров, см. пояснение сверху

        # Номер карты источник кладёт отдельной строкой; для района он не
        # годится, поэтому под регион берём первую строку, которая картой
        # не является.
        region = next((c for c in cells if not _CHART.match(c)), None)
        if region:
            # Район источник иногда разбивает на две строки ("Arctic" и
            # "Beaufort Sea"); в списке предупреждений он идёт одной строкой.
            region = " ".join(region.split())
        body = "\n".join(cells)
        header = f"NAVAREA {ref.group(1)} {msgnum}"

        results.append(
            ParsedWarning(
                area_code=area_code,
                msg_number=msgnum,
                category=None,
                issued_at_raw=None,
                region=(region or "")[:120] or None,
                raw_text=f"{header}\n{body}",
                cancels=_CANCEL.findall(body),
            )
        )
    return results


class CanadaCcgSource:
    source_id = "ccg_canada"
    covers_areas = ["XVII", "XVIII"]

    def __init__(self, timeout: float = 30.0):
        # Страница тяжёлая (около 900 КБ), поэтому запас по времени больше
        # обычного: на судовом канале двадцати секунд не хватает.
        self._timeout = timeout

    async def fetch_raw(self, area_code: str) -> str:
        params = {
            "navareas": AREA_QUERY.get(area_code, "2"),
            "status": "PUBLISHED",
            "sortBy": "DATE",
            "maxHits": "50",
        }
        headers = {"User-Agent": "navarea-bot/1.0 (personal non-commercial NAVAREA warnings monitor)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(URL, params=params)
            resp.raise_for_status()
            return resp.text

    def parse(self, area_code: str, raw_text: str) -> list[ParsedWarning]:
        return parse_messages(area_code, raw_text)
