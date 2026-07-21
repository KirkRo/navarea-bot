"""
Маленький HTTP-сервер на стандартной библиотеке, без новых зависимостей.
Делает две вещи:

  1) отвечает "OK" на любой левый запрос -- нужно, чтобы Render видел, что
     процесс слушает порт, и чтобы внешний пинг-сервис мог будить бота
     на бесплатном тарифе (см. README, вариант хостинга Б);

  2) отдаёт /map?pts=...&title=...&info=... -- страницу с картой
     (Leaflet + OpenStreetMap, без ключей API) с отмеченными координатами
     из конкретного предупреждения. Одна точка -- маркер, две и больше --
     контур области с точками, при клике всплывает подсказка с текстом.

На варианте хостинга Oracle этот сервер тоже поднимается, просто ссылки
на карту будут работать только если в .env заполнен PUBLIC_URL (см. FAQ
в README) -- иначе бот использует запасной вариант со ссылкой на Google
Maps на середину области, без своей страницы.
"""
from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from string import Template
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

_MAP_TEMPLATE = Template("""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>html,body,#map{height:100%;margin:0;font-family:sans-serif}</style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var points = $points_json;
var popupHtml = $popup_json;
var map = L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

var layer;
if (points.length <= 1) {
    var p = points[0];
    layer = L.marker(p).addTo(map);
    map.setView(p, 9);
} else {
    layer = L.polygon(points, {color: '#e8a33e', weight: 3, fillOpacity: 0.15}).addTo(map);
    points.forEach(function(p) { L.circleMarker(p, {radius: 5, color: '#e8a33e'}).addTo(map); });
    map.fitBounds(layer.getBounds(), {padding: [30, 30]});
}
layer.bindPopup(popupHtml).openPopup();
</script>
</body>
</html>
""")


def _render_map(query: dict) -> bytes:
    raw_pts = query.get("pts", [""])[0]
    title = query.get("title", ["NAVAREA"])[0]
    info = query.get("info", [""])[0]

    points = []
    for pair in raw_pts.split(";"):
        if not pair:
            continue
        try:
            lat_s, lon_s = pair.split(",")
            points.append([float(lat_s), float(lon_s)])
        except ValueError:
            continue

    if not points:
        return b"<html><body>Coordinates not found for this warning.</body></html>"

    popup = f"<b>{title}</b>"
    if info:
        popup += f"<br>{info}"

    html = _MAP_TEMPLATE.substitute(
        title=title,
        points_json=json.dumps(points),
        popup_json=json.dumps(popup),
    )
    return html.encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/map":
            query = parse_qs(parsed.query)
            body = _render_map(query)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"navarea-bot: OK")

    def log_message(self, format: str, *args) -> None:  # noqa: A002 -- глушим стандартный access-лог
        pass


def start_web_server(port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Веб-сервер (health-check + карта) поднят на порту %s", port)


def build_map_url(public_url: str, coords: list[tuple[float, float]], title: str, info: str = "") -> str:
    from urllib.parse import quote

    pts = ";".join(f"{lat},{lon}" for lat, lon in coords)
    return f"{public_url.rstrip('/')}/map?pts={quote(pts)}&title={quote(title)}&info={quote(info[:200])}"
