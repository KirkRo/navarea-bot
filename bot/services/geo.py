"""
Достаём координаты из текста предупреждения (формат DD-MM.MMN/S DDD-MM.MME/W,
изредка DD-MM-SS.SN/S, изредка с запятой вместо точки как в испанских
источниках) и переводим их в обычные градусы для карты.
"""
from __future__ import annotations

import re

_COORD_PAIR = re.compile(
    r"(\d{1,3}-\d{1,2}(?:[.,]\d+)?(?:-\d{1,2}(?:[.,]\d+)?)?)\s*([NS])\s+"
    r"(\d{1,3}-\d{1,2}(?:[.,]\d+)?(?:-\d{1,2}(?:[.,]\d+)?)?)\s*([EW])"
)


def _parse_dms(raw: str) -> float:
    raw = raw.replace(",", ".")
    parts = raw.split("-")
    deg = float(parts[0])
    minutes = float(parts[1]) if len(parts) > 1 else 0.0
    seconds = float(parts[2]) if len(parts) > 2 else 0.0
    return deg + minutes / 60 + seconds / 3600


def extract_coordinates(text: str, max_points: int = 60) -> list[tuple[float, float]]:
    """Список (широта, долгота) в обычных градусах, в порядке появления в тексте.
    max_points -- защита от совсем огромных списков (например, списки буровых)."""
    coords = []
    for lat_raw, lat_hemi, lon_raw, lon_hemi in _COORD_PAIR.findall(text):
        try:
            lat = _parse_dms(lat_raw)
            lon = _parse_dms(lon_raw)
        except ValueError:
            continue
        if lat > 90 or lon > 180:
            continue  # похоже на мусор, не координата
        if lat_hemi == "S":
            lat = -lat
        if lon_hemi == "W":
            lon = -lon
        coords.append((round(lat, 5), round(lon, 5)))
        if len(coords) >= max_points:
            break
    return coords


def centroid(coords: list[tuple[float, float]]) -> tuple[float, float]:
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)
    return round(lat, 5), round(lon, 5)


def google_maps_url(coords: list[tuple[float, float]]) -> str:
    """Запасной вариант без своего хостинга -- просто точка в центре на Google Maps."""
    lat, lon = centroid(coords)
    return f"https://www.google.com/maps?q={lat},{lon}"
