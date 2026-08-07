"""
Тропические циклоны и их близость к маршруту.

Источник -- открытая сводка Национального центра ураганов США
(nhc.noaa.gov/CurrentStorms.json), ключа не требует. Оттуда берётся
текущее положение, интенсивность, давление и направление перемещения,
а прогноз пути разбирается из текста штормового предупреждения (TCM),
где положения даются на 12, 24, 36, 48, 72, 96 и 120 часов.

Честно о покрытии: NHC ведёт Атлантику и восточную часть Тихого океана.
Тайфуны западной части Тихого океана -- зона ответственности JTWC, и
открытой сводки в таком же виде у него нет. Поэтому в приложении прямо
написано, какие бассейны покрыты, а не создаётся впечатление, что видны
все циклоны мира.

Главное здесь -- не карта, а ответ на вопрос "мешает ли он мне":
расстояние от циклона до линии маршрута, точка наибольшего сближения и
время, когда это произойдёт.
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

CURRENT_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
_TIMEOUT = 20.0

# Классификация NHC -> человеческое название
KINDS = {
    "TD": "Тропическая депрессия", "TS": "Тропический шторм",
    "HU": "Ураган", "TY": "Тайфун", "STD": "Субтропическая депрессия",
    "STS": "Субтропический шторм", "PTC": "Посттропический циклон",
    "PC": "Потенциальный тропический циклон", "SD": "Субтропическая депрессия",
    "SS": "Субтропический шторм", "EX": "Внетропический циклон",
}

# Шкала Саффира-Симпсона по максимальному ветру в узлах
def category(wind_kt: float | None) -> str:
    if wind_kt is None:
        return ""
    w = float(wind_kt)
    if w >= 137: return "5 категория"
    if w >= 113: return "4 категория"
    if w >= 96:  return "3 категория"
    if w >= 83:  return "2 категория"
    if w >= 64:  return "1 категория"
    if w >= 34:  return "штормовой"
    return "депрессия"


R_NM = 3440.065


def _hav(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = math.radians(b[0] - a[0])
    dl = math.radians(b[1] - a[1])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_NM * math.asin(min(1.0, math.sqrt(x)))


def _point_to_segment_nm(p, a, b) -> float:
    """Расстояние от точки до отрезка. На масштабах в сотни миль плоское
    приближение с поправкой на схождение меридианов даёт погрешность
    заметно меньше, чем разброс самого прогноза пути."""
    latm = math.radians((a[0] + b[0]) / 2)
    kx = math.cos(latm)
    ax, ay = a[1] * kx, a[0]
    bx, by = b[1] * kx, b[0]
    px, py = p[1] * kx, p[0]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return _hav(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    proj = (ay + t * dy, (ax + t * dx) / kx)
    return _hav(p, proj)


def distance_to_route(point, route: list) -> float | None:
    """Кратчайшее расстояние от точки до ломаной маршрута."""
    if not route or len(route) < 2:
        return None
    best = None
    for i in range(len(route) - 1):
        d = _point_to_segment_nm(point, route[i], route[i + 1])
        if best is None or d < best:
            best = d
    return best


# ---------------------------------------------------------------------- #
# Разбор прогноза пути из текста предупреждения
# ---------------------------------------------------------------------- #
# В тексте TCM положения даются строками вида:
#   FORECAST VALID 12/1800Z 25.5N  76.3W
#   MAX WIND  85 KT...GUSTS 105 KT.
_FC_POS = re.compile(
    r"FORECAST VALID\s+(\d{2})/(\d{4})Z\s+(\d+\.?\d*)([NS])\s+(\d+\.?\d*)([EW])",
    re.I,
)
_FC_WIND = re.compile(r"MAX WIND\s+(\d+)\s*KT", re.I)


def parse_forecast(text: str) -> list[dict]:
    """Достаёт прогнозные положения. Ветер берётся из строки, следующей
    за положением -- в TCM они идут парами."""
    if not text:
        return []
    out: list[dict] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _FC_POS.search(line)
        if not m:
            continue
        day, hhmm, la, ns, lo, ew = m.groups()
        lat = float(la) * (1 if ns.upper() == "N" else -1)
        lon = float(lo) * (1 if ew.upper() == "E" else -1)
        wind = None
        for j in range(i + 1, min(i + 4, len(lines))):
            w = _FC_WIND.search(lines[j])
            if w:
                wind = int(w.group(1))
                break
        out.append({"day": int(day), "hhmm": hhmm, "lat": lat, "lon": lon, "wind_kt": wind})
    return out


def _forecast_times(points: list[dict], issued: datetime | None = None) -> list[dict]:
    """Восстанавливает полные даты: в тексте есть только день месяца и время."""
    if not points:
        return []
    base = issued or datetime.now(timezone.utc)
    out = []
    prev = None
    for p in points:
        hh, mm = int(p["hhmm"][:2]), int(p["hhmm"][2:])
        t = base.replace(day=1, hour=hh, minute=mm, second=0, microsecond=0)
        # подбираем месяц так, чтобы день совпал и время шло вперёд
        for delta_month in (0, 1):
            month = base.month + delta_month
            year = base.year + (1 if month > 12 else 0)
            month = month - 12 if month > 12 else month
            try:
                cand = t.replace(year=year, month=month, day=p["day"])
            except ValueError:
                continue
            if prev is None or cand >= prev:
                t = cand
                break
        prev = t
        q = dict(p)
        q["at"] = t.isoformat()
        out.append(q)
    return out


# ---------------------------------------------------------------------- #
# Получение данных
# ---------------------------------------------------------------------- #
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Watchkeeper/1.0; maritime safety app)",
    "Accept": "application/json,text/plain,*/*",
}


async def fetch_storms(with_forecast: bool = True) -> list[dict]:
    """Активные циклоны со сводки NHC. Прогноз пути подтягивается отдельно
    для каждого шторма -- это ещё один запрос, поэтому его можно отключить."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
        resp = await client.get(CURRENT_URL)
        resp.raise_for_status()
        data = resp.json()

        storms = []
        for raw in (data.get("activeStorms") or []):
            s = _normalize(raw)
            if s is None:
                continue
            if with_forecast and raw.get("forecastAdvisory"):
                url = _advisory_url(raw["forecastAdvisory"])
                if url:
                    try:
                        r = await client.get(url)
                        if r.status_code == 200:
                            s["forecast"] = _forecast_times(parse_forecast(r.text))
                    except Exception as e:
                        logger.debug("Прогноз пути для %s не получен: %s", s.get("id"), e)
            storms.append(s)
        return storms


def _advisory_url(node) -> str | None:
    """В сводке ссылка лежит объектом с полями url/text либо строкой."""
    if isinstance(node, dict):
        for k in ("url", "text", "href"):
            v = node.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
    if isinstance(node, str) and node.startswith("http"):
        return node
    return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _normalize(raw: dict) -> dict | None:
    """Приводит запись к своему виду. Названия полей у NHC менялись, поэтому
    каждое значение ищется в нескольких возможных местах."""
    lat = _num(raw.get("latitudeNumeric"))
    lon = _num(raw.get("longitudeNumeric"))
    if lat is None or lon is None:
        # запасной путь: разобрать строковые "25.5N" / "76.3W"
        m = re.match(r"(\d+\.?\d*)\s*([NS])", str(raw.get("latitude") or ""))
        if m:
            lat = float(m.group(1)) * (1 if m.group(2).upper() == "N" else -1)
        m = re.match(r"(\d+\.?\d*)\s*([EW])", str(raw.get("longitude") or ""))
        if m:
            lon = float(m.group(1)) * (1 if m.group(2).upper() == "E" else -1)
    if lat is None or lon is None:
        return None

    cls = (raw.get("classification") or "").upper()
    wind = _num(raw.get("intensity"))
    return {
        "id": raw.get("id") or raw.get("binNumber") or "",
        "name": raw.get("name") or "",
        "basin": (raw.get("id") or "")[:2].upper(),
        "classification": cls,
        "kind": KINDS.get(cls, cls or "Циклон"),
        "category": category(wind),
        "lat": lat, "lon": lon,
        "wind_kt": wind,
        "gust_kt": _num(raw.get("gusts")),
        "pressure_mb": _num(raw.get("pressure")),
        "movement_dir": _num(raw.get("movementDir")),
        "movement_kt": _num(raw.get("movementSpeed")),
        "updated": raw.get("lastUpdate") or "",
        "advisory": raw.get("advisoryNumber") or "",
        "forecast": [],
    }


def analyse_route(storm: dict, route: list) -> dict:
    """Мешает ли циклон маршруту: расстояние сейчас, наибольшее сближение
    по прогнозу и когда оно случится."""
    now_d = distance_to_route((storm["lat"], storm["lon"]), route)
    closest, closest_at = now_d, None

    for p in (storm.get("forecast") or []):
        d = distance_to_route((p["lat"], p["lon"]), route)
        if d is None:
            continue
        if closest is None or d < closest:
            closest, closest_at = d, p.get("at")

    return {
        "distance_now_nm": round(now_d) if now_d is not None else None,
        "closest_nm": round(closest) if closest is not None else None,
        "closest_at": closest_at,
    }


def danger_level(distance_nm: float | None, wind_kt: float | None) -> str:
    """Насколько это важно для вахты. Пороги взяты по здравому смыслу:
    сотня миль до урагана -- это уже зона штормовых ветров и зыби."""
    if distance_nm is None:
        return "info"
    if distance_nm < 100:
        return "critical"
    if distance_nm < 300:
        return "warning"
    if distance_nm < 600:
        return "watch"
    return "info"
