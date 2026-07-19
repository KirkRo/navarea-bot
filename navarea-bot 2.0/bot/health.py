"""
Совсем маленький HTTP-сервер на стандартной библиотеке, без новых
зависимостей. Единственная задача -- отвечать "OK" на любой GET-запрос,
чтобы:

  1) Render видел, что процесс слушает порт (иначе бесплатный Web Service
     считает деплой неудачным),
  2) внешний пинг-сервис (UptimeRobot и подобные) мог раз в несколько
     минут "будить" бота, не давая свободному тарифу Render усыпить его.

На варианте хостинга Oracle Cloud этот сервер не нужен и не мешает --
он всё равно поднимается, просто его никто не дёргает снаружи.
"""
from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"navarea-bot: OK")

    def log_message(self, format: str, *args) -> None:  # noqa: A002 -- глушим стандартный access-лог
        pass


def start_health_server(port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health-check сервер поднят на порту %s", port)
