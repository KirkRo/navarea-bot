"""
Планирование перехода: порт отправления -> порт прибытия, и какие
действующие предупреждения попадают в коридор вдоль маршрута.

Маршрут считается по ортодромии (great circle) -- это не настоящая
прокладка с обходом берега, а прямая по сфере. Для отбора предупреждений
этого достаточно: коридор берётся широкий (по умолчанию 150 миль в
каждую сторону), и лучше показать лишнее, чем пропустить опасность.
Настоящую прокладку всё равно делает штурман в ECDIS, бот только
подсказывает, на что посмотреть.

Список портов -- курируемый вручную, основные торговые порты мира с
упором на Европу, Атлантику, Карибы и Южную Америку. Он заведомо не
полный: если порта нет, в Mini App можно ввести координаты вручную
в формате "43.3N 5.4E" или просто "43.3,5.4".
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

EARTH_RADIUS_NM = 3440.065  # радиус Земли в морских милях


@dataclass
class Port:
    name: str
    country: str
    lat: float
    lon: float

    @property
    def label(self) -> str:
        return f"{self.name}, {self.country}"


# ---------------------------------------------------------------------- #
# Список портов (name, country, lat, lon)
# ---------------------------------------------------------------------- #
PORTS: list[Port] = [Port(*p) for p in [
    # --- Северная Европа ---
    ("Rotterdam", "Нидерланды", 51.95, 4.14),
    ("Amsterdam", "Нидерланды", 52.42, 4.80),
    ("Antwerp", "Бельгия", 51.26, 4.40),
    ("Zeebrugge", "Бельгия", 51.33, 3.20),
    ("Hamburg", "Германия", 53.54, 9.97),
    ("Bremerhaven", "Германия", 53.55, 8.57),
    ("Wilhelmshaven", "Германия", 53.51, 8.15),
    ("Le Havre", "Франция", 49.48, 0.11),
    ("Dunkirk", "Франция", 51.05, 2.37),
    ("Calais", "Франция", 50.97, 1.86),
    ("London Gateway", "Великобритания", 51.51, 0.48),
    ("Felixstowe", "Великобритания", 51.95, 1.32),
    ("Southampton", "Великобритания", 50.90, -1.40),
    ("Liverpool", "Великобритания", 53.43, -3.00),
    ("Immingham", "Великобритания", 53.63, -0.19),
    ("Dublin", "Ирландия", 53.35, -6.21),
    ("Copenhagen", "Дания", 55.70, 12.60),
    ("Aarhus", "Дания", 56.15, 10.22),
    ("Gothenburg", "Швеция", 57.69, 11.86),
    ("Stockholm", "Швеция", 59.32, 18.14),
    ("Oslo", "Норвегия", 59.90, 10.75),
    ("Bergen", "Норвегия", 60.40, 5.32),
    ("Stavanger", "Норвегия", 58.97, 5.73),
    ("Trondheim", "Норвегия", 63.44, 10.40),
    ("Narvik", "Норвегия", 68.44, 17.43),
    ("Helsinki", "Финляндия", 60.15, 24.96),
    ("Kotka", "Финляндия", 60.46, 26.95),
    ("Tallinn", "Эстония", 59.45, 24.77),
    ("Riga", "Латвия", 56.98, 24.09),
    ("Klaipeda", "Литва", 55.71, 21.13),
    ("Gdansk", "Польша", 54.40, 18.68),
    ("Gdynia", "Польша", 54.53, 18.55),
    ("St Petersburg", "Россия", 59.90, 30.25),
    ("Ust-Luga", "Россия", 59.67, 28.40),
    ("Murmansk", "Россия", 68.97, 33.05),
    ("Reykjavik", "Исландия", 64.15, -21.94),

    # --- Западная Европа и Атлантика ---
    ("Brest", "Франция", 48.38, -4.49),
    ("Saint-Nazaire", "Франция", 47.27, -2.20),
    ("Bordeaux", "Франция", 44.87, -0.55),
    ("Bilbao", "Испания", 43.35, -3.02),
    ("Vigo", "Испания", 42.24, -8.73),
    ("Leixoes", "Португалия", 41.19, -8.70),
    ("Lisbon", "Португалия", 38.70, -9.15),
    ("Sines", "Португалия", 37.95, -8.87),
    ("Cadiz", "Испания", 36.53, -6.28),
    ("Algeciras", "Испания", 36.13, -5.44),
    ("Gibraltar", "Гибралтар", 36.14, -5.36),
    ("Las Palmas", "Испания", 28.14, -15.41),
    ("Tenerife", "Испания", 28.47, -16.24),
    ("Casablanca", "Марокко", 33.60, -7.61),
    ("Tanger Med", "Марокко", 35.88, -5.51),
    ("Dakar", "Сенегал", 14.68, -17.42),
    ("Abidjan", "Кот-д'Ивуар", 5.25, -4.00),
    ("Tema", "Гана", 5.63, 0.01),
    ("Lagos", "Нигерия", 6.44, 3.38),
    ("Luanda", "Ангола", -8.78, 13.23),
    ("Walvis Bay", "Намибия", -22.95, 14.50),
    ("Cape Town", "ЮАР", -33.91, 18.43),
    ("Durban", "ЮАР", -29.87, 31.03),

    # --- Средиземное и Чёрное море ---
    ("Barcelona", "Испания", 41.35, 2.17),
    ("Valencia", "Испания", 39.44, -0.31),
    ("Marseille", "Франция", 43.34, 5.35),
    ("Genoa", "Италия", 44.40, 8.92),
    ("La Spezia", "Италия", 44.10, 9.83),
    ("Livorno", "Италия", 43.55, 10.30),
    ("Naples", "Италия", 40.84, 14.26),
    ("Gioia Tauro", "Италия", 38.45, 15.90),
    ("Taranto", "Италия", 40.47, 17.22),
    ("Trieste", "Италия", 45.65, 13.76),
    ("Venice", "Италия", 45.44, 12.29),
    ("Koper", "Словения", 45.55, 13.73),
    ("Rijeka", "Хорватия", 45.33, 14.44),
    ("Piraeus", "Греция", 37.94, 23.63),
    ("Thessaloniki", "Греция", 40.63, 22.93),
    ("Malta Freeport", "Мальта", 35.82, 14.53),
    ("Valletta", "Мальта", 35.90, 14.51),
    ("Istanbul", "Турция", 41.02, 28.97),
    ("Ambarli", "Турция", 40.96, 28.69),
    ("Izmir", "Турция", 38.44, 27.14),
    ("Mersin", "Турция", 36.79, 34.63),
    ("Limassol", "Кипр", 34.65, 33.02),
    ("Beirut", "Ливан", 33.90, 35.51),
    ("Haifa", "Израиль", 32.83, 35.00),
    ("Ashdod", "Израиль", 31.82, 34.63),
    ("Port Said", "Египет", 31.26, 32.31),
    ("Alexandria", "Египет", 31.19, 29.87),
    ("Damietta", "Египет", 31.47, 31.76),
    ("Suez", "Египет", 29.93, 32.55),
    ("Tripoli", "Ливия", 32.90, 13.19),
    ("Tunis", "Тунис", 36.82, 10.30),
    ("Algiers", "Алжир", 36.77, 3.06),
    ("Constanta", "Румыния", 44.17, 28.65),
    ("Varna", "Болгария", 43.19, 27.92),
    ("Burgas", "Болгария", 42.49, 27.48),
    ("Odesa", "Украина", 46.49, 30.74),
    ("Chornomorsk", "Украина", 46.30, 30.66),
    ("Pivdennyi", "Украина", 46.62, 31.01),
    ("Novorossiysk", "Россия", 44.72, 37.78),
    ("Poti", "Грузия", 42.15, 41.66),
    ("Batumi", "Грузия", 41.65, 41.63),

    # --- Северная Америка, восточное побережье ---
    ("New York", "США", 40.67, -74.05),
    ("Norfolk", "США", 36.87, -76.33),
    ("Baltimore", "США", 39.26, -76.58),
    ("Philadelphia", "США", 39.90, -75.14),
    ("Charleston", "США", 32.78, -79.93),
    ("Savannah", "США", 32.08, -81.09),
    ("Jacksonville", "США", 30.39, -81.61),
    ("Miami", "США", 25.78, -80.17),
    ("Port Everglades", "США", 26.09, -80.12),
    ("Tampa", "США", 27.94, -82.45),
    ("New Orleans", "США", 29.94, -90.06),
    ("Houston", "США", 29.73, -95.27),
    ("Corpus Christi", "США", 27.81, -97.40),
    ("Mobile", "США", 30.69, -88.04),
    ("Veracruz", "Мексика", 19.20, -96.13),
    ("Altamira", "Мексика", 22.50, -97.87),
    ("Halifax", "Канада", 44.65, -63.57),
    ("Montreal", "Канада", 45.55, -73.53),
    ("Saint John", "Канада", 45.27, -66.06),

    # --- Карибы и Центральная Америка ---
    ("Kingston", "Ямайка", 17.97, -76.79),
    ("Freeport", "Багамы", 26.53, -78.70),
    ("Caucedo", "Доминикана", 18.42, -69.63),
    ("Rio Haina", "Доминикана", 18.42, -70.02),
    ("San Juan", "Пуэрто-Рико", 18.45, -66.10),
    ("Point Lisas", "Тринидад и Тобаго", 10.39, -61.48),
    ("Port of Spain", "Тринидад и Тобаго", 10.65, -61.53),
    ("Willemstad", "Кюрасао", 12.11, -68.93),
    ("Oranjestad", "Аруба", 12.52, -70.04),
    ("Colon", "Панама", 9.36, -79.90),
    ("Balboa", "Панама", 8.95, -79.56),
    ("Cristobal", "Панама", 9.35, -79.90),
    ("Cartagena", "Колумбия", 10.40, -75.53),
    ("Barranquilla", "Колумбия", 11.00, -74.79),
    ("Santa Marta", "Колумбия", 11.25, -74.21),
    ("Puerto Cabello", "Венесуэла", 10.48, -68.01),
    ("La Guaira", "Венесуэла", 10.60, -66.93),
    ("Limon", "Коста-Рика", 9.99, -83.03),
    ("Puerto Cortes", "Гондурас", 15.83, -87.95),
    ("Santo Tomas", "Гватемала", 15.70, -88.62),
    ("Veracruz Norte", "Мексика", 19.22, -96.12),

    # --- Южная Америка ---
    ("Santos", "Бразилия", -23.98, -46.30),
    ("Rio de Janeiro", "Бразилия", -22.89, -43.19),
    ("Paranagua", "Бразилия", -25.50, -48.51),
    ("Itajai", "Бразилия", -26.90, -48.65),
    ("Rio Grande", "Бразилия", -32.04, -52.10),
    ("Salvador", "Бразилия", -12.96, -38.51),
    ("Suape", "Бразилия", -8.39, -34.96),
    ("Fortaleza", "Бразилия", -3.71, -38.48),
    ("Belem", "Бразилия", -1.44, -48.50),
    ("Manaus", "Бразилия", -3.13, -60.02),
    ("Vitoria", "Бразилия", -20.32, -40.34),
    ("Buenos Aires", "Аргентина", -34.58, -58.37),
    ("Rosario", "Аргентина", -32.94, -60.65),
    ("Bahia Blanca", "Аргентина", -38.78, -62.28),
    ("Montevideo", "Уругвай", -34.90, -56.21),
    ("Asuncion", "Парагвай", -25.27, -57.63),
    ("Guayaquil", "Эквадор", -2.27, -79.89),
    ("Callao", "Перу", -12.05, -77.14),
    ("San Antonio", "Чили", -33.59, -71.61),
    ("Valparaiso", "Чили", -33.03, -71.63),
    ("Punta Arenas", "Чили", -53.16, -70.91),

    # --- Ближний Восток и Индийский океан ---
    ("Jeddah", "Саудовская Аравия", 21.48, 39.16),
    ("Dammam", "Саудовская Аравия", 26.51, 50.20),
    ("Jebel Ali", "ОАЭ", 25.01, 55.06),
    ("Khor Fakkan", "ОАЭ", 25.35, 56.36),
    ("Fujairah", "ОАЭ", 25.16, 56.36),
    ("Salalah", "Оман", 16.94, 54.01),
    ("Sohar", "Оман", 24.51, 56.63),
    ("Doha", "Катар", 25.28, 51.53),
    ("Kuwait", "Кувейт", 29.36, 47.94),
    ("Bandar Abbas", "Иран", 27.15, 56.21),
    ("Karachi", "Пакистан", 24.84, 66.98),
    ("Mundra", "Индия", 22.84, 69.72),
    ("Nhava Sheva", "Индия", 18.95, 72.95),
    ("Chennai", "Индия", 13.10, 80.30),
    ("Kolkata", "Индия", 22.55, 88.31),
    ("Cochin", "Индия", 9.97, 76.26),
    ("Colombo", "Шри-Ланка", 6.95, 79.84),
    ("Chittagong", "Бангладеш", 22.31, 91.80),
    ("Djibouti", "Джибути", 11.60, 43.14),
    ("Mombasa", "Кения", -4.06, 39.66),
    ("Dar es Salaam", "Танзания", -6.82, 39.30),
    ("Port Louis", "Маврикий", -20.16, 57.50),

    # --- Азия и Тихий океан ---
    ("Singapore", "Сингапур", 1.26, 103.83),
    ("Port Klang", "Малайзия", 3.00, 101.39),
    ("Tanjung Pelepas", "Малайзия", 1.36, 103.55),
    ("Jakarta", "Индонезия", -6.10, 106.88),
    ("Surabaya", "Индонезия", -7.20, 112.73),
    ("Laem Chabang", "Таиланд", 13.08, 100.88),
    ("Bangkok", "Таиланд", 13.70, 100.57),
    ("Ho Chi Minh", "Вьетнам", 10.76, 106.71),
    ("Haiphong", "Вьетнам", 20.86, 106.69),
    ("Manila", "Филиппины", 14.59, 120.96),
    ("Hong Kong", "Китай", 22.31, 114.13),
    ("Shenzhen", "Китай", 22.51, 113.90),
    ("Guangzhou", "Китай", 23.09, 113.44),
    ("Shanghai", "Китай", 31.23, 121.50),
    ("Ningbo", "Китай", 29.87, 121.55),
    ("Qingdao", "Китай", 36.09, 120.32),
    ("Tianjin", "Китай", 38.98, 117.78),
    ("Dalian", "Китай", 38.93, 121.65),
    ("Xiamen", "Китай", 24.46, 118.07),
    ("Busan", "Южная Корея", 35.10, 129.04),
    ("Incheon", "Южная Корея", 37.45, 126.60),
    ("Tokyo", "Япония", 35.62, 139.78),
    ("Yokohama", "Япония", 35.45, 139.65),
    ("Nagoya", "Япония", 35.05, 136.85),
    ("Kobe", "Япония", 34.68, 135.20),
    ("Osaka", "Япония", 34.65, 135.43),
    ("Vladivostok", "Россия", 43.11, 131.89),
    ("Vostochny", "Россия", 42.74, 133.07),
    ("Kaohsiung", "Тайвань", 22.61, 120.28),
    ("Taipei", "Тайвань", 25.15, 121.74),

    # --- Северная Америка, западное побережье, и Океания ---
    ("Los Angeles", "США", 33.73, -118.26),
    ("Long Beach", "США", 33.75, -118.20),
    ("Oakland", "США", 37.80, -122.33),
    ("Seattle", "США", 47.58, -122.35),
    ("Tacoma", "США", 47.27, -122.42),
    ("Vancouver", "Канада", 49.29, -123.11),
    ("Prince Rupert", "Канада", 54.32, -130.32),
    ("Manzanillo", "Мексика", 19.06, -104.32),
    ("Lazaro Cardenas", "Мексика", 17.94, -102.18),
    ("Anchorage", "США", 61.24, -149.89),
    ("Honolulu", "США", 21.31, -157.87),
    ("Sydney", "Австралия", -33.85, 151.21),
    ("Melbourne", "Австралия", -37.83, 144.92),
    ("Brisbane", "Австралия", -27.38, 153.17),
    ("Fremantle", "Австралия", -32.05, 115.74),
    ("Port Hedland", "Австралия", -20.31, 118.57),
    ("Auckland", "Новая Зеландия", -36.84, 174.77),
    ("Tauranga", "Новая Зеландия", -37.64, 176.18),
]]

_PORT_INDEX = {p.name.lower(): p for p in PORTS}

# "43.3N 5.4E", "43.3,5.4", "43-20N 005-24E"
_MANUAL_COORD = re.compile(
    r"^\s*(-?\d{1,3}(?:[.,]\d+)?)\s*([NS])?\s*[, ]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*([EW])?\s*$",
    re.IGNORECASE,
)


def find_ports(query: str, limit: int = 12) -> list[Port]:
    """Поиск порта по части названия или страны."""
    q = query.strip().lower()
    if not q:
        return []
    exact = [p for p in PORTS if p.name.lower() == q]
    starts = [p for p in PORTS if p.name.lower().startswith(q) and p not in exact]
    contains = [p for p in PORTS if q in p.label.lower() and p not in exact and p not in starts]
    return (exact + starts + contains)[:limit]


def resolve_point(text: str) -> Port | None:
    """Порт по названию либо координаты, введённые вручную."""
    if not text:
        return None
    port = _PORT_INDEX.get(text.strip().lower())
    if port:
        return port
    found = find_ports(text, limit=1)
    if found:
        return found[0]

    m = _MANUAL_COORD.match(text)
    if m:
        lat = float(m.group(1).replace(",", "."))
        lon = float(m.group(3).replace(",", "."))
        if (m.group(2) or "").upper() == "S":
            lat = -abs(lat)
        if (m.group(4) or "").upper() == "W":
            lon = -abs(lon)
        if abs(lat) <= 90 and abs(lon) <= 180:
            return Port(f"{lat:.2f}, {lon:.2f}", "координаты", lat, lon)
    return None


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_NM * math.asin(min(1.0, math.sqrt(a)))


def planned_route(a: Port, b: Port) -> dict:
    """Маршрут через проливы и каналы вместо прямой через сушу."""
    from .routing import NODE_TITLES, densify, plan_route

    r = plan_route((a.lat, a.lon), (b.lat, b.lon))
    pts = densify(r["points"])
    legs = [{"key": w, "title": NODE_TITLES.get(w), "lat": None, "lon": None}
            for w in r["waypoints"] if w in NODE_TITLES]
    from .routing import NODES
    for leg in legs:
        leg["lat"], leg["lon"] = NODES[leg["key"]]
    return {
        "points": pts,
        "distance_nm": r["distance_nm"],
        "legs": legs,
        "direct": r.get("direct", False),
    }


def great_circle_points(a: Port, b: Port, step_nm: float = 60.0) -> list[tuple[float, float]]:
    """Точки вдоль ортодромии между двумя портами."""
    total = haversine_nm(a.lat, a.lon, b.lat, b.lon)
    steps = max(2, min(400, int(total / step_nm) + 1))

    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
    d = total / EARTH_RADIUS_NM
    if d == 0:
        return [(a.lat, a.lon)]

    points = []
    for i in range(steps + 1):
        f = i / steps
        A = math.sin((1 - f) * d) / math.sin(d)
        B = math.sin(f * d) / math.sin(d)
        x = A * math.cos(lat1) * math.cos(lon1) + B * math.cos(lat2) * math.cos(lon2)
        y = A * math.cos(lat1) * math.sin(lon1) + B * math.cos(lat2) * math.sin(lon2)
        z = A * math.sin(lat1) + B * math.sin(lat2)
        points.append((
            math.degrees(math.atan2(z, math.sqrt(x * x + y * y))),
            math.degrees(math.atan2(y, x)),
        ))
    return points


def _bearing_rad(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Начальный ортодромический пеленг из a в b, в радианах."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    return math.atan2(
        math.sin(lon2 - lon1) * math.cos(lat2),
        math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1),
    )


def _distance_to_segment_nm(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """Расстояние от точки до ортодромического отрезка a–b в морских милях."""
    segment = haversine_nm(*a, *b) / EARTH_RADIUS_NM
    if segment == 0:
        return haversine_nm(*point, *a)

    d13 = haversine_nm(*a, *point) / EARTH_RADIUS_NM
    bearing_ab = _bearing_rad(a, b)
    bearing_ap = _bearing_rad(a, point)
    delta = bearing_ap - bearing_ab
    cross_track = math.asin(max(-1.0, min(1.0, math.sin(d13) * math.sin(delta))))
    along_track = math.atan2(math.sin(d13) * math.cos(delta), math.cos(d13))
    if along_track <= 0:
        return haversine_nm(*point, *a)
    if along_track >= segment:
        return haversine_nm(*point, *b)
    return abs(cross_track) * EARTH_RADIUS_NM


def distance_to_route(route: list[tuple[float, float]], lat: float, lon: float) -> float:
    """Минимальное расстояние от точки до линии маршрута, в морских милях."""
    point = (lat, lon)
    if len(route) == 1:
        return haversine_nm(*point, *route[0])
    return min(_distance_to_segment_nm(point, a, b) for a, b in zip(route, route[1:]))


def warnings_on_route(route: list[tuple[float, float]], warnings: list, corridor_nm: float = 150.0) -> list[dict]:
    """Из списка предупреждений оставляет те, что попадают в коридор вдоль маршрута.

    warnings -- строки из БД (нужны поля id, area_code, msg_number, region, raw_text).
    Возвращает список словарей, отсортированный по расстоянию от маршрута."""
    from .geo import extract_coordinates, extract_shapes

    result = []
    for w in warnings:
        coords = extract_coordinates(w["raw_text"])
        if not coords:
            continue
        best = min(distance_to_route(route, lat, lon) for lat, lon in coords)
        if best <= corridor_nm:
            result.append({
                "id": w["id"],
                "area_code": w["area_code"],
                "msg_number": w["msg_number"],
                "region": w["region"],
                "raw_text": w["raw_text"],
                "coords": coords[:40],
                "shapes": extract_shapes(w["raw_text"]),
                "distance_nm": round(best, 1),
            })
    result.sort(key=lambda x: x["distance_nm"])
    return result
