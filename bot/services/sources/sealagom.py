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
import logging
import time
from typing import Optional

import httpx

from .base import ParsedWarning

logger = logging.getLogger(__name__)

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
    "include_geo_features": "true",
    "include_archived": "false",
    "include_all": "true",
}


def _browser_headers(token: str) -> dict:
    """Заголовки как у обычного браузера. Без User-Agent защита сайта
    (Cloudflare и подобное) часто отдаёт 403 на запросы из скриптов, даже
    когда токен полностью рабочий -- на это мы уже наступили."""
    return {
        "X-API-Token": token,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
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


def _shapes_from_sealagom(msg: dict) -> list[dict]:
    """Готовая геометрия из Sealagom (include_geo_features) в наш формат.

    Их разбор точнее нашего: они отдают уже размеченные полигоны, полосы
    (lanes), линии и круги радиуса, а не сырой текст, который приходится
    угадывать регулярками. Если геометрии в ответе нет (не тот тариф или
    у сообщения её просто нет), возвращаем пустой список -- вызывающий код
    тогда откатится на собственный разбор текста.

    Координаты у них в GeoJSON-порядке [долгота, широта], у Leaflet
    наоборот [широта, долгота] -- переворачиваем.
    """
    out: list[dict] = []
    feats = msg.get("geo_features") or msg.get("geometry") or []
    if isinstance(feats, dict):
        feats = feats.get("features") or [feats]

    for f in feats:
        if not isinstance(f, dict):
            continue
        geom = f.get("geometry") or f
        gtype = str(geom.get("type") or f.get("type") or "").lower()
        coords = geom.get("coordinates")
        if coords is None:
            continue

        def flip(pair):
            try:
                lon, lat = float(pair[0]), float(pair[1])
            except (TypeError, ValueError, IndexError):
                return None
            if abs(lat) > 90 or abs(lon) > 180:
                return None
            return [round(lat, 5), round(lon, 5)]

        if gtype in ("polygon",):
            for ring in coords:
                pts = [p for p in (flip(c) for c in ring) if p]
                if len(pts) >= 3:
                    out.append({"type": "polygon", "points": pts})
        elif gtype in ("multipolygon",):
            for poly in coords:
                for ring in poly:
                    pts = [p for p in (flip(c) for c in ring) if p]
                    if len(pts) >= 3:
                        out.append({"type": "polygon", "points": pts})
        elif gtype in ("linestring", "lane", "line"):
            pts = [p for p in (flip(c) for c in coords) if p]
            if len(pts) >= 2:
                out.append({"type": "line", "points": pts})
        elif gtype in ("multilinestring",):
            for line in coords:
                pts = [p for p in (flip(c) for c in line) if p]
                if len(pts) >= 2:
                    out.append({"type": "line", "points": pts})
        elif gtype in ("point",):
            p = flip(coords)
            if p:
                radius = f.get("radius_nm") or f.get("radius") or (f.get("properties") or {}).get("radius_nm")
                shape = {"type": "point", "points": [p]}
                if radius:
                    try:
                        shape = {"type": "circle", "points": [p], "radius_nm": float(radius)}
                    except (TypeError, ValueError):
                        pass
                out.append(shape)
        elif gtype in ("multipoint",):
            for c in coords:
                p = flip(c)
                if p:
                    out.append({"type": "point", "points": [p]})
    return out


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
                shapes=_shapes_from_sealagom(msg) or None,
            )
        )
    return results


class SealagomSource:
    """NAVAREA I-XXI через sealagom.com. Один инстанс переиспользуется для
    всех районов сразу -- см. кэш в _fetch_all."""

    source_id = "sealagom"
    covers_areas = list(ROMAN_TO_ID.keys())

    _MINIMAL_PARAMS = {"include_messages": "true"}
    _MAX_PAGES = 50  # страховка от бесконечного цикла, если "next" зациклится

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
        """Обходит пагинацию: Sealagom отдаёт результат страницами (поле "next"),
        без этого доезжала только первая страница -- часть районов и часть
        действующих предупреждений просто терялась."""
        headers = _browser_headers(self._api_token)
        merged: list = []
        url = NAVAREA_URL
        query = dict(params)
        pages = 0

        async with httpx.AsyncClient(timeout=self._timeout, headers=headers, follow_redirects=True) as client:
            while url and pages < self._MAX_PAGES:
                resp = await client.get(url, params=query)
                resp.raise_for_status()
                chunk = resp.json()
                merged.extend(chunk.get("results", []))
                url = chunk.get("next")
                query = None  # "next" уже содержит все параметры внутри себя
                pages += 1

        return {"results": merged}

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
        """Береговые регионы. При 403 пробуем сокращать набор параметров:
        часть из них (geo_features, архив, расширенные координаты) доступна
        не на всяком тарифе, и сервер отвечает отказом на весь запрос
        целиком, а не на отдельное поле."""
        now = time.time()
        if self._cache is not None and (now - self._cache_at) < self._cache_seconds:
            return self._cache

        # от самого полного набора к самому скромному
        attempts = [
            _NAVAREA_PARAMS,
            {"include_messages": "true", "include_coordinates": "true"},
            {"include_messages": "true"},
            {},
        ]

        headers = _browser_headers(self._api_token)
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=self._timeout, headers=headers, follow_redirects=True) as client:
            for params in attempts:
                try:
                    resp = await client.get(COASTAL_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    if params is not _NAVAREA_PARAMS:
                        logger.info("Береговые регионы Sealagom: подошёл сокращённый запрос %s", sorted(params))
                    self._cache = data
                    self._cache_at = now
                    return data
                except httpx.HTTPStatusError as e:
                    last_error = e
                    if e.response.status_code not in (400, 401, 403):
                        raise
                except Exception as e:
                    last_error = e
                    raise

        raise last_error if last_error else RuntimeError("Sealagom coastal: запрос не удался")

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
