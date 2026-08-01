"""
Прокладка маршрута между портами через ключевые узлы.

Прямая ортодромия между портами -- это не маршрут: Одесса и Сингапур
соединяются линией через Турцию, Аравию и Индию. Поэтому маршрут строится
по графу: порты привязываются к ближайшему морскому бассейну, бассейны
соединены через реальные проливы и каналы (Босфор, Гибралтар, Суэц,
Баб-эль-Мандеб, Малакка, Панама, мыс Доброй Надежды, Горн и так далее),
а между соседними узлами уже идёт ортодромия.

Это не замена прокладке в ECDIS: узлов десятки, а не тысячи, обхода
отмелей и систем разделения движения тут нет. Задача скромнее -- чтобы
линия шла морем и через те же проливы, что и реальный переход, и чтобы
предупреждения отбирались вдоль правдоподобного пути.
"""
from __future__ import annotations

import math
from typing import Optional

# Узлы: проливы, каналы, мысы и открытые точки океанов
NODES: dict[str, tuple[float, float]] = {
    # Европа, Чёрное и Средиземное
    "azov": (46.0, 36.5),
    "kerch": (45.3, 36.6),
    "black_sea": (43.5, 33.0),
    "bosphorus": (41.1, 29.1),
    "dardanelles": (40.2, 26.3),
    "aegean": (37.5, 25.2),
    "e_med": (34.0, 28.0),
    "c_med": (35.5, 18.0),
    "w_med": (38.0, 6.0),
    "alboran": (36.0, -3.5),
    "gibraltar": (35.95, -5.6),
    # Атлантика
    "iberia_w": (38.0, -10.5),
    "biscay": (45.5, -7.0),
    "channel_w": (49.0, -6.0),
    "dover": (51.0, 1.5),
    "north_sea": (54.5, 4.0),
    "skagen": (57.8, 10.6),
    "baltic": (56.0, 18.0),
    "gulf_finland": (59.7, 25.0),
    "norway_sea": (65.0, 5.0),
    "barents": (70.5, 33.0),
    "irish_sea": (53.5, -5.2),
    "hebrides": (58.5, -8.0),
    "n_atlantic": (45.0, -30.0),
    "azores": (38.5, -28.0),
    "canaries": (28.0, -17.0),
    "dakar_w": (14.0, -19.5),
    "gulf_guinea": (2.0, 3.0),
    "c_atlantic": (0.0, -25.0),
    "s_atlantic": (-30.0, -15.0),
    "cape_town": (-35.0, 18.5),
    "cape_agulhas": (-36.0, 20.5),
    # Северная Америка
    "cape_race": (46.0, -52.0),
    "us_east": (38.0, -73.0),
    "florida_str": (25.0, -79.5),
    "gulf_mexico": (26.0, -90.0),
    "yucatan": (21.5, -86.0),
    "caribbean_w": (15.0, -80.0),
    "caribbean_e": (15.0, -63.0),
    "panama_atl": (9.4, -79.9),
    "panama_pac": (8.9, -79.6),
    "halifax_e": (44.0, -60.0),
    # Южная Америка
    "brazil_ne": (-5.0, -33.0),
    "brazil_se": (-25.0, -44.0),
    "plata": (-36.0, -55.0),
    "horn": (-57.0, -67.0),
    "magellan_w": (-53.5, -75.0),
    "chile_c": (-33.0, -73.5),
    "peru_c": (-12.5, -78.0),
    "galapagos": (-1.0, -90.0),
    # Индийский океан и Ближний Восток
    "suez_n": (31.3, 32.35),
    "suez_s": (29.9, 32.6),
    "red_sea_c": (20.0, 38.5),
    "bab_el_mandeb": (12.6, 43.4),
    "gulf_aden": (12.5, 47.5),
    "socotra": (12.0, 54.0),
    "hormuz": (26.6, 56.5),
    "persian_gulf": (27.5, 51.5),
    "arabian_sea": (18.0, 62.0),
    "india_w": (17.0, 71.0),
    "sri_lanka_s": (5.5, 80.5),
    "bengal": (15.0, 88.0),
    "indian_c": (-10.0, 75.0),
    "mozambique": (-20.0, 40.0),
    "madagascar_s": (-27.0, 46.0),
    "mauritius_e": (-20.0, 60.0),
    "indian_s": (-35.0, 80.0),
    # Юго-Восточная Азия и Тихий океан
    "malacca_w": (5.5, 96.0),
    "malacca_e": (1.3, 103.8),
    "singapore": (1.2, 104.0),
    "java_sea": (-5.0, 110.0),
    "lombok": (-8.8, 115.8),
    "sunda": (-6.0, 105.8),
    "s_china_sea": (12.0, 113.0),
    "luzon_str": (20.5, 121.0),
    "e_china_sea": (28.0, 124.0),
    "korea_str": (34.0, 129.0),
    "japan_e": (35.0, 141.0),
    "tsugaru": (41.5, 141.0),
    "okhotsk": (46.0, 145.0),
    "yellow_sea": (35.5, 123.0),
    "philippines_e": (13.0, 126.0),
    "sulawesi": (2.0, 125.0),
    "torres": (-10.5, 142.0),
    "arafura": (-10.0, 133.0),
    "australia_nw": (-19.0, 116.0),
    "australia_s": (-39.0, 140.0),
    "bass": (-39.5, 146.0),
    "tasman": (-38.0, 158.0),
    "nz_n": (-35.0, 174.5),
    "coral_sea": (-18.0, 155.0),
    # Тихий океан
    "n_pacific": (35.0, -170.0),
    "hawaii": (21.0, -157.5),
    "us_west": (36.0, -123.5),
    "alaska": (56.0, -150.0),
    "bering": (60.0, -175.0),
    "mexico_w": (18.0, -104.5),
    "c_pacific": (0.0, -150.0),
    "s_pacific": (-30.0, -140.0),
}

# Рёбра: между какими узлами есть проход морем
EDGES: list[tuple[str, str]] = [
    ("azov", "kerch"), ("kerch", "black_sea"), ("black_sea", "bosphorus"),
    ("bosphorus", "dardanelles"), ("dardanelles", "aegean"), ("aegean", "e_med"),
    ("aegean", "c_med"), ("e_med", "c_med"), ("e_med", "suez_n"), ("c_med", "w_med"),
    ("w_med", "alboran"), ("alboran", "gibraltar"), ("gibraltar", "iberia_w"),
    ("iberia_w", "biscay"), ("iberia_w", "canaries"), ("iberia_w", "azores"),
    ("iberia_w", "n_atlantic"), ("biscay", "channel_w"), ("channel_w", "dover"), ("channel_w", "n_atlantic"),
    ("channel_w", "irish_sea"), ("dover", "north_sea"), ("north_sea", "skagen"),
    ("north_sea", "hebrides"), ("skagen", "baltic"), ("baltic", "gulf_finland"),
    ("hebrides", "norway_sea"), ("norway_sea", "barents"), ("irish_sea", "hebrides"),
    ("hebrides", "n_atlantic"), ("n_atlantic", "azores"), ("n_atlantic", "cape_race"),
    ("azores", "canaries"), ("canaries", "dakar_w"), ("dakar_w", "gulf_guinea"),
    ("dakar_w", "c_atlantic"), ("gulf_guinea", "c_atlantic"), ("c_atlantic", "brazil_ne"),
    ("c_atlantic", "s_atlantic"), ("gulf_guinea", "s_atlantic"), ("s_atlantic", "cape_town"),
    ("cape_town", "cape_agulhas"), ("cape_agulhas", "mozambique"), ("cape_agulhas", "indian_s"),
    ("cape_agulhas", "mauritius_e"), ("cape_race", "halifax_e"), ("halifax_e", "us_east"),
    ("us_east", "florida_str"), ("florida_str", "gulf_mexico"), ("florida_str", "caribbean_e"),
    ("gulf_mexico", "yucatan"), ("yucatan", "caribbean_w"), ("caribbean_w", "caribbean_e"),
    ("caribbean_w", "panama_atl"), ("panama_atl", "panama_pac"), ("caribbean_e", "brazil_ne"),
    ("n_atlantic", "us_east"), ("brazil_ne", "brazil_se"), ("brazil_se", "plata"),
    ("plata", "horn"), ("horn", "magellan_w"), ("magellan_w", "chile_c"),
    ("chile_c", "peru_c"), ("peru_c", "panama_pac"), ("peru_c", "galapagos"),
    ("galapagos", "c_pacific"), ("panama_pac", "mexico_w"), ("mexico_w", "us_west"),
    ("us_west", "n_pacific"), ("us_west", "alaska"), ("alaska", "bering"),
    ("n_pacific", "hawaii"), ("hawaii", "c_pacific"), ("n_pacific", "japan_e"),
    ("suez_n", "suez_s"), ("suez_s", "red_sea_c"), ("red_sea_c", "bab_el_mandeb"),
    ("bab_el_mandeb", "gulf_aden"), ("gulf_aden", "socotra"), ("socotra", "arabian_sea"),
    ("arabian_sea", "hormuz"), ("hormuz", "persian_gulf"), ("arabian_sea", "india_w"),
    ("arabian_sea", "indian_c"), ("india_w", "sri_lanka_s"), ("sri_lanka_s", "bengal"),
    ("sri_lanka_s", "malacca_w"), ("sri_lanka_s", "indian_c"), ("indian_c", "malacca_w"),
    ("indian_c", "mauritius_e"), ("indian_c", "indian_s"), ("mauritius_e", "mozambique"),
    ("mozambique", "madagascar_s"), ("madagascar_s", "indian_s"), ("indian_s", "australia_s"),
    ("malacca_w", "malacca_e"), ("malacca_e", "singapore"), ("singapore", "s_china_sea"),
    ("singapore", "java_sea"), ("malacca_w", "sunda"), ("sunda", "java_sea"),
    ("java_sea", "lombok"), ("lombok", "indian_s"), ("java_sea", "arafura"),
    ("arafura", "torres"), ("torres", "coral_sea"), ("s_china_sea", "luzon_str"),
    ("s_china_sea", "philippines_e"), ("luzon_str", "e_china_sea"), ("e_china_sea", "yellow_sea"),
    ("e_china_sea", "korea_str"), ("korea_str", "japan_e"), ("japan_e", "tsugaru"),
    ("tsugaru", "okhotsk"), ("philippines_e", "sulawesi"), ("sulawesi", "coral_sea"),
    ("philippines_e", "n_pacific"), ("coral_sea", "tasman"), ("tasman", "nz_n"),
    ("tasman", "bass"), ("bass", "australia_s"), ("australia_nw", "malacca_w"),
    ("australia_nw", "indian_s"), ("australia_nw", "arafura"), ("c_pacific", "s_pacific"),
    ("s_pacific", "nz_n"), ("s_pacific", "horn"), ("japan_e", "philippines_e"),
]

R_NM = 3440.065


def _hav(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = math.radians(b[0] - a[0])
    dl = math.radians(b[1] - a[1])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_NM * math.asin(min(1.0, math.sqrt(x)))


_GRAPH: dict[str, list[tuple[str, float]]] = {}
for _a, _b in EDGES:
    _GRAPH.setdefault(_a, []).append((_b, _hav(NODES[_a], NODES[_b])))
    _GRAPH.setdefault(_b, []).append((_a, _hav(NODES[_b], NODES[_a])))


def nearest_nodes(point: tuple[float, float], count: int = 3) -> list[str]:
    """Ближайшие узлы, но только те, что реально рядом.

    Раньше брались просто три ближайших, и алгоритм выбирал из них тот,
    что давал кратчайшую сумму -- в итоге для Хьюстона стартовым узлом
    оказывалось тихоокеанское побережье Мексики, и линия срезала материк.
    Теперь узел годится, только если он не дальше чем в 1.35 раза от
    самого близкого: это отсекает "заманчивые" узлы по ту сторону суши."""
    ranked = sorted(((n, _hav(point, NODES[n])) for n in NODES), key=lambda x: x[1])
    if not ranked:
        return []
    limit = ranked[0][1] * 1.15 + 25
    return [n for n, d in ranked[:count] if d <= limit] or [ranked[0][0]]


def _dijkstra(start: str, goal: str) -> Optional[list[str]]:
    import heapq

    dist = {start: 0.0}
    prev: dict[str, str] = {}
    pq = [(0.0, start)]
    seen: set[str] = set()

    while pq:
        d, node = heapq.heappop(pq)
        if node in seen:
            continue
        seen.add(node)
        if node == goal:
            path = [node]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return list(reversed(path))
        for nxt, w in _GRAPH.get(node, []):
            nd = d + w
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                prev[nxt] = node
                heapq.heappush(pq, (nd, nxt))
    return None


def plan_route(a: tuple[float, float], b: tuple[float, float]) -> dict:
    """Строит маршрут через узлы. Возвращает точки, длину и список узлов."""
    best: Optional[tuple[float, list[str]]] = None

    # Пробуем несколько ближайших узлов с обеих сторон -- ближайший
    # географически не всегда даёт лучший путь (например, порт в Чёрном
    # море и узел в Эгейском по прямой ближе, но идти надо через Босфор).
    for sn in nearest_nodes(a, 3):
        for gn in nearest_nodes(b, 3):
            path = _dijkstra(sn, gn) if sn != gn else [sn]
            if not path:
                continue
            total = _hav(a, NODES[path[0]]) + _hav(NODES[path[-1]], b)
            for i in range(len(path) - 1):
                total += _hav(NODES[path[i]], NODES[path[i + 1]])
            if best is None or total < best[0]:
                best = (total, path)

    if best is None:
        return {"points": [a, b], "distance_nm": _hav(a, b), "waypoints": [], "direct": True}

    _total, path = best
    pts = [a] + [NODES[n] for n in path] + [b]

    # убираем узлы, которые дают петлю рядом с портом
    cleaned = [pts[0]]
    for p in pts[1:]:
        if _hav(cleaned[-1], p) > 15:
            cleaned.append(p)
    if cleaned[-1] != pts[-1]:
        cleaned.append(pts[-1])

    dist = sum(_hav(cleaned[i], cleaned[i + 1]) for i in range(len(cleaned) - 1))
    return {"points": cleaned, "distance_nm": dist, "waypoints": path, "direct": False}


def densify(points: list[tuple[float, float]], step_nm: float = 90.0) -> list[tuple[float, float]]:
    """Дробит каждый отрезок по ортодромии -- нужно, чтобы линия на карте
    выглядела дугой и чтобы коридор поиска предупреждений был сплошным."""
    out: list[tuple[float, float]] = []
    for i in range(len(points) - 1):
        p, q = points[i], points[i + 1]
        d = _hav(p, q)
        steps = max(1, min(60, int(d / step_nm)))
        lat1, lon1 = math.radians(p[0]), math.radians(p[1])
        lat2, lon2 = math.radians(q[0]), math.radians(q[1])
        ang = d / R_NM
        for s in range(steps):
            f = s / steps
            if ang < 1e-9:
                out.append(p)
                continue
            A = math.sin((1 - f) * ang) / math.sin(ang)
            B = math.sin(f * ang) / math.sin(ang)
            x = A * math.cos(lat1) * math.cos(lon1) + B * math.cos(lat2) * math.cos(lon2)
            y = A * math.cos(lat1) * math.sin(lon1) + B * math.cos(lat2) * math.sin(lon2)
            z = A * math.sin(lat1) + B * math.sin(lat2)
            out.append((math.degrees(math.atan2(z, math.hypot(x, y))),
                        math.degrees(math.atan2(y, x))))
    out.append(points[-1])
    return out


# Человекочитаемые названия узлов для списка точек поворота
NODE_TITLES = {
    "bosphorus": "Босфор", "dardanelles": "Дарданеллы", "gibraltar": "Гибралтар",
    "suez_n": "Суэцкий канал, север", "suez_s": "Суэцкий канал, юг",
    "bab_el_mandeb": "Баб-эль-Мандеб", "hormuz": "Ормузский пролив",
    "malacca_w": "Малаккский пролив, запад", "malacca_e": "Малаккский пролив, восток",
    "panama_atl": "Панамский канал, Атлантика", "panama_pac": "Панамский канал, Тихий океан",
    "cape_agulhas": "Мыс Игольный", "cape_town": "Кейптаун", "horn": "Мыс Горн",
    "magellan_w": "Магелланов пролив", "dover": "Па-де-Кале", "skagen": "Скаген",
    "kerch": "Керченский пролив", "luzon_str": "Пролив Лусон", "korea_str": "Корейский пролив",
    "torres": "Торресов пролив", "sunda": "Зондский пролив", "lombok": "Пролив Ломбок",
    "tsugaru": "Пролив Цугару", "florida_str": "Флоридский пролив", "yucatan": "Юкатанский пролив",
    "bass": "Бассов пролив", "channel_w": "Ла-Манш, западный вход", "bering": "Берингов пролив",
}
