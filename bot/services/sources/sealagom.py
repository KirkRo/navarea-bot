"""
Источник Sealagom (sealagom.com) -- платный API ($20/мес за Full API),
агрегирующий все 21 район NAVAREA и Coastal warnings многих стран в
одном месте, уже разобранными на отдельные сообщения, с готовыми
координатами и статусом отмены. Используется вместо собственных
скрейперов (nga.py/ukho.py/peru_dhn.py/spain_ihm.py), когда в .env
задан SEALAGOM_API_TOKEN.

Структура ответа по документации https://www.sealagom.com/api/docs/:

    GET /api/v1/navarea/?include_messages=true&include_coordinates=true...
    {
      "results": [
        {
          "id": 4,
          "title": "NAVAREA IV",
          "active_messages": [
            {
              "id": 123,
              "number": "700/26",
              "content": "полный текст предупреждения",
              "added_on": "2026-07-19T13:20:00Z",
              "cancel_date": null
            }
          ]
        }
      ]
    }

За один вызов API отдаёт СРАЗУ все районы, поэтому результат кэшируется
на CACHE_SECONDS -- если в одном цикле опроса нужно несколько районов,
второй и следующие берут уже скачанное, а не бьют по API повторно.

ВАЖНО: структура ответа собрана по документации, а не проверена на
реальных данных (нет доступа к sealagom.com из песочницы разработки).
Разбор написан защищённо (валится не должен, просто может недосчитать
поле), но при первом реальном запуске стоит свериться с тем, что
приходит по факту, и поправить при необходимости.
"""
from __future__ import annotations

import json
import time
from typing import Optional

import httpx

from .base import ParsedWarning

NAVAREA_URL = "https://www.sealagom.com/api/v1/navarea/"
COASTAL_URL = "https://www.sealagom.com/api/v1/coastal/"

ROMAN_TO_ID = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
    "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20, "XXI": 21,
}

_NAVAREA_PARAMS = {
    "include_messages": "true",
    "include_coordinates": "true",
    "include_enhanced_coordinates": "true",
    "include_keywords": "true",
    "include_all": "true",
}


def _region_from_message(msg: dict) -> Optional[str]:
    keywords = msg.get("keywords") or {}
    loc = keywords.get("location")
    if loc:
        return loc
    # запасной вариант -- первая строчка текста похожа на регион, если она короткая и заглавными
    content = (msg.get("content") or "").strip()
    first_line = content.split(".")[0].strip()
    if first_line and len(first_line) < 60 and first_line.isupper():
        return first_line
    return None


def _messages_to_warnings(area_code: str, messages: list[dict]) -> list[ParsedWarning]:
    results = []
    for msg in messages:
        if msg.get("cancel_date"):
            continue  # Sealagom уже сам отмечает отменённые -- не показываем как действующие
        results.append(
            ParsedWarning(
                area_code=area_code,
                msg_number=msg.get("number"),
                category=None,
                issued_at_raw=msg.get("added_on"),
                region=_region_from_message(msg),
                raw_text=(msg.get("content") or "").strip(),
                cancels=[],  # отмену Sealagom сообщает через cancel_date, не через ссылки в тексте
            )
        )
    return results


class SealagomSource:
    """NAVAREA I-XXI через sealagom.com. Один инстанс переиспользуется для
    всех районов сразу -- см. кэш в _fetch_all."""

    source_id = "sealagom"
    covers_areas = list(ROMAN_TO_ID.keys())

    _MINIMAL_PARAMS = {"include_messages": "true"}

    def __init__(self, api_token: str, timeout: float = 25.0, cache_seconds: float = 60.0, error_cache_seconds: float = 45.0):
        self._api_token = api_token
        self._timeout = timeout
        self._cache_seconds = cache_seconds
        self._error_cache_seconds = error_cache_seconds
        self._cache: Optional[dict] = None
        self._cache_at: float = 0.0
        self._last_error: Optional[Exception] = None
        self._last_error_at: float = 0.0

    async def _request(self, params: dict) -> dict:
        headers = {"X-API-Token": self._api_token}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(NAVAREA_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    async def _fetch_all(self) -> dict:
        now = time.time()
        if self._cache is not None and (now - self._cache_at) < self._cache_seconds:
            return self._cache

        # Если недавно уже падало -- не долбимся по API на каждый следующий
        # район в этом же цикле опроса, сразу отдаём ту же ошибку.
        if self._last_error is not None and (now - self._last_error_at) < self._error_cache_seconds:
            raise self._last_error

        try:
            data = await self._request(_NAVAREA_PARAMS)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                # Может быть запрошены параметры не по тарифу (coordinates/keywords/
                # архив требуют Full) -- пробуем облегчённый запрос как запасной вариант.
                try:
                    data = await self._request(self._MINIMAL_PARAMS)
                except Exception as e2:
                    self._last_error, self._last_error_at = e2, now
                    raise
            else:
                self._last_error, self._last_error_at = e, now
                raise
        except Exception as e:
            self._last_error, self._last_error_at = e, now
            raise

        self._cache, self._cache_at = data, now
        self._last_error = None
        return data

    async def fetch_raw(self, area_code: str) -> str:
        data = await self._fetch_all()
        return json.dumps(data)

    def parse(self, area_code: str, raw_text: str) -> list[ParsedWarning]:
        data = json.loads(raw_text)
        target_id = ROMAN_TO_ID.get(area_code)
        if target_id is None:
            return []

        for area_obj in data.get("results", []):
            if area_obj.get("id") == target_id:
                messages = area_obj.get("active_messages") or []
                return _messages_to_warnings(area_code, messages)
        return []


class SealagomCoastalSource:
    """Coastal warnings через sealagom.com. covers_areas заполняется динамически
    в registry.py после первого запроса (список стран заранее не известен)."""

    source_id = "sealagom_coastal"
    covers_areas: list[str] = []  # заполняется в registry.py

    def __init__(self, api_token: str, timeout: float = 25.0, cache_seconds: float = 60.0):
        self._api_token = api_token
        self._timeout = timeout
        self._cache_seconds = cache_seconds
        self._cache: Optional[dict] = None
        self._cache_at: float = 0.0

    async def _fetch_all(self) -> dict:
        now = time.time()
        if self._cache is not None and (now - self._cache_at) < self._cache_seconds:
            return self._cache

        headers = {"X-API-Token": self._api_token}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(COASTAL_URL, params=_NAVAREA_PARAMS)
            resp.raise_for_status()
            data = resp.json()

        self._cache = data
        self._cache_at = now
        return data

    async def fetch_raw(self, area_code: str) -> str:
        data = await self._fetch_all()
        return json.dumps(data)

    def parse(self, area_code: str, raw_text: str) -> list[ParsedWarning]:
        """area_code здесь -- это "COASTAL:<id>", см. registry.py."""
        data = json.loads(raw_text)
        if not area_code.startswith("COASTAL:"):
            return []
        target_id = int(area_code.split(":", 1)[1])

        for area_obj in data.get("results", []):
            if area_obj.get("id") == target_id:
                messages = area_obj.get("active_messages") or []
                return _messages_to_warnings(area_code, messages)
        return []

    async def list_regions(self) -> list[dict]:
        """Список доступных coastal-регионов (id + название), для регистрации в registry.py."""
        data = await self._fetch_all()
        return [{"id": r.get("id"), "title": r.get("title")} for r in data.get("results", [])]
