"""
Выгрузка предупреждений в форматы, которые понимают чужие программы.

Открытые форматы делаем сами: GeoJSON и KML открываются почти везде,
WKT и CSV идут в базы и таблицы, GPX читают навигаторы и планировщики,
Shapefile и GeoPackage нужны GIS. Всё, кроме Shapefile, собирается на
стандартной библиотеке; для Shapefile берём pyshp, потому что там три
двоичных файла со своими индексами и писать их вручную ради одной кнопки
неразумно.

Про форматы ECDIS (JRC, TRANSAS, FURUNO) отдельно. Открытых описаний у
них нет, и собрать файл «по мотивам» значит выдать штурману данные,
которые ECDIS либо не примет, либо покажет не там, где они есть на самом
деле. На мостике это опасно, поэтому такие форматы здесь не выдуманы:
чтобы их добавить, нужен образец настоящего файла с конкретного
оборудования (см. функцию ecdis_note ниже).
"""
from __future__ import annotations

import io
import json
import logging
import zipfile

logger = logging.getLogger(__name__)

# Что умеем отдавать. Ключ уходит в адрес запроса, mime и расширение --
# в заголовки и в имя файла.
FORMATS = {
    "geojson":   ("GeoJSON",   "application/geo+json",                 "geojson", "text"),
    "json":      ("JSON",      "application/json",                     "json",    "text"),
    "kml":       ("KML",       "application/vnd.google-earth.kml+xml",  "kml",     "text"),
    "gpx":       ("GPX",       "application/gpx+xml",                  "gpx",     "text"),
    "wkt":       ("WKT",       "text/csv",                             "csv",     "text"),
    "csv":       ("CSV",       "text/csv",                             "csv",     "text"),
    "txt":       ("TXT",       "text/plain",                           "txt",     "text"),
    "shapefile": ("Shapefile", "application/zip",                      "zip",     "binary"),
    "gpkg":      ("GeoPackage", "application/geopackage+sqlite3",      "gpkg",    "binary"),
}

ECDIS_FORMATS = ("JRC", "TRANSAS", "FURUNO")


def ecdis_note(lang: str = "ru") -> str:
    if lang != "ru":
        return ("Files for JRC, TRANSAS and FURUNO are not generated: these formats have no "
                "open specification. Send a sample file exported from the actual ECDIS and "
                "the format will be added.")
    return ("Файлы для JRC, TRANSAS и FURUNO не собираются: у этих форматов нет открытого "
            "описания. Пришлите образец файла, выгруженный с самой ECDIS, и формат добавим.")


def _esc_xml(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _polygons(feature: dict) -> list[list]:
    """Замкнутые контуры предупреждения. Меньше трёх точек это не площадь."""
    out = []
    for shape in feature.get("shapes") or []:
        pts = shape.get("points") or []
        if len(pts) >= 3:
            out.append(list(pts))
    return out


def _points(feature: dict) -> list[tuple]:
    return [tuple(p) for p in (feature.get("points") or [])[:20]]


# ---------------------------------------------------------------------- #
# Текстовые форматы
# ---------------------------------------------------------------------- #

def as_geojson(features: list[dict]) -> str:
    """Область отдаём полигоном, одиночную точку точкой: программа, которая
    получит полигон из одной вершины, нарисует пустое место."""
    out = []
    for f in features:
        geoms = []
        for ring in _polygons(f):
            closed = [[p[1], p[0]] for p in ring]
            closed.append(closed[0])          # GeoJSON требует замкнутое кольцо
            geoms.append({"type": "Polygon", "coordinates": [closed]})
        if not geoms:
            for lat, lon in _points(f):
                geoms.append({"type": "Point", "coordinates": [lon, lat]})
        for geom in geoms:
            out.append({"type": "Feature", "geometry": geom,
                        "properties": {"area": f["area"], "number": f["number"],
                                       "region": f["region"], "issued": f["issued"],
                                       "text": f["text"][:4000]}})
    return json.dumps({"type": "FeatureCollection", "features": out},
                      ensure_ascii=False, indent=1)


def as_json(features: list[dict]) -> str:
    """Плоский список без геометрии GeoJSON: удобно, когда файл читает
    скрипт, а не карта."""
    out = []
    for f in features:
        out.append({"area": f["area"], "number": f["number"], "region": f["region"],
                    "issued": f["issued"], "text": f["text"],
                    "points": [[p[0], p[1]] for p in _points(f)],
                    "areas": [[[p[0], p[1]] for p in ring] for ring in _polygons(f)]})
    return json.dumps(out, ensure_ascii=False, indent=1)


def as_kml(features: list[dict]) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
             "<name>NAVAREA warnings</name>"]
    for f in features:
        title = _esc_xml(f"{f['area']} {f['number']}".strip())
        desc = _esc_xml(f["text"][:3000])
        rings = _polygons(f)
        for ring in rings:
            closed = ring + [ring[0]]
            coords = " ".join(f"{p[1]},{p[0]},0" for p in closed)
            parts.append(f"<Placemark><name>{title}</name><description>{desc}</description>"
                         f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coords}"
                         f"</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>")
        if not rings:
            for lat, lon in _points(f):
                parts.append(f"<Placemark><name>{title}</name><description>{desc}</description>"
                             f"<Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>")
    parts.append("</Document></kml>")
    return "\n".join(parts)


def as_gpx(features: list[dict]) -> str:
    """Точки идут путевыми точками, области -- треком по контуру.

    Маршрутом (rte) контур делать нельзя: навигатор попробует вести по
    нему судно, а это граница опасного района, а не линия пути."""
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<gpx version="1.1" creator="WatchKeeper" '
             'xmlns="http://www.topografix.com/GPX/1/1">']
    for f in features:
        title = _esc_xml(f"{f['area']} {f['number']}".strip())
        desc = _esc_xml(" ".join(f["text"].split())[:1000])
        for lat, lon in _points(f):
            parts.append(f'<wpt lat="{lat}" lon="{lon}"><name>{title}</name>'
                         f"<desc>{desc}</desc><sym>Danger Area</sym></wpt>")
        for ring in _polygons(f):
            pts = ring + [ring[0]]
            seg = "".join(f'<trkpt lat="{p[0]}" lon="{p[1]}"></trkpt>' for p in pts)
            parts.append(f"<trk><name>{title}</name><desc>{desc}</desc><trkseg>{seg}</trkseg></trk>")
    parts.append("</gpx>")
    return "\n".join(parts)


def as_wkt(features: list[dict]) -> str:
    """WKT в колонке таблицы: так его принимают PostGIS, QGIS и Excel."""
    rows = [["area", "number", "region", "issued", "wkt", "text"]]
    for f in features:
        for ring in _polygons(f):
            closed = ring + [ring[0]]
            body = ", ".join(f"{p[1]} {p[0]}" for p in closed)
            rows.append([f["area"], f["number"], f["region"], f["issued"],
                         f"POLYGON(({body}))", " ".join(f["text"].split())[:2000]])
        if not _polygons(f):
            for lat, lon in _points(f):
                rows.append([f["area"], f["number"], f["region"], f["issued"],
                             f"POINT({lon} {lat})", " ".join(f["text"].split())[:2000]])
    return _csv_rows(rows)


def as_csv(features: list[dict]) -> str:
    rows = [["area", "number", "region", "issued", "lat", "lon", "text"]]
    for f in features:
        pts = _points(f)
        lat, lon = pts[0] if pts else ("", "")
        rows.append([f["area"], f["number"], f["region"], f["issued"], lat, lon,
                     " ".join(f["text"].split())[:2000]])
    return _csv_rows(rows)


def _csv_rows(rows: list[list]) -> str:
    """Разделитель точка с запятой: Excel в русской локали принимает запятую
    за разделитель разрядов и складывает строку в одну ячейку."""
    import csv

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def as_txt(features: list[dict]) -> str:
    """Просто читаемый текст: распечатать и положить на прокладочный стол."""
    parts = []
    for f in features:
        head = f"{f['area']} {f['number']}".strip()
        if f.get("region"):
            head += f" · {f['region']}"
        parts.append(head)
        parts.append("-" * len(head))
        parts.append(f["text"].strip())
        pts = _points(f)
        if pts:
            coords = "; ".join(f"{abs(p[0]):.3f}{'N' if p[0] >= 0 else 'S'} "
                               f"{abs(p[1]):.3f}{'E' if p[1] >= 0 else 'W'}" for p in pts)
            parts.append(f"Координаты: {coords}")
        parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------- #
# Двоичные форматы
# ---------------------------------------------------------------------- #

def as_shapefile(features: list[dict]) -> bytes:
    """Shapefile это набор файлов, поэтому отдаём zip.

    Точки и площади лежат в разных слоях: формат не разрешает держать
    разные типы геометрии в одном файле."""
    import shapefile  # pyshp

    bufs = {}

    def build(kind: str, shape_type: int, writer_body) -> None:
        shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
        w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shape_type)
        w.field("area", "C", 12)
        w.field("number", "C", 16)
        w.field("region", "C", 64)
        w.field("issued", "C", 32)
        w.field("text", "C", 254)
        count = writer_body(w)
        w.close()
        if count:
            bufs[f"warnings_{kind}.shp"] = shp.getvalue()
            bufs[f"warnings_{kind}.shx"] = shx.getvalue()
            bufs[f"warnings_{kind}.dbf"] = dbf.getvalue()

    def attrs(f: dict) -> list:
        return [f["area"][:12], str(f["number"])[:16], (f["region"] or "")[:64],
                str(f["issued"])[:32], " ".join(f["text"].split())[:254]]

    def points_body(w) -> int:
        n = 0
        for f in features:
            if _polygons(f):
                continue
            for lat, lon in _points(f):
                w.point(lon, lat)
                w.record(*attrs(f))
                n += 1
        return n

    def polys_body(w) -> int:
        n = 0
        for f in features:
            for ring in _polygons(f):
                # В shapefile внешнее кольцо идёт по часовой стрелке и
                # замыкается на первую точку.
                closed = [[p[1], p[0]] for p in ring]
                closed.append(closed[0])
                w.poly([closed])
                w.record(*attrs(f))
                n += 1
        return n

    build("points", shapefile.POINT, points_body)
    build("areas", shapefile.POLYGON, polys_body)

    # Проекция WGS84: без .prj GIS не знает системы координат и кладёт
    # предупреждения не туда.
    wgs84 = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
             'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, blob in bufs.items():
            zf.writestr(name, blob)
            if name.endswith(".shp"):
                zf.writestr(name[:-4] + ".prj", wgs84)
        zf.writestr("readme.txt",
                    "NAVAREA warnings exported from WatchKeeper.\n"
                    "warnings_points -- point warnings, warnings_areas -- area warnings.\n"
                    "Coordinate system WGS84 (EPSG:4326).\n")
    return out.getvalue()


def as_geopackage(features: list[dict]) -> bytes:
    """GeoPackage это база SQLite с обязательными служебными таблицами.

    Пишем во временный файл, а не в память: sqlite3 из стандартной
    библиотеки умеет открывать только файл, а тянуть ради этого стороннюю
    сборку в проект не хочется."""
    import os
    import sqlite3
    import struct
    import tempfile

    path = os.path.join(tempfile.mkdtemp(), "warnings.gpkg")
    con = sqlite3.connect(path)
    cur = con.cursor()

    # application_id 'GPKG' и user_version -- по ним программы опознают файл
    cur.execute("PRAGMA application_id = 1196444487")
    cur.execute("PRAGMA user_version = 10301")
    cur.executescript("""
        CREATE TABLE gpkg_spatial_ref_sys (
            srs_name TEXT NOT NULL, srs_id INTEGER PRIMARY KEY,
            organization TEXT NOT NULL, organization_coordsys_id INTEGER NOT NULL,
            definition TEXT NOT NULL, description TEXT);
        CREATE TABLE gpkg_contents (
            table_name TEXT PRIMARY KEY, data_type TEXT NOT NULL,
            identifier TEXT UNIQUE, description TEXT DEFAULT '',
            last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE, srs_id INTEGER);
        CREATE TABLE gpkg_geometry_columns (
            table_name TEXT NOT NULL, column_name TEXT NOT NULL,
            geometry_type_name TEXT NOT NULL, srs_id INTEGER NOT NULL,
            z TINYINT NOT NULL, m TINYINT NOT NULL,
            CONSTRAINT pk_geom_cols PRIMARY KEY (table_name, column_name));
        CREATE TABLE warnings (
            fid INTEGER PRIMARY KEY AUTOINCREMENT, geom BLOB,
            area TEXT, number TEXT, region TEXT, issued TEXT, text TEXT);
    """)
    wgs84 = ('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
             'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]')
    cur.executemany(
        "INSERT INTO gpkg_spatial_ref_sys VALUES (?,?,?,?,?,?)",
        [("WGS 84", 4326, "EPSG", 4326, wgs84, None),
         ("Undefined cartesian", -1, "NONE", -1, "undefined", None),
         ("Undefined geographic", 0, "NONE", 0, "undefined", None)])
    cur.execute("INSERT INTO gpkg_geometry_columns VALUES ('warnings','geom','GEOMETRY',4326,0,0)")

    def wkb_point(lon: float, lat: float) -> bytes:
        return struct.pack("<BIdd", 1, 1, lon, lat)

    def wkb_polygon(ring: list) -> bytes:
        closed = [(p[1], p[0]) for p in ring]
        closed.append(closed[0])
        body = struct.pack("<BII", 1, 3, 1) + struct.pack("<I", len(closed))
        for lon, lat in closed:
            body += struct.pack("<dd", lon, lat)
        return body

    def gpkg_blob(wkb: bytes) -> bytes:
        # Заголовок GeoPackage: магия GP, версия, флаги, идентификатор srs
        return b"GP" + struct.pack("<BB", 0, 1) + struct.pack("<i", 4326) + wkb

    xs, ys = [], []
    rows = []
    for f in features:
        attrs = (f["area"], str(f["number"]), f["region"] or "", str(f["issued"]),
                 " ".join(f["text"].split())[:4000])
        rings = _polygons(f)
        for ring in rings:
            rows.append((gpkg_blob(wkb_polygon(ring)),) + attrs)
            xs += [p[1] for p in ring]
            ys += [p[0] for p in ring]
        if not rings:
            for lat, lon in _points(f):
                rows.append((gpkg_blob(wkb_point(lon, lat)),) + attrs)
                xs.append(lon)
                ys.append(lat)
    cur.executemany("INSERT INTO warnings (geom, area, number, region, issued, text) "
                    "VALUES (?,?,?,?,?,?)", rows)
    cur.execute("INSERT INTO gpkg_contents (table_name, data_type, identifier, description,"
                " min_x, min_y, max_x, max_y, srs_id) VALUES (?,?,?,?,?,?,?,?,?)",
                ("warnings", "features", "warnings", "NAVAREA warnings",
                 min(xs) if xs else -180, min(ys) if ys else -90,
                 max(xs) if xs else 180, max(ys) if ys else 90, 4326))
    con.commit()
    con.close()

    with open(path, "rb") as fh:
        blob = fh.read()
    try:
        os.remove(path)
    except OSError:
        pass
    return blob


BUILDERS = {
    "geojson": as_geojson, "json": as_json, "kml": as_kml, "gpx": as_gpx,
    "wkt": as_wkt, "csv": as_csv, "txt": as_txt,
    "shapefile": as_shapefile, "gpkg": as_geopackage,
}


def build(fmt: str, features: list[dict], area: str = "") -> tuple[bytes, str, str]:
    """Готовый файл: содержимое, mime и имя. Неизвестный формат отдаём
    как GeoJSON, а не ошибкой: кнопка в приложении всё равно должна
    что-то отдать.

    Район попадает в имя файла. Выгрузка идёт по одному файлу на район,
    и без кода в имени на диске получалась бы стопка одинаковых
    warnings.geojson, которые различить можно только открыв каждый."""
    fmt = (fmt or "geojson").lower()
    if fmt not in BUILDERS:
        fmt = "geojson"
    title, mime, ext, kind = FORMATS[fmt]
    body = BUILDERS[fmt](features)
    if kind == "text":
        body = body.encode("utf-8")
    # В имени файла оставляем только буквы, цифры и дефис: коды районов
    # вроде I-COASTAL безопасны, но подставить сюда могут что угодно.
    tag = "".join(ch for ch in str(area) if ch.isalnum() or ch == "-")
    return body, mime, (f"warnings_{tag}.{ext}" if tag else f"warnings.{ext}")


def group_by_area(features: list[dict]) -> dict:
    """Раскладываем предупреждения по районам, сохраняя порядок появления."""
    out: dict[str, list[dict]] = {}
    for f in features:
        out.setdefault(f.get("area") or "", []).append(f)
    return out
