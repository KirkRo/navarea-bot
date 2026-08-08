"""
Погода и состояние моря.

Источник -- Open-Meteo: он не требует ключа и не считает запросы, поэтому
не добавляет ни строчки в .env и не ломается, когда у бота нет денег на
платном API. Две разные ручки:

  forecast  -- атмосфера: ветер, порывы, давление, видимость, осадки
  marine    -- море: высота и период волны, зыбь, направление

Главное здесь -- route_forecast(): погоду на переходе спрашивают не
«сейчас в точке», а «что будет, когда я туда приду». Поэтому по маршруту
раскладывается время прихода на каждую точку по заданной скорости, и
прогноз берётся на этот час, а не на текущий.

Дальше трёх-пяти суток прогноз ветра в море -- уже гадание, поэтому
дальние точки маршрута честно помечаются как выходящие за горизонт
прогноза, а не заполняются числами.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WatchKeeper/1.0; maritime safety app)"}

# Дальше этого срока прогноза не спрашиваем: Open-Meteo отдаёт 16 суток,
# но для ветра и волны в открытом море всё, что дальше недели, -- шум.
MAX_FORECAST_DAYS = 7
MAX_FORECAST_HOURS = MAX_FORECAST_DAYS * 24

_HOURLY = "wind_speed_10m,wind_gusts_10m,wind_direction_10m,pressure_msl,visibility,precipitation,temperature_2m"
_MARINE_HOURLY = "wave_height,wave_direction,wave_period,swell_wave_height,swell_wave_period"


# ---------------------------------------------------------------------- #
# Единицы и словесные описания
# ---------------------------------------------------------------------- #
BEAUFORT = [
    (1, 0, "штиль"), (4, 1, "тихий"), (7, 2, "лёгкий"), (11, 3, "слабый"),
    (17, 4, "умеренный"), (22, 5, "свежий"), (28, 6, "сильный"), (34, 7, "крепкий"),
    (41, 8, "очень крепкий"), (48, 9, "шторм"), (56, 10, "сильный шторм"),
    (64, 11, "жестокий шторм"),
]


def beaufort(knots: float) -> tuple[int, str]:
    for limit, force, name in BEAUFORT:
        if knots < limit:
            return force, name
    return 12, "ураган"


def compass(deg: float | None) -> str:
    if deg is None:
        return "—"
    names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
             "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[int((deg % 360) / 22.5 + 0.5) % 16]


def _kn(v: float | None) -> float | None:
    """Ветер запрашивается сразу в узлах (wind_speed_unit=kn), пересчёт не
    нужен -- по умолчанию Open-Meteo отдаёт километры в час, и молчаливый
    пересчёт «как из м/с» завысил бы силу ветра втрое."""
    return None if v is None else round(float(v), 1)


# ---------------------------------------------------------------------- #
# Запросы
# ---------------------------------------------------------------------- #
async def _get(client: httpx.AsyncClient, url: str, params: dict) -> dict | None:
    try:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("Погода: %s не ответил (%s)", url, e)
        return None


def _pick_hour(data: dict | None, key: str, idx: int):
    """Значение из почасового ряда по номеру часа."""
    if not data:
        return None
    series = (data.get("hourly") or {}).get(key)
    if not series or idx >= len(series):
        return None
    return series[idx]


def _hour_index(data: dict | None, when: datetime) -> int | None:
    """Номер часа в ряду, ближайший к нужному времени."""
    if not data:
        return None
    times = (data.get("hourly") or {}).get("time") or []
    if not times:
        return None
    want = when.strftime("%Y-%m-%dT%H:00")
    if want in times:
        return times.index(want)
    # ряд всегда начинается с полуночи текущих суток по UTC
    try:
        first = datetime.fromisoformat(times[0]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    idx = int((when - first).total_seconds() // 3600)
    return idx if 0 <= idx < len(times) else None


def _sea_state(wave_m: float | None) -> str:
    if wave_m is None:
        return "—"
    for limit, name in ((0.1, "зеркально гладкое"), (0.5, "рябь"), (1.25, "небольшое волнение"),
                        (2.5, "умеренное волнение"), (4.0, "значительное волнение"),
                        (6.0, "крупное волнение"), (9.0, "очень крупное волнение"),
                        (14.0, "исключительно крупное волнение")):
        if wave_m < limit:
            return name
    return "аномальное волнение"


async def point_forecast(lat: float, lon: float, when: datetime | None = None,
                         days: int = 3) -> dict:
    """Погода и море в одной точке. when -- момент, на который нужен прогноз
    (по умолчанию ближайший час)."""
    when = when or datetime.now(timezone.utc)
    days = max(1, min(MAX_FORECAST_DAYS, days))
    common = {"latitude": round(lat, 3), "longitude": round(lon, 3),
              "forecast_days": days, "timezone": "UTC"}

    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        air, sea = await asyncio.gather(
            _get(client, FORECAST_URL,
                 {**common, "hourly": _HOURLY, "wind_speed_unit": "kn"}),
            _get(client, MARINE_URL, {**common, "hourly": _MARINE_HOURLY}),
        )

    idx = _hour_index(air, when)
    sidx = _hour_index(sea, when)
    if idx is None and sidx is None:
        return {"error": "no_data", "lat": lat, "lon": lon}

    wind_kn = _kn(_pick_hour(air, "wind_speed_10m", idx or 0))
    gust_kn = _kn(_pick_hour(air, "wind_gusts_10m", idx or 0))
    wdir = _pick_hour(air, "wind_direction_10m", idx or 0)
    wave = _pick_hour(sea, "wave_height", sidx or 0)
    swell = _pick_hour(sea, "swell_wave_height", sidx or 0)
    vis = _pick_hour(air, "visibility", idx or 0)

    force, force_name = beaufort(wind_kn or 0)
    return {
        "lat": round(lat, 3), "lon": round(lon, 3),
        "at": when.strftime("%Y-%m-%d %H:00 UTC"),
        "wind_kn": wind_kn, "gust_kn": gust_kn,
        "wind_from": compass(wdir), "wind_dir_deg": wdir,
        "beaufort": force, "beaufort_name": force_name,
        "wave_m": wave, "swell_m": swell,
        "wave_period_s": _pick_hour(sea, "wave_period", sidx or 0),
        "wave_from": compass(_pick_hour(sea, "wave_direction", sidx or 0)),
        "sea_state": _sea_state(wave),
        "pressure_hpa": _pick_hour(air, "pressure_msl", idx or 0),
        "air_c": _pick_hour(air, "temperature_2m", idx or 0),
        "precip_mm": _pick_hour(air, "precipitation", idx or 0),
        "visibility_nm": None if vis is None else round(vis / 1852, 1),
    }


async def route_forecast(points: list[tuple[float, float]], speed_kn: float = 12.0,
                         start_at: datetime | None = None, samples: int = 6) -> dict:
    """Погода вдоль маршрута с учётом времени прихода в каждую точку.

    points -- уже проложенный маршрут (из voyage.planned_route).
    Берём не все точки, а несколько равномерных: больше запросов не даст
    ничего нового, а времени и трафика съест заметно."""
    from .voyage import haversine_nm

    if len(points) < 2:
        return {"error": "no_route"}
    speed_kn = max(3.0, min(30.0, float(speed_kn or 12.0)))
    start_at = start_at or datetime.now(timezone.utc)

    # накопленное расстояние по маршруту
    cum = [0.0]
    for i in range(1, len(points)):
        cum.append(cum[-1] + haversine_nm(points[i - 1][0], points[i - 1][1],
                                          points[i][0], points[i][1]))
    total = cum[-1]
    samples = max(2, min(10, samples))

    picks, seen = [], set()
    for k in range(samples):
        target = total * k / (samples - 1)
        idx = min(range(len(cum)), key=lambda i: abs(cum[i] - target))
        # На коротком маршруте точек меньше, чем запрошенных проб, и соседние
        # пробы попадают в одну и ту же точку. Повтор -- это лишний запрос
        # к погоде и дублирующаяся строка в ответе.
        if idx in seen:
            continue
        seen.add(idx)
        hours = cum[idx] / speed_kn
        picks.append((points[idx], cum[idx], start_at + timedelta(hours=hours), hours))

    async def one(pt, dist, when, hours):
        if hours > MAX_FORECAST_HOURS:
            return {"lat": round(pt[0], 3), "lon": round(pt[1], 3),
                    "distance_nm": round(dist), "eta_hours": round(hours),
                    "at": when.strftime("%Y-%m-%d %H:00 UTC"),
                    "beyond_forecast": True}
        f = await point_forecast(pt[0], pt[1], when=when, days=MAX_FORECAST_DAYS)
        f["distance_nm"] = round(dist)
        f["eta_hours"] = round(hours)
        return f

    legs = await asyncio.gather(*[one(*p) for p in picks])
    legs = [dict(x) for x in legs]

    inside = [x for x in legs if not x.get("beyond_forecast") and x.get("wind_kn") is not None]
    worst = max(inside, key=lambda x: x["wind_kn"]) if inside else None

    return {
        "distance_nm": round(total),
        "speed_kn": speed_kn,
        "passage_hours": round(total / speed_kn, 1),
        "start_at": start_at.strftime("%Y-%m-%d %H:00 UTC"),
        "eta": (start_at + timedelta(hours=total / speed_kn)).strftime("%Y-%m-%d %H:00 UTC"),
        "forecast_horizon_days": MAX_FORECAST_DAYS,
        "legs": legs,
        "worst": worst,
    }


async def geocode(name: str) -> dict | None:
    """Координаты населённого пункта -- на случай, когда порта нет в нашем
    справочнике, а человек всё равно про него спрашивает."""
    if not name or len(name.strip()) < 2:
        return None
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        data = await _get(client, GEOCODE_URL, {"name": name.strip(), "count": 1, "language": "ru"})
    results = (data or {}).get("results") or []
    if not results:
        return None
    r = results[0]
    return {"label": ", ".join(x for x in (r.get("name"), r.get("country")) if x),
            "lat": r.get("latitude"), "lon": r.get("longitude")}
