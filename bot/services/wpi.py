"""
Справочник портов мира из World Port Index (NGA Pub. 150, издание 27, 2019).

3559 портов с координатами, типом гавани, укрытием и средней величиной
прилива. Лежит рядом в bot/data/wpi_ports.json и грузится с диска, поэтому
работает без сети: в рейсе это и есть основной сценарий.

Величина прилива здесь справочная, средняя по порту. Предвычисления на
дату и час она не заменяет и заменять не может: для этого нужны гармоники
конкретного поста, которых в Pub. 150 нет. Зато на вопрос «насколько
вообще ходит вода в этом порту» отвечает, а именно он возникает при
планировании подхода и расчёте запаса под килём.

Названия в Pub. 150 официальные и иногда расходятся с бытовыми: Одесса
записана как Odesa, Сингапур как Keppel - (East Singapore). Поэтому поиск
идёт и по списку бытовых написаний (ALIASES), иначе человек ищет знакомое
слово и ничего не находит.
"""
from __future__ import annotations

import json
import logging
import math
import pathlib

logger = logging.getLogger(__name__)

DATA_FILE = pathlib.Path(__file__).resolve().parent.parent / "data" / "wpi_ports.json"

HARBOR_TYPES = {
    "CN": ("прибрежная природная", "coastal natural"),
    "CB": ("прибрежная с молом", "coastal breakwater"),
    "CT": ("прибрежная со шлюзом", "coastal tide gate"),
    "RN": ("речная природная", "river natural"),
    "RB": ("речной бассейн", "river basin"),
    "RT": ("речная со шлюзом", "river tide gate"),
    "LC": ("озеро или канал", "lake or canal"),
    "OR": ("открытый рейд", "open roadstead"),
    "TH": ("тайфунная гавань", "typhoon harbor"),
}
HARBOR_SIZES = {"L": ("большая", "large"), "M": ("средняя", "medium"),
                "S": ("малая", "small"), "V": ("очень малая", "very small")}
SHELTER = {"E": ("отличное", "excellent"), "G": ("хорошее", "good"),
           "F": ("среднее", "fair"), "P": ("плохое", "poor"), "N": ("нет", "none")}

# Бытовые написания, по которым порт ищут чаще, чем по официальному имени
ALIASES = {
    "одесса": "odesa", "odessa": "odesa",
    "сингапур": "singapore", "singapore": "keppel",
    "стамбул": "istanbul", "istanbul": "istanbul",
    "новороссийск": "novorossiysk", "владивосток": "vladivostok",
    "роттердам": "rotterdam", "гамбург": "hamburg", "антверпен": "antwerp",
    "шанхай": "shanghai", "гонконг": "hong kong", "пирей": "piraievs",
    "пирейс": "piraievs", "гибралтар": "gibraltar", "мальта": "valletta",
    "суэц": "suez", "панама": "balboa", "роттердам порт": "rotterdam",
}

_ports: list[dict] | None = None


def _load() -> list[dict]:
    """Читаем файл один раз на процесс: 430 КБ разбираются заметно дольше,
    чем длится обычный запрос, и повторять это на каждый поиск незачем."""
    global _ports
    if _ports is None:
        try:
            with open(DATA_FILE, encoding="utf-8") as fh:
                _ports = json.load(fh)
        except Exception:
            logger.exception("Справочник портов не прочитался: %s", DATA_FILE)
            _ports = []
    return _ports


def count() -> int:
    return len(_load())


def _describe(port: dict, lang: str = "ru") -> dict:
    i = 0 if lang == "ru" else 1
    out = dict(port)
    if port.get("type") in HARBOR_TYPES:
        out["type_text"] = HARBOR_TYPES[port["type"]][i]
    if port.get("size") in HARBOR_SIZES:
        out["size_text"] = HARBOR_SIZES[port["size"]][i]
    if port.get("shelter") in SHELTER:
        out["shelter_text"] = SHELTER[port["shelter"]][i]
    return out


def search(query: str, limit: int = 12, lang: str = "ru") -> list[dict]:
    """Поиск по названию. Совпадение с начала названия важнее совпадения
    в середине: по запросу «порт» первым должен идти Портленд, а не
    Ньюпорт."""
    q = " ".join((query or "").lower().split())
    if len(q) < 2:
        return []
    q = ALIASES.get(q, q)

    starts, inside = [], []
    for port in _load():
        name = port["name"].lower()
        if name.startswith(q):
            starts.append(port)
        elif q in name:
            inside.append(port)
        if len(starts) >= limit:
            break
    return [_describe(p, lang) for p in (starts + inside)[:limit]]


def nearest(lat: float, lon: float, limit: int = 5, lang: str = "ru") -> list[dict]:
    """Ближайшие порты к точке. Расстояние считаем по сфере, а не по
    разнице координат: на широте 60 градусов один градус долготы вдвое
    короче градуса широты, и без поправки ближайшим окажется не тот порт."""
    out = []
    for port in _load():
        d = distance_nm(lat, lon, port["lat"], port["lon"])
        out.append((d, port))
    out.sort(key=lambda x: x[0])
    result = []
    for d, port in out[:limit]:
        item = _describe(port, lang)
        item["distance_nm"] = round(d, 1)
        result.append(item)
    return result


def distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r1, r2 = math.radians(lat1), math.radians(lat2)
    dlat = r2 - r1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(r1) * math.cos(r2) * math.sin(dlon / 2) ** 2
    return 2 * math.asin(min(1.0, math.sqrt(a))) * 3440.065


def by_id(port_id: int, lang: str = "ru") -> dict | None:
    for port in _load():
        if port["id"] == port_id:
            return _describe(port, lang)
    return None


def tide_note(port: dict, lang: str = "ru") -> str:
    """Короткая строка про приливы для карточки порта."""
    metres = port.get("tide_m")
    if not metres:
        return ("Средняя величина прилива в справочнике не указана"
                if lang == "ru" else "Mean tide range is not listed")
    if lang != "ru":
        return f"Mean tide range {metres} m ({port.get('tide_ft')} ft)"
    return f"Средняя величина прилива {metres} м ({port.get('tide_ft')} фут)"
