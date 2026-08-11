"""
Координаты из текста предупреждения.

Каждый координатор пишет их по-своему, и это не мелочь: не разобрали формат
-- предупреждение осталось без метки на карте, разобрали неверно -- метка
встала не туда, что хуже отсутствия метки. Поэтому здесь собраны все записи,
которые реально встречаются в сообщениях NAVAREA и NAVTEX:

    44-30.5N 030-15.2E      NGA, UKHO -- градусы-минуты через дефис
    44-30-15N 030-15-40E    они же, с секундами
    44°30'.5N 030°15'.2E    UKHO и европейские источники
    44°30'15"N 030°15'40"E  с секундами и знаком секунд
    44 30.5N 030 15.2E      пробел вместо дефиса
    N44 30.5 E030 15.2      полушарие впереди -- Франция, Испания, Норвегия
    44,5N 30,25E            десятичные градусы с запятой -- испанские источники
    44-30.0N/030-15.0E      разделитель косой чертой без пробела

Правильность важнее полноты: если минуты или секунды выходят за 60, а
широта за 90 -- это не координата, а номер сообщения, дата или частота,
и такая пара отбрасывается.
"""
from __future__ import annotations

import re

# Одна величина: градусы и, необязательно, минуты и секунды.
# Разделителем служит дефис, пробел, знак градуса или апостроф.
_VAL = r"""
    \d{1,3}                                   # градусы
    (?:
        \s*[°°]\s*\d{1,2}(?:['′]\s*)?(?:[.,]\d+)?   # 44°30'.5
        (?:\s*\d{1,2}(?:[.,]\d+)?\s*["″])?               # ...15"
      | [-\s]\d{1,2}(?:[.,]\d+)?                              # 44-30.5 / 44 30.5
        (?:[-\s]\d{1,2}(?:[.,]\d+)?)?                         # ...-15
      | [.,]\d+                                               # 44.5 десятичные
    )?
"""

# Полушарие после величины: 44-30.5N 030-15.2E
_PAIR_SUFFIX = re.compile(
    rf"(?P<lat>{_VAL})\s*(?P<lath>[NS])"
    # Между широтой и долготой встречается что угодно: пробел, запятая,
    # косая черта и тире -- испанский источник пишет «43 00.23 N - 032 51.55 E».
    rf"[\s,;/-]+"
    rf"(?P<lon>{_VAL})\s*(?P<lonh>[EW])",
    re.VERBOSE,
)
# Полушарие перед величиной: N44 30.5 E030 15.2
_PAIR_PREFIX = re.compile(
    rf"(?P<lath>[NS])\s*(?P<lat>{_VAL})"
    # Между широтой и долготой встречается что угодно: пробел, запятая,
    # косая черта и тире -- испанский источник пишет «43 00.23 N - 032 51.55 E».
    rf"[\s,;/-]+"
    rf"(?P<lonh>[EW])\s*(?P<lon>{_VAL})",
    re.VERBOSE,
)


def _parse_value(raw: str) -> float | None:
    """Градусы-минуты-секунды или десятичные градусы -> градусы.

    None, если запись не похожа на координату: минуты или секунды больше
    шестидесяти означают, что это что-то другое."""
    s = raw.replace(",", ".").strip()
    # 44°30'.5 -- десятая доля минуты пишется после знака минут. Убираем знак,
    # чтобы получилось 44°30.5, иначе .5 читалось бы как полсекунды.
    s = re.sub(r"['′]\s*(?=\.\d)", "", s)
    s = s.replace("°", " ").replace("°", " ")
    s = s.replace("'", " ").replace("′", " ")
    s = s.replace('"', " ").replace("″", " ")
    s = s.replace("-", " ")
    parts = [p for p in s.split() if p]
    if not parts:
        return None

    try:
        # Одна часть: либо целые градусы, либо десятичные
        if len(parts) == 1:
            return float(parts[0])
        deg = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2]) if len(parts) > 2 else 0.0
    except ValueError:
        return None

    if minutes >= 60 or seconds >= 60:
        return None
    if deg != int(deg):          # градусы с дробной частью И минуты -- бессмыслица
        return None
    return deg + minutes / 60 + seconds / 3600


def _finish(lat: float | None, lath: str, lon: float | None, lonh: str):
    if lat is None or lon is None:
        return None
    if lat > 90 or lon > 180:
        return None
    if lath == "S":
        lat = -lat
    if lonh == "W":
        lon = -lon
    return (round(lat, 5), round(lon, 5))


def _iter_pairs(text: str):
    """Все пары координат в порядке появления, без перекрытий.

    Оба написания ищутся по одному тексту, поэтому найденные куски
    сравниваются по положению: иначе «N44 30.5 E030 15.2» дал бы и пару
    с полушарием впереди, и обрывок следующей записи."""
    found = []
    for rx, order in ((_PAIR_SUFFIX, "suffix"), (_PAIR_PREFIX, "prefix")):
        for m in rx.finditer(text):
            found.append((m.start(), m.end(), m, order))
    found.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    used_to = -1
    for start, end, m, _order in found:
        if start < used_to:
            continue                       # перекрывается с уже взятой парой
        pt = _finish(_parse_value(m.group("lat")), m.group("lath"),
                     _parse_value(m.group("lon")), m.group("lonh"))
        if pt is None:
            continue
        used_to = end
        yield start, end, pt


def extract_coordinates(text: str, max_points: int = 60) -> list[tuple[float, float]]:
    """Список (широта, долгота) в обычных градусах, в порядке появления в тексте.
    max_points -- защита от совсем огромных списков (например, списки буровых)."""
    coords = []
    for _s, _e, pt in _iter_pairs(text):
        coords.append(pt)
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
    matches = list(_iter_pairs(text))
    if not matches:
        return []

    # 1) группируем подряд идущие координаты
    groups: list[list] = []
    current: list = []
    prev_end = None
    for start, end, pt in matches:
        if prev_end is not None:
            between = text[prev_end:start]
            if not _SEPARATOR_ONLY.match(between):
                if current:
                    groups.append(current)
                current = []
        current.append((start, end, pt))
        prev_end = end
    if current:
        groups.append(current)

    # 2) превращаем группы в фигуры
    shapes: list[dict] = []
    for group in groups[:max_shapes]:
        pts = [[pt[0], pt[1]] for _s, _e, pt in group]
        if not pts:
            continue

        # Окно поиска подсказки широкое: в реальных сообщениях между словами
        # "IN AREA BOUND BY" и первой координатой нередко вклинивается название
        # судна, даты и прочее на 200+ символов.
        kind = _classify(text[max(0, group[0][0] - 320):group[0][0]])

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
