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


# ---------------------------------------------------------------------- #
# Разбор геометрии: одно предупреждение может описывать НЕСКОЛЬКО фигур
# ---------------------------------------------------------------------- #

# Что стоит перед группой координат -- по этому понимаем, что рисовать
_POLYGON_HINTS = (
    "BOUND BY", "BOUNDED BY", "BOUNDARY", "IN AREA", "IN AREAS", "AREA BOUND",
    "DELIMITED BY", "DELIMITADA POR", "DELIMITADO POR", "ZONA", "AREA WITHIN",
    "AREA DELIMITED", "LIMITED BY", "AREA:", "AREAS:", "WITHIN THE AREA",
    "AREA ENCLOSED", "ENCLOSED BY", "AREA FORMED", "POLYGON", "PERIMETER",
    "OPERATIONS IN", "EXERCISES IN", "FIRINGS IN", "SURVEY IN", "OPERATIONS AREA",
    "HAZARDOUS OPERATIONS", "SEISMIC SURVEY", "PROHIBITED IN", "AREA COMPRISED",
    "COMPRENDIDA", "COMPRISED BY", "AREA LIMITED", "AVOID AREA", "DANGER AREA",
)
_LINE_HINTS = (
    "TRACKLINE", "LINE JOINING", "JOINING", "ALONG TRACK", "ALONG THE LINE",
    "TRACK JOINING", "LINEA", "LINE FROM", "ALONG A LINE", "ROUTE", "LANE",
    "PIPELINE", "CABLE OPERATIONS", "CABLE ROUTE", "ALONG THE TRACK",
)

# Разделители, которые НЕ разрывают группу координат (перечисление внутри одной фигуры)
_SEPARATOR_ONLY = re.compile(r"^[\s,;.\-]*(?:AND|TO|Y|E)?[\s,;.\-]*$", re.IGNORECASE)


def _classify(prefix: str) -> str:
    """Чем является группа координат, судя по тексту перед ней."""
    upper = prefix.upper()
    pos_poly = max((upper.rfind(k) for k in _POLYGON_HINTS), default=-1)
    pos_line = max((upper.rfind(k) for k in _LINE_HINTS), default=-1)
    if pos_line > pos_poly:
        return "line"
    if pos_poly >= 0:
        return "polygon"
    return "points"


def extract_shapes(text: str, max_shapes: int = 40) -> list[dict]:
    """Разбирает текст предупреждения на отдельные фигуры.

    Одно сообщение сплошь и рядом описывает несколько НЕ связанных между
    собой объектов: районы A, B, C, список позиций буровых, перечень
    погасших огней. Если свалить все координаты в один полигон, получится
    бессмыслица -- контур через пол-Средиземного моря, соединяющий точки,
    которые друг к другу отношения не имеют. Поэтому координаты сначала
    группируются по признаку "идут в тексте подряд, разделены только
    запятой или словом AND", а тип фигуры определяется по словам перед
    группой (BOUND BY -> полигон, TRACKLINE JOINING -> линия, иначе точки).

    Возвращает список вида
        [{"type": "polygon"|"line"|"point", "points": [[lat, lon], ...]}, ...]
    """
    matches = list(_COORD_PAIR.finditer(text))
    if not matches:
        return []

    # 1) группируем подряд идущие координаты
    groups: list[list] = []
    current: list = []
    prev_end = None
    for m in matches:
        if prev_end is not None:
            between = text[prev_end:m.start()]
            if not _SEPARATOR_ONLY.match(between):
                if current:
                    groups.append(current)
                current = []
        current.append(m)
        prev_end = m.end()
    if current:
        groups.append(current)

    # 2) превращаем группы в фигуры
    shapes: list[dict] = []
    for group in groups[:max_shapes]:
        pts = []
        for m in group:
            lat_raw, lat_hemi, lon_raw, lon_hemi = m.group(1), m.group(2), m.group(3), m.group(4)
            try:
                lat, lon = _parse_dms(lat_raw), _parse_dms(lon_raw)
            except ValueError:
                continue
            if lat > 90 or lon > 180:
                continue
            if lat_hemi == "S":
                lat = -lat
            if lon_hemi == "W":
                lon = -lon
            pts.append([round(lat, 5), round(lon, 5)])
        if not pts:
            continue

        # Окно поиска подсказки широкое: в реальных сообщениях между словами
        # "IN AREA BOUND BY" и первой координатой нередко вклинивается название
        # судна, даты и прочее на 200+ символов.
        kind = _classify(text[max(0, group[0].start() - 320):group[0].start()])

        if len(pts) == 1:
            shapes.append({"type": "point", "points": pts})
        elif len(pts) == 2:
            shapes.append({"type": "line" if kind != "points" else "point", "points": pts})
        elif kind == "polygon":
            shapes.append({"type": "polygon", "points": pts})
        elif kind == "line":
            shapes.append({"type": "line", "points": pts})
        elif len(pts) >= 4:
            # Четыре и больше координат подряд, перечисленных через запятую --
            # это практически всегда обход контура района, даже если ключевого
            # слова рядом не нашлось. Отдельные объекты (буровые, огни) так
            # подряд не перечисляют, у них между координатами идут названия.
            shapes.append({"type": "polygon", "points": pts})
        else:
            # перечисление отдельных позиций (буровые, огни) -- каждая сама по себе
            for p in pts:
                shapes.append({"type": "point", "points": [p]})

    return shapes[:max_shapes]
