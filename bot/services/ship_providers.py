"""
Слой источников данных о судах.

Устроен так, чтобы остальное приложение не знало, откуда пришли данные.
Провайдеры опрашиваются по приоритету, первый ответивший выигрывает.
Добавить новый источник -- это написать класс с двумя методами и
вписать его в PROVIDERS, ничего больше менять не нужно.

Про источники прямо и без иллюзий:

* Официального открытого API с данными судов не существует. Всё, что
  есть (MarineTraffic, VesselFinder, Datalastic, MyShipTracking),
  отдаёт данные только по ключу и за деньги.
* Неофициальный разбор их страниц делать нельзя: это нарушает условия
  использования и отваливается при первой же смене вёрстки. Мы уже
  наступали на это с сайтами предупреждений, здесь наступать не будем.
* Поэтому без ключа работает локальный провайдер: подсказки по судам,
  которые пользователь уже завёл. Это честно и всегда работает, в том
  числе в рейсе без связи.
* Как только появится ключ, достаточно задать SHIP_API_URL и
  SHIP_API_TOKEN в .env -- включится HttpShipProvider, и поиск начнёт
  находить суда по всей мировой базе.
"""
from __future__ import annotations

import logging
from typing import Protocol

import httpx

from ..config import config

logger = logging.getLogger(__name__)


class ShipDataProvider(Protocol):
    """Любой источник данных о судах."""

    name: str
    priority: int  # меньше -- выше приоритет

    async def search(self, query: str, limit: int = 8) -> list[dict]:
        """Подсказки по части названия, IMO или MMSI."""
        ...

    async def fetch(self, ident: str) -> dict | None:
        """Полная карточка по идентификатору из подсказки."""
        ...


class LocalShipProvider:
    """Суда, которые пользователь уже завёл. Работает всегда и без сети."""

    name = "local"
    priority = 10

    def __init__(self, vessels: list[dict]):
        self._vessels = vessels or []

    async def search(self, query: str, limit: int = 8) -> list[dict]:
        q = (query or "").strip().lower()
        if not q:
            return []
        out = []
        for v in self._vessels:
            hay = " ".join(str(v.get(k, "")) for k in ("name", "imo", "mmsi", "callsign")).lower()
            if q in hay:
                out.append({
                    "ident": v.get("_id") or v.get("imo") or v.get("name"),
                    "name": v.get("name") or "Без названия",
                    "imo": v.get("imo", ""),
                    "mmsi": v.get("mmsi", ""),
                    "type": v.get("type", ""),
                    "flag": v.get("flag", ""),
                    "source": "мои суда",
                })
            if len(out) >= limit:
                break
        return out

    async def fetch(self, ident: str) -> dict | None:
        for v in self._vessels:
            if v.get("_id") == ident or v.get("imo") == ident:
                return v
        return None


class HttpShipProvider:
    """Внешний AIS-сервис по ключу. Включается, когда заданы SHIP_API_URL
    и SHIP_API_TOKEN -- конкретный сервис не зашит, подойдёт любой,
    отдающий JSON со списком судов.

    Ожидаемый ответ на поиск: список объектов или {"data": [...]}, где у
    каждого есть название и хотя бы один идентификатор. Названия полей
    подхватываются гибко: и name, и SHIPNAME, и vessel_name.
    """

    name = "http"
    priority = 1

    _NAME_KEYS = ("name", "shipname", "SHIPNAME", "vessel_name", "vesselName", "title")
    _IMO_KEYS = ("imo", "IMO", "imo_number", "imoNumber")
    _MMSI_KEYS = ("mmsi", "MMSI", "mmsi_number")
    _TYPE_KEYS = ("type", "ship_type", "shiptype", "TYPE_NAME", "vessel_type")
    _FLAG_KEYS = ("flag", "FLAG", "country", "country_name")

    def __init__(self, url: str, token: str, timeout: float = 15.0):
        self._url = url.rstrip("/")
        self._token = token
        self._timeout = timeout

    @staticmethod
    def _pick(obj: dict, keys) -> str:
        for k in keys:
            v = obj.get(k)
            if v not in (None, ""):
                return str(v)
        return ""

    def _to_item(self, obj: dict) -> dict:
        imo = self._pick(obj, self._IMO_KEYS)
        mmsi = self._pick(obj, self._MMSI_KEYS)
        return {
            "ident": imo or mmsi or self._pick(obj, self._NAME_KEYS),
            "name": self._pick(obj, self._NAME_KEYS) or "Без названия",
            "imo": imo,
            "mmsi": mmsi,
            "type": self._pick(obj, self._TYPE_KEYS),
            "flag": self._pick(obj, self._FLAG_KEYS),
            "source": "AIS-сервис",
            "_raw": obj,
        }

    async def _request(self, params: dict) -> list[dict]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "X-API-Key": self._token,
            "User-Agent": "watchkeeper/1.0 (bridge officer toolkit)",
        }
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers,
                                     follow_redirects=True) as client:
            resp = await client.get(self._url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, dict):
            for key in ("data", "results", "vessels", "items"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
            else:
                data = [data]
        return data if isinstance(data, list) else []

    async def search(self, query: str, limit: int = 8) -> list[dict]:
        try:
            rows = await self._request({"query": query, "search": query, "limit": limit})
        except Exception:
            logger.exception("Поиск судна во внешнем сервисе не удался")
            return []
        return [self._to_item(r) for r in rows if isinstance(r, dict)][:limit]

    async def fetch(self, ident: str) -> dict | None:
        try:
            rows = await self._request({"imo": ident, "mmsi": ident, "query": ident, "limit": 1})
        except Exception:
            logger.exception("Загрузка судна из внешнего сервиса не удалась")
            return None
        if not rows:
            return None

        item = self._to_item(rows[0])
        raw = item.pop("_raw", {})
        # переносим то, что удалось опознать, в поля нашей карточки
        card = {"name": item["name"], "imo": item["imo"], "mmsi": item["mmsi"],
                "type": item["type"], "flag": item["flag"]}
        numeric = {
            "loa": ("length", "LENGTH", "loa", "length_overall"),
            "beam": ("breadth", "BREADTH", "beam", "width"),
            "dwt": ("dwt", "DWT", "deadweight"),
            "gt": ("gt", "GT", "gross_tonnage"),
            "built": ("built", "YEAR_BUILT", "year_built", "build_year"),
            "draft_max": ("max_draught", "draught", "MAX_DRAUGHT", "draft"),
            "speed": ("speed", "SPEED", "avg_speed", "service_speed"),
            "callsign": ("callsign", "CALLSIGN", "call_sign"),
        }
        for our, theirs in numeric.items():
            val = self._pick(raw, theirs)
            if val:
                card[our] = val
        return {k: v for k, v in card.items() if v}


def build_providers(user_vessels: list[dict]) -> list:
    """Список источников по приоритету. Локальный есть всегда."""
    providers: list = [LocalShipProvider(user_vessels)]
    url = getattr(config, "ship_api_url", "")
    token = getattr(config, "ship_api_token", "")
    if url and token:
        providers.append(HttpShipProvider(url, token))
    return sorted(providers, key=lambda p: p.priority)


async def search_ships(user_vessels: list[dict], query: str, limit: int = 8) -> dict:
    """Подсказки из всех доступных источников, дубли по IMO убираются."""
    results: list[dict] = []
    seen: set[str] = set()
    used: list[str] = []

    for provider in build_providers(user_vessels):
        try:
            items = await provider.search(query, limit=limit)
        except Exception:
            logger.exception("Источник %s не ответил", provider.name)
            continue
        if items:
            used.append(provider.name)
        for it in items:
            key = (it.get("imo") or it.get("mmsi") or it.get("name") or "").lower()
            if key and key in seen:
                continue
            seen.add(key)
            results.append(it)
        if len(results) >= limit:
            break

    return {"results": results[:limit], "providers": used}


async def fetch_ship(user_vessels: list[dict], ident: str) -> dict | None:
    for provider in build_providers(user_vessels):
        try:
            card = await provider.fetch(ident)
        except Exception:
            logger.exception("Источник %s не отдал карточку", provider.name)
            continue
        if card:
            return card
    return None


def provider_info() -> dict:
    """Что показать в интерфейсе про доступные источники."""
    external = bool(getattr(config, "ship_api_url", "") and getattr(config, "ship_api_token", ""))
    return {
        "external": external,
        "title": "Поиск по мировой базе судов" if external else "Поиск по своим судам",
        "note": ("Подключён внешний AIS-сервис: поиск идёт по мировой базе."
                 if external else
                 "Внешний сервис не подключён, поэтому подсказки идут по судам, "
                 "которые ты уже завёл. Карточку можно заполнить вручную один раз — "
                 "дальше она сама подставляется в расчёты."),
    }
