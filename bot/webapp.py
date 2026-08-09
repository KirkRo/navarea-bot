"""
HTTP-сервер бота на стандартной библиотеке (без Flask/FastAPI, чтобы не
тянуть зависимости). Отдаёт:

  /                  health-check ("OK") -- по нему Render понимает, что
                     процесс жив, и внешний пинг-сервис будит бота
  /app               Telegram Mini App (одностраничное приложение)
  /map               отдельная страница карты для ссылок из сообщений бота
  /api/stats         сводка по всем районам (кэш STATS_TTL секунд)
  /api/warnings      список/поиск предупреждений
  /api/favorites     избранные районы (GET) и переключение
  /api/ports         поиск порта по названию
  /api/voyage        предупреждения вдоль маршрута между двумя портами
  /api/invoice       ссылка на оплату подписки звёздами (кнопка в Mini App)

Все /api/* отдают JSON. Данные, привязанные к пользователю (избранное),
доступны только после проверки подписи Telegram initData -- иначе кто
угодно мог бы читать и менять чужое избранное, зная user_id.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from string import Template
from urllib.parse import parse_qs, quote, unquote, urlparse

logger = logging.getLogger(__name__)

STATS_TTL = 30.0  # секунд, кэш статистики

_state: dict = {"db": None, "bot_token": "", "started_at": time.time()}
_stats_cache: dict = {"data": None, "at": 0.0}


# ---------------------------------------------------------------------- #
# Проверка подписи Telegram Mini App
# ---------------------------------------------------------------------- #

def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    """Проверяет подпись initData из Telegram.WebApp и возвращает данные
    пользователя. None -- если подпись неверная или её нет.

    Алгоритм из документации Telegram: secret = HMAC_SHA256("WebAppData",
    bot_token), затем HMAC_SHA256(secret, отсортированные пары ключ=значение)
    должен совпасть с полем hash."""
    if not init_data or not bot_token:
        return None
    try:
        received_hash = None
        data_pairs = []
        for pair in init_data.split("&"):
            if not pair:
                continue
            key, _, value = pair.partition("=")
            if key == "hash":
                received_hash = value
            else:
                data_pairs.append((key, unquote(value)))
        if not received_hash:
            return None

        check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_pairs))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, received_hash):
            return None

        for k, v in data_pairs:
            if k == "user":
                return json.loads(v)
        return None
    except Exception:
        logger.exception("Не удалось проверить initData")
        return None


def _user_id_from_query(query: dict) -> int | None:
    init_data = (query.get("initData") or [""])[0]
    user = validate_init_data(init_data, _state["bot_token"])
    if not user:
        return None
    uid = user.get("id")
    return int(uid) if uid else None


# ---------------------------------------------------------------------- #
# Данные для API
# ---------------------------------------------------------------------- #

def _row_to_dict(row, with_coords: bool = True) -> dict:
    from .services.geo import extract_coordinates, extract_shapes

    data = {
        "id": row["id"],
        "area_code": row["area_code"],
        "msg_number": row["msg_number"],
        "region": row["region"],
        "text": row["raw_text"],
        "issued_at": row["issued_at"],
        "first_seen_at": row["first_seen_at"],
        "is_cancelled": bool(row["is_cancelled"]),
    }
    if with_coords:
        data["coords"] = extract_coordinates(row["raw_text"])[:40]
        # Готовая геометрия от источника (Sealagom) точнее нашего разбора текста --
        # берём её, если есть, и только иначе разбираем текст сами.
        stored = None
        try:
            raw_shapes = row["shapes_json"]
            if raw_shapes:
                stored = json.loads(raw_shapes)
        except (KeyError, TypeError, ValueError):
            stored = None
        data["shapes"] = stored or extract_shapes(row["raw_text"])
        data["geo_source"] = "source" if stored else "parsed"
    return data


def _build_id() -> str:
    from .config import BUILD
    return BUILD


def _build_stats() -> dict:
    from .services.sources.registry import AREAS, POLLABLE_AREAS, area_display_name

    db = _state["db"]
    per_area = db.area_stats()

    areas = []
    for code in POLLABLE_AREAS:
        info = AREAS.get(code)
        s = per_area.get(code, {})
        areas.append({
            "code": code,
            "name": area_display_name(code) if info else code,
            "is_coastal": code.startswith("COASTAL:"),
            "coordinator": info.coordinator if info else "",
            "in_force": s.get("in_force", 0),
            "archived": s.get("archived", 0),
            "added_today": s.get("added_today", 0),
            "added_week": s.get("added_week", 0),
            "last_update": s.get("last_update"),
        })

    totals = {
        "in_force": sum(a["in_force"] for a in areas),
        "archived": sum(a["archived"] for a in areas),
        "added_today": sum(a["added_today"] for a in areas),
        "added_week": sum(a["added_week"] for a in areas),
        "areas_count": len(areas),
    }
    last_update = max((a["last_update"] for a in areas if a["last_update"]), default=None)

    return {
        "totals": totals,
        "areas": areas,
        "last_update": last_update,
        "build": _build_id(),
        "server": {
            "status": "ok",
            "uptime_seconds": int(time.time() - _state["started_at"]),
            "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }


def _cached_stats() -> dict:
    now = time.time()
    if _stats_cache["data"] is not None and (now - _stats_cache["at"]) < STATS_TTL:
        return _stats_cache["data"]
    data = _build_stats()
    _stats_cache["data"], _stats_cache["at"] = data, now
    return data


def invalidate_stats_cache() -> None:
    """Вызывается после сохранения новых предупреждений, чтобы Mini App
    сразу увидел свежие цифры, не дожидаясь истечения TTL."""
    _stats_cache["data"] = None


# ---------------------------------------------------------------------- #
# Маршруты API
# ---------------------------------------------------------------------- #

def _api_stats(query: dict) -> dict:
    return _cached_stats()


def _api_warnings(query: dict) -> dict:
    db = _state["db"]
    q = (query.get("q") or [""])[0].strip()
    areas = [a for a in (query.get("area") or []) if a]
    include_archived = (query.get("archived") or ["0"])[0] == "1"
    limit = min(int((query.get("limit") or ["500"])[0]), 4000)

    rows = db.search_warnings(query=q, areas=areas or None,
                              include_archived=include_archived, limit=limit)
    return {"count": len(rows), "results": [_row_to_dict(r) for r in rows]}


def _api_favorites(query: dict) -> dict:
    db = _state["db"]
    user_id = _user_id_from_query(query)
    if user_id is None:
        return {"error": "unauthorized", "favorites": []}

    toggle = (query.get("toggle") or [""])[0].strip()
    if toggle:
        db.toggle_favorite(user_id, toggle)
    return {"favorites": db.get_favorites(user_id)}


def _api_ports(query: dict) -> dict:
    from .services.voyage import find_ports

    q = (query.get("q") or [""])[0]
    return {"results": [
        {"name": p.name, "country": p.country, "lat": p.lat, "lon": p.lon, "label": p.label}
        for p in find_ports(q)
    ]}


def _api_voyage(query: dict) -> dict:
    from .services.voyage import (great_circle_points, haversine_nm,
                                  resolve_point, warnings_on_route)

    db = _state["db"]
    _uid, denied = _require("voyage", query, personal=False)
    if denied:
        return denied
    src = (query.get("from") or [""])[0]
    dst = (query.get("to") or [""])[0]
    corridor = float((query.get("corridor") or ["150"])[0])

    a, b = resolve_point(src), resolve_point(dst)
    if not a or not b:
        missing = "отправления" if not a else "прибытия"
        return {"error": f"Не удалось определить порт {missing}. Попробуй другое название или введи координаты."}

    from .services.voyage import planned_route
    plan = planned_route(a, b)
    route = plan["points"]
    found = warnings_on_route(route, db.all_active_warnings(), corridor_nm=corridor)

    return {
        "from": {"label": a.label, "lat": a.lat, "lon": a.lon},
        "to": {"label": b.label, "lat": b.lat, "lon": b.lon},
        "legs": plan["legs"],
        "direct_nm": round(haversine_nm(a.lat, a.lon, b.lat, b.lon)),
        "distance_nm": round(plan["distance_nm"]),
        "corridor_nm": corridor,
        "route": [[round(la, 3), round(lo, 3)] for la, lo in route],
        "count": len(found),
        "results": found,
    }



def _require(feature: str, query: dict, personal: bool = True):
    """Возвращает user_id или словарь с отказом.

    personal=False -- раздел не хранит ничего личного (например, расчёт
    маршрута), поэтому при выключенных тарифах подпись не обязательна:
    иначе страница просто не открывалась вне Telegram."""
    from .config import config
    from .services.access import can

    db = _state["db"]
    user_id = _user_id_from_query(query)

    if user_id is None:
        if not personal and not config.paywall_enabled:
            return 0, None
        return None, {"error": "unauthorized"}

    if not can(db, user_id, feature):
        return None, {"error": "premium_required", "feature": feature}
    return user_id, None


def _api_access(query: dict) -> dict:
    """Что доступно этому пользователю -- для интерфейса приложения."""
    from .config import config
    from .services.access import PAID_FEATURES, TRIAL_DAYS, access_state

    db = _state["db"]
    user_id = _user_id_from_query(query)
    if not config.paywall_enabled:
        return {"tier": "open", "premium": True, "paywall": False,
                "title": "Открытый доступ", "paid_features": PAID_FEATURES,
                "trial_days": TRIAL_DAYS, "price_stars": config.stars_price_monthly}

    if user_id is None:
        return {"tier": "free", "premium": False, "paywall": True,
                "paid_features": PAID_FEATURES,
                "trial_days": TRIAL_DAYS, "price_stars": config.stars_price_monthly}

    st = access_state(db, user_id)
    st["paywall"] = True
    st["paid_features"] = PAID_FEATURES
    st["trial_days"] = TRIAL_DAYS
    st["price_stars"] = config.stars_price_monthly
    return st


def _api_vessel(query: dict) -> dict:
    """Карточка судна: список, сохранение, выбор активного, документы."""
    import time as _t
    from .services.ship_providers import provider_info
    from .services.vessel import (FIELD_KEYS, normalize, preset_titles,
                                  preset_values, suggest_from_history, vessel_payload)

    db = _state["db"]
    user_id, denied = _require("vessel", query)
    if denied:
        return denied

    vessels, active_id = db.get_vessels(user_id)
    docs = db.get_vessel_docs(user_id)
    action = (query.get("action") or [""])[0]
    vid = (query.get("id") or [""])[0]

    # Подсказки при заполнении: свои прежние суда и типовые серии.
    if action == "suggest":
        q = (query.get("q") or [""])[0]
        return {"history": suggest_from_history(vessels, q),
                "presets": [p for p in preset_titles()
                            if not q or q.lower() in (p["title"] + " " + p["type"]).lower()]}

    if action == "preset":
        return {"values": preset_values((query.get("preset") or [""])[0])}

    if action == "save":
        data = normalize({k: (query.get(k) or [""])[0] for k in FIELD_KEYS})
        if data:
            if vid:
                for i, v in enumerate(vessels):
                    if v.get("_id") == vid:
                        data["_id"] = vid
                        vessels[i] = data
                        break
                else:
                    data["_id"] = vid
                    vessels.append(data)
            else:
                data["_id"] = f"v{int(_t.time() * 1000)}"
                vessels.append(data)
            active_id = data["_id"]
            db.save_vessels(user_id, vessels, active_id, docs)

    elif action == "select" and vid:
        if any(v.get("_id") == vid for v in vessels):
            active_id = vid
            db.save_vessels(user_id, vessels, active_id, docs)

    elif action == "delete" and vid:
        vessels = [v for v in vessels if v.get("_id") != vid]
        if active_id == vid:
            active_id = vessels[0]["_id"] if vessels else ""
        db.save_vessels(user_id, vessels, active_id, docs)

    elif action == "doc_add":
        title = (query.get("title") or [""])[0].strip()
        if title:
            docs.append({
                "id": f"d{int(_t.time() * 1000)}",
                "title": title,
                "edition": (query.get("edition") or [""])[0].strip(),
                "note": (query.get("note") or [""])[0].strip(),
            })
            db.save_vessels(user_id, vessels, active_id, docs)

    elif action == "doc_del":
        did = (query.get("doc") or [""])[0]
        docs = [d for d in docs if d.get("id") != did]
        db.save_vessels(user_id, vessels, active_id, docs)

    return vessel_payload(vessels, active_id, docs, provider_info())


def _api_ship_search(query: dict) -> dict:
    """Подсказки при вводе названия судна. Источники -- по приоритету."""
    import asyncio

    from .services.ship_providers import fetch_ship, search_ships

    db = _state["db"]
    user_id, denied = _require("vessel", query)
    if denied:
        return denied

    vessels, _active = db.get_vessels(user_id)
    q = (query.get("q") or [""])[0].strip()
    ident = (query.get("fetch") or [""])[0].strip()

    try:
        loop = asyncio.new_event_loop()
        try:
            if ident:
                card = loop.run_until_complete(fetch_ship(vessels, ident))
                return {"card": card or {}}
            if len(q) < 2:
                return {"results": [], "providers": []}
            return loop.run_until_complete(search_ships(vessels, q))
        finally:
            loop.close()
    except Exception as e:
        logger.exception("Поиск судна не удался")
        return {"results": [], "providers": [], "error": str(e)}


def _api_dsc(query: dict) -> dict:
    from .services.dsc import dsc_payload
    return dsc_payload()


def _api_prompts(query: dict) -> dict:
    """Библиотека готовых запросов к ассистенту и режимы ответа."""
    from .services.prompts import prompts_payload
    return prompts_payload()


def _api_notifications(query: dict) -> dict:
    """Лента колокольчика. ?seen=1 -- отметить всё прочитанным."""
    from .services.notify import build_feed

    db = _state["db"]
    user_id = _user_id_from_query(query)
    if user_id is None:
        return {"items": [], "unread": 0, "error": "unauthorized"}

    if (query.get("seen") or [""])[0] == "1":
        feed = build_feed(db, user_id)
        db.set_notif_seen_at(user_id)
        db.mark_support_seen(user_id, "user")
        for it in feed["items"]:
            it["unread"] = False
        feed["unread"] = 0
        return feed

    return build_feed(db, user_id)


def _api_my_ports(query: dict) -> dict:
    """Порты рейса пользователя: список, добавление, правка, удаление.

    Это заменило прежний раздел «Рейс»: маршрут строится по списку портов
    захода, а не по двум полям «откуда» и «куда». Не путать с /api/ports --
    там живёт поиск по справочнику портов, он нужен для подсказок при вводе."""
    from .services.voyage import resolve_point

    db = _state["db"]
    user_id, denied = _require("voyage", query)
    if denied:
        return denied

    action = (query.get("action") or [""])[0]
    pid = (query.get("id") or ["0"])[0]

    if action == "add":
        name = (query.get("name") or [""])[0].strip()
        if name:
            p = resolve_point(name)
            db.add_port(user_id, p.name if p else name,
                        p.country if p else "",
                        p.lat if p else None, p.lon if p else None,
                        (query.get("eta") or [""])[0].strip(),
                        (query.get("note") or [""])[0].strip())
    elif action == "del" and pid.isdigit():
        db.delete_port(user_id, int(pid))
    elif action == "edit" and pid.isdigit():
        fields = {}
        for f in ("name", "eta", "note"):
            if f in query:
                fields[f] = (query.get(f) or [""])[0].strip()
        if fields.get("name"):
            p = resolve_point(fields["name"])
            if p:
                fields.update({"name": p.name, "country": p.country, "lat": p.lat, "lon": p.lon})
        db.update_port(user_id, int(pid), **fields)
    elif action == "move" and pid.isdigit():
        # переставляем порт выше или ниже соседа
        rows = db.get_ports(user_id)
        idx = next((i for i, r in enumerate(rows) if r["id"] == int(pid)), None)
        step = -1 if (query.get("dir") or ["up"])[0] == "up" else 1
        if idx is not None and 0 <= idx + step < len(rows):
            a, b = rows[idx], rows[idx + step]
            db.update_port(user_id, a["id"], ord_num=b["ord_num"])
            db.update_port(user_id, b["id"], ord_num=a["ord_num"])

    return _ports_payload(db, user_id)


def _ports_payload(db, user_id: int) -> dict:
    """Список портов плюс расстояния между соседними и итог по рейсу."""
    from .services.voyage import Port, planned_route

    rows = db.get_ports(user_id)
    ports, prev = [], None
    total = 0.0
    for r in rows:
        item = {"id": r["id"], "name": r["name"], "country": r.get("country") or "",
                "lat": r.get("lat"), "lon": r.get("lon"),
                "eta": r.get("eta") or "", "note": r.get("note") or "",
                "leg_nm": None, "legs": []}
        if prev and prev.get("lat") is not None and r.get("lat") is not None:
            try:
                plan = planned_route(Port(prev["name"], prev.get("country") or "", prev["lat"], prev["lon"]),
                                     Port(r["name"], r.get("country") or "", r["lat"], r["lon"]))
                item["leg_nm"] = round(plan["distance_nm"])
                item["legs"] = [l.get("title") for l in plan.get("legs", []) if l.get("title")]
                total += plan["distance_nm"]
            except Exception:
                logger.exception("Не удалось посчитать участок между портами")
        ports.append(item)
        prev = r

    return {"ports": ports, "total_nm": round(total), "count": len(ports)}


def _api_port_weather(query: dict) -> dict:
    """Погода в порту: наш прогноз плюс ссылки на Windy и Ventusky.

    Свой прогноз даёт цифры, которые можно вставить в расчёт; карты Windy
    и Ventusky показывают картину вокруг порта -- в них удобно смотреть
    фронты и поля ветра, чего числами не передать."""
    import asyncio

    from .services.voyage import resolve_point
    from .services.weather import point_forecast

    name = (query.get("q") or [""])[0].strip()
    lat = (query.get("lat") or [""])[0]
    lon = (query.get("lon") or [""])[0]

    label = name
    try:
        flat, flon = float(lat), float(lon)
    except ValueError:
        p = resolve_point(name)
        if not p:
            return {"error": "not_found", "q": name}
        flat, flon, label = p.lat, p.lon, p.label

    try:
        data = asyncio.run(point_forecast(flat, flon))
    except Exception as e:
        logger.warning("Погода в порту не получена: %s", e)
        data = {"error": "no_data"}

    data["place"] = label
    data["lat"], data["lon"] = round(flat, 4), round(flon, 4)
    data["maps"] = _weather_maps(flat, flon)
    return data


def _weather_maps(lat: float, lon: float) -> list[dict]:
    """Внешние погодные карты по точке. Ссылки строятся по координатам,
    ключей и регистрации не требуют.

    В embed сознательно выключены detail, menu и message: с ними Windy
    разворачивает на всю высоту таблицу прогноза и закрыть её внутри
    окна Mini App нечем -- карты под ней просто не видно."""
    la, lo = round(lat, 3), round(lon, 3)

    def windy(overlay: str) -> str:
        return (f"https://embed.windy.com/embed2.html?lat={la}&lon={lo}"
                f"&detailLat={la}&detailLon={lo}&width=100%25&height=100%25"
                f"&zoom=6&level=surface&overlay={overlay}&product=ecmwf"
                f"&menu=false&message=false&marker=true&calendar=now"
                f"&pressure=false&type=map&location=coordinates&detail=false"
                f"&metricWind=kt&metricTemp=%C2%B0C&radarRange=-1")

    return [
        {"id": "windy_wind", "name": "Windy · ветер", "site": "Windy",
         "url": f"https://www.windy.com/?{la},{lo},8,i:pressure",
         "embed": windy("wind")},
        {"id": "windy_waves", "name": "Windy · волнение", "site": "Windy",
         "url": f"https://www.windy.com/?{la},{lo},8,i:pressure,waves",
         "embed": windy("waves")},
        {"id": "ventusky_wind", "name": "Ventusky · ветер", "site": "Ventusky",
         "url": f"https://www.ventusky.com/?p={la};{lo};7&l=wind-10m&w=kt"},
        {"id": "ventusky_waves", "name": "Ventusky · волны", "site": "Ventusky",
         "url": f"https://www.ventusky.com/?p={la};{lo};7&l=wave&w=kt"},
        {"id": "ventusky_press", "name": "Ventusky · давление", "site": "Ventusky",
         "url": f"https://www.ventusky.com/?p={la};{lo};6&l=pressure&w=kt"},
    ]


def _api_support(query: dict) -> dict:
    """Переписка с создателем бота прямо в приложении.

    Сообщение пользователя тут же уходит владельцу в Telegram обычным
    сообщением от бота -- отвечать он может там же, ответом на него."""
    db = _state["db"]
    user_id = _user_id_from_query(query)
    if user_id is None:
        return {"messages": [], "error": "unauthorized"}

    action = (query.get("action") or [""])[0]

    if action == "send":
        text = (query.get("text") or [""])[0].strip()
        if text:
            db.add_support_message(user_id, "user", text[:2000])
            _notify_owner(user_id, text[:2000])
    elif action == "seen":
        db.mark_support_seen(user_id, "user")

    msgs = db.get_support_thread(user_id, limit=100)
    return {
        "messages": [{"author": m["author"], "text": m["text"], "at": m["created_at"]} for m in msgs],
        "unread": db.support_unread_for_user(user_id),
    }


def _notify_owner(user_id: int, text: str) -> None:
    """Сообщение владельцу о новом обращении. Идёт напрямую по Bot API:
    веб-сервер живёт в своём потоке, до объекта бота отсюда не дотянуться."""
    import urllib.request

    from .config import config

    token = _state["bot_token"]
    if not token or not config.owner_ids:
        return

    name = ""
    try:
        u = _state["db"].get_user(user_id)
        name = (getattr(u, "first_name", "") or "") + (
            f" @{u.username}" if getattr(u, "username", None) else "")
    except Exception:
        pass

    body = (f"💬 Поддержка · от {name.strip() or user_id} (id {user_id})\n\n{text}\n\n"
            f"Ответить: /reply {user_id} текст")
    payload = json.dumps({"chat_id": config.owner_ids[0], "text": body}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception:
        logger.exception("Не удалось уведомить владельца об обращении")


def _api_invoice(query: dict) -> dict:
    """Ссылка на оплату подписки звёздами для кнопки внутри Mini App.

    Раньше кнопка «Оформить» просто закрывала приложение и рассчитывала,
    что человек сам наберёт /subscribe в чате -- со стороны это выглядело
    как «нажал и выкинуло на главную». Теперь ссылку делаем прямо здесь,
    а приложение открывает по ней окно оплаты Telegram (openInvoice).

    Обращаемся к Bot API напрямую по HTTP: веб-сервер живёт в своём потоке
    и до объекта бота с его циклом событий отсюда не дотянуться, а метод
    createInvoiceLink -- обычный POST.
    """
    import urllib.error
    import urllib.request

    from .config import config
    from .handlers.billing import INVOICE_PAYLOAD, SUBSCRIPTION_PERIOD_SECONDS
    from .services.access import is_owner

    token = _state["bot_token"]
    if not token:
        return {"error": "no_token"}

    user_id = _user_id_from_query(query)
    if user_id is None:
        return {"error": "unauthorized"}

    db = _state["db"]
    if is_owner(user_id):
        return {"error": "owner"}
    if db is not None and db.is_premium_active(user_id):
        return {"error": "already_premium"}

    payload = {
        "title": "WatchKeeper Premium",
        "description": (
            "Все районы NAVAREA и береговые, проверка маршрута, карточка судна, "
            "чек-листы и сертификаты, история и расширенные расчёты. "
            "Автопродление каждые 30 дней, отменить в любой момент."
        ),
        "payload": INVOICE_PAYLOAD,
        "currency": "XTR",
        "prices": [{"label": "Premium, 1 месяц", "amount": config.stars_price_monthly}],
        "subscription_period": SUBSCRIPTION_PERIOD_SECONDS,
    }
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/createInvoiceLink",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            answer = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Telegram кладёт причину отказа в тело ответа -- она полезнее кода
        try:
            answer = json.loads(e.read().decode("utf-8"))
        except Exception:
            logger.exception("createInvoiceLink не ответил")
            return {"error": "telegram_error"}
    except Exception:
        logger.exception("createInvoiceLink не ответил")
        return {"error": "network"}

    if not answer.get("ok"):
        logger.warning("createInvoiceLink отказал: %s", answer.get("description"))
        return {"error": "telegram_error", "detail": answer.get("description", "")}

    return {"link": answer["result"], "price_stars": config.stars_price_monthly}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _api_gmdss(query: dict) -> dict:
    """EPIRB и SART: оборудование пользователя, чек-листы, история проверок.
    Привязано к человеку, поэтому только с проверенной подписью Telegram."""
    from .services.bridge import (EPIRB_CHECKLIST, EPIRB_SELFTEST_STEPS,
                                  SART_CHECKLIST, SART_TEST_STEPS,
                                  gmdss_due_threshold, gmdss_status)

    db = _state["db"]
    user_id, denied = _require("bridge", query)
    if denied:
        return denied

    data = db.get_gmdss(user_id) or {}
    data.setdefault("epirb", {})
    data.setdefault("sart", {})

    action = (query.get("action") or [""])[0]
    kind = (query.get("kind") or [""])[0]

    if action == "save_equipment" and kind in ("epirb", "sart"):
        eq = data[kind]
        # Пишем только то, что реально пришло. Пустое значение -- это
        # осознанная очистка поля (кнопка «Очистить» в календаре),
        # а не повод оставить старое.
        for f in ("model", "mmsi_hex", "battery_expires", "notes"):
            if f in query:
                eq[f] = (query.get(f) or [""])[0].strip()
        db.save_gmdss(user_id, data)

    elif action == "save_checklist" and kind in ("epirb", "sart"):
        try:
            checked = json.loads((query.get("checked") or ["[]"])[0])
        except ValueError:
            checked = []
        data[kind]["checklist"] = checked
        data[kind]["checklist_at"] = _now_iso()
        db.save_gmdss(user_id, data)

    elif action == "log_test" and kind in ("epirb", "sart"):
        result = (query.get("result") or ["pass"])[0]
        entry = {"at": _now_iso(), "result": result}
        data[kind].setdefault("history", [])
        data[kind]["history"].insert(0, entry)
        data[kind]["history"] = data[kind]["history"][:30]
        db.save_gmdss(user_id, data)

    elif action == "clear_history" and kind in ("epirb", "sart"):
        data[kind]["history"] = []
        db.save_gmdss(user_id, data)

    for k in ("epirb", "sart"):
        eq = data.get(k, {})
        eq["status"] = gmdss_status(eq.get("battery_expires"))

    return {
        "equipment": data,
        "epirb_checklist": EPIRB_CHECKLIST,
        "sart_checklist": SART_CHECKLIST,
        "epirb_steps": EPIRB_SELFTEST_STEPS,
        "sart_steps": SART_TEST_STEPS,
    }


def _api_cyclones(query: dict) -> dict:
    """Тропические циклоны и их близость к маршруту.

    Данные тянутся из сети, поэтому вызов асинхронный: выполняем его в
    своём потоке обработчика. Если сеть недоступна -- отдаём пустой
    список, а не ошибку: в рейсе это обычное дело."""
    from .services.cyclone import distance_to_route, fetch_storms

    try:
        import asyncio
        storms = asyncio.run(fetch_storms())
    except Exception as e:
        logger.warning("Не удалось получить сводку по циклонам: %s", e)
        return {"storms": [], "error": "no_data"}

    # если передан маршрут -- считаем расстояние от каждого циклона до линии
    raw = (query.get("route") or [""])[0]
    route = []
    if raw:
        try:
            route = json.loads(raw)
        except ValueError:
            route = []
    if route:
        for st in storms:
            pos = st.get("position")
            if pos:
                st["route_distance_nm"] = distance_to_route(pos, route)

    return {"storms": storms}


def _api_ask(query: dict) -> dict:
    """Ask WatchKeeper: понимаем вопрос и говорим, что с ним делать.

    Приложение присылает вместе с вопросом то, что уже знает о судне,
    позиции и маршруте. Это и есть главный смысл: человек спрашивает
    "какой у меня запас под килём", а осадку своего судна диктовать
    не должен -- она в карточке."""
    from .services.ask import (ask_payload, match_colreg, match_intent,
                               match_view, match_watch)

    text = (query.get("q") or [""])[0].strip()
    if not text:
        return {"kind": "hint", **ask_payload()}

    watch_role = (query.get("watch") or ["2nd"])[0]

    ctx = {}
    raw = (query.get("ctx") or [""])[0]
    if raw:
        try:
            ctx = json.loads(raw)
        except ValueError:
            ctx = {}

    # Порядок проверок: сперва то, что распознаётся однозначно по смыслу,
    # потом расчёты. Иначе «через сколько часов моя вахта» уедет в ETA,
    # а «судно справа, что делать» -- в расчёт CPA вместо правил.

    # 0. Погода и всё, что вокруг неё, уходит к ассистенту сразу.
    #    Иначе «сколько идти до Сингапура и что там с ветром» перехватит
    #    расчёт ETA и про ветер никто не ответит.
    import re as _re
    if _re.search(r"погод|ветер|ветра|ветром|волн\w*|зыб|шторм|циклон|тайфун|ураган|"
                  r"туман|видимост|давлени\w*\s*\d*\s*(?:гпа|hpa)?|прогноз|"
                  r"weather|wind|wave|swell|storm|cyclone|typhoon|forecast|visibility",
                  text, _re.I):
        return _ask_assistant(text, query, ctx, watch_role)

    # 1. Вахта
    w = match_watch(text, schedule=watch_role)
    if w:
        nxt = w["next"]
        return {
            "kind": "watch", "intent": "WATCH", "q": text,
            "on_watch": bool(w["now_on_watch"]),
            "current": list(w["now_on_watch"]) if w["now_on_watch"] else None,
            "next_at": nxt[0].isoformat() if nxt else None,
            "next_window": list(nxt[1]) if nxt else None,
        }

    # 2. Правила расхождения
    col = match_colreg(text)
    if col:
        return {"kind": "colreg", "q": text, **col}

    # 3. Расчёт: числа из фразы плюс то, что известно приложению
    got = match_intent(text, ctx)
    if got:
        got["kind"] = "need" if got["missing"] else "tool"
        got["q"] = text
        return got

    # 4. Раздел приложения
    view = match_view(text)
    if view:
        return {"kind": "view", "q": text, **view}

    # 5. Всё остальное уходит к Claude с инструментами.
    return _ask_assistant(text, query, ctx, watch_role)


def _ask_assistant(text: str, query: dict, ctx: dict, watch_role: str) -> dict:
    """Вопрос к Claude с инструментами: он сам возьмёт погоду на переходе,
    предупреждения по району, сводку циклонов, карточку судна и позицию.

    Сервер многопоточный, каждый запрос обрабатывается в своём потоке,
    поэтому асинхронный вызов выполняется прямо здесь."""
    qa = _state.get("qa")
    if qa is None:
        return {"kind": "text", "intent": "GENERAL", "q": text,
                "text": "Ассистент не настроен: в .env не задан ключ ANTHROPIC_API_KEY."}

    pos = (ctx or {}).get("position") or {}
    route = (ctx or {}).get("route") or {}
    route_note = ""
    if route.get("from") and route.get("to"):
        route_note = f"{route['from']} — {route['to']}"
        if route.get("distance"):
            route_note += f", {route['distance']} миль"

    agent_ctx = {
        "db": _state["db"],
        "user_id": _user_id_from_query(query),
        "watch": watch_role,
        "position": {"lat": pos["lat_dec"], "lon": pos["lon_dec"]}
                    if pos.get("lat_dec") is not None else None,
        "route": route_note or None,
        "mode": (query.get("mode") or [""])[0],
    }

    try:
        import asyncio
        return {"kind": "text", "intent": "GENERAL", "q": text,
                "text": asyncio.run(qa.ask_agent(text, agent_ctx))}
    except Exception as e:
        logger.warning("Ассистент не ответил: %s", e)
        return {"kind": "text", "intent": "GENERAL", "q": text,
                "text": "Ассистент сейчас недоступен. Расчёты и справочники работают без связи."}



def _api_stations(query: dict) -> dict:
    from .services.radio import stations_payload
    return stations_payload()


def _api_zones(query: dict) -> dict:
    from .services.zones import zones_payload
    return zones_payload()



def _api_bridge(query: dict) -> dict:
    """Чек-листы и сертификаты пользователя. Всё привязано к человеку,
    поэтому только с проверенной подписью Telegram."""
    from .services.bridge import (CERT_THRESHOLDS, CHECKLIST_TEMPLATES,
                                  COMMON_CERTS, cert_status, days_left)

    db = _state["db"]
    user_id, denied = _require("bridge", query)
    if denied:
        return denied

    action = (query.get("action") or [""])[0]

    if action == "save_checklist":
        try:
            items = json.loads((query.get("items") or ["[]"])[0])
        except ValueError:
            items = []
        db.save_checklist(
            user_id,
            (query.get("template") or [""])[0],
            (query.get("port") or [""])[0],
            items,
            (query.get("completed") or ["0"])[0] == "1",
        )
    elif action == "add_cert":
        db.add_certificate(
            user_id,
            (query.get("name") or [""])[0].strip(),
            (query.get("number") or [""])[0].strip(),
            (query.get("expires") or [""])[0].strip(),
            (query.get("notes") or [""])[0].strip(),
        )
    elif action == "del_checklist":
        try:
            db.delete_checklist(user_id, int((query.get("id") or ["0"])[0]))
        except ValueError:
            pass
    elif action == "clear_checklists":
        db.clear_checklists(user_id)
    elif action == "del_cert":
        try:
            db.delete_certificate(user_id, int((query.get("id") or ["0"])[0]))
        except ValueError:
            pass

    certs = []
    for c in db.get_certificates(user_id):
        certs.append({
            "id": c["id"], "name": c["name"], "number": c.get("number"),
            "expires": str(c["expires"])[:10], "notes": c.get("notes"),
            "days_left": days_left(c["expires"]), "status": cert_status(c["expires"]),
        })

    history = []
    for h in db.get_checklists(user_id, limit=20):
        try:
            items = json.loads(h["items_json"])
        except (ValueError, TypeError):
            items = []
        done = sum(1 for i in items if i.get("done"))
        history.append({
            "id": h["id"], "template": h["template"], "port": h.get("port"),
            "created_at": h["created_at"], "completed": bool(h.get("completed_at")),
            "done": done, "total": len(items),
        })

    return {
        "templates": CHECKLIST_TEMPLATES,
        "common_certs": COMMON_CERTS,
        "certificates": certs,
        "history": history,
    }


def _api_history(query: dict) -> dict:
    """График за 30 дней плюс раскладка по районам для тепловой карты."""
    db = _state["db"]
    days = min(int((query.get("days") or ["30"])[0]), 365)
    hist = db.history(days)
    stats = _cached_stats()
    heat = sorted(
        [{"code": a["code"], "name": a["name"], "in_force": a["in_force"], "added_today": a["added_today"]}
         for a in stats["areas"] if a["in_force"] > 0],
        key=lambda x: -x["in_force"],
    )
    peak = max((h["in_force"] for h in hist), default=0)
    return {"history": hist, "heat": heat, "peak": peak,
            "max_area": heat[0]["in_force"] if heat else 0}


API_ROUTES = {
    "/api/cyclones": _api_cyclones,
    "/api/ask": _api_ask,
    "/api/gmdss": _api_gmdss,
    "/api/dsc": _api_dsc,
    "/api/prompts": _api_prompts,
    "/api/notifications": _api_notifications,
    "/api/my-ports": _api_my_ports,
    "/api/port-weather": _api_port_weather,
    "/api/support": _api_support,
    "/api/invoice": _api_invoice,
    "/api/ship-search": _api_ship_search,
    "/api/access": _api_access,
    "/api/vessel": _api_vessel,
    "/api/stations": _api_stations,
    "/api/history": _api_history,
    "/api/bridge": _api_bridge,
    "/api/zones": _api_zones,
    "/api/stats": _api_stats,
    "/api/warnings": _api_warnings,
    "/api/favorites": _api_favorites,
    "/api/ports": _api_ports,
    "/api/voyage": _api_voyage,
}


# ---------------------------------------------------------------------- #
# Страница карты (для ссылок из сообщений бота)
# ---------------------------------------------------------------------- #

_MAP_TEMPLATE = Template("""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>html,body,#map{height:100%;margin:0;font-family:system-ui,sans-serif}</style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var points = $points_json;
var popupHtml = $popup_json;
var map = L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; OpenStreetMap'
}).addTo(map);
var layer;
if (points.length <= 1) {
    layer = L.marker(points[0]).addTo(map);
    map.setView(points[0], 9);
} else {
    layer = L.polygon(points, {color:'#e8a33e', weight:3, fillOpacity:0.15}).addTo(map);
    points.forEach(function(p){ L.circleMarker(p, {radius:5, color:'#e8a33e'}).addTo(map); });
    map.fitBounds(layer.getBounds(), {padding:[30,30]});
}
layer.bindPopup(popupHtml).openPopup();
</script>
</body>
</html>
""")


def _render_map(query: dict) -> bytes:
    raw_pts = (query.get("pts") or [""])[0]
    title = (query.get("title") or ["NAVAREA"])[0]
    info = (query.get("info") or [""])[0]

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
    return _MAP_TEMPLATE.substitute(
        title=title, points_json=json.dumps(points), popup_json=json.dumps(popup)
    ).encode("utf-8")


# ---------------------------------------------------------------------- #
# HTTP
# ---------------------------------------------------------------------- #

class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        # на HEAD отдаём только заголовки, тело слать нельзя
        if getattr(self, "_with_body", True):
            self.wfile.write(body)

    def do_HEAD(self) -> None:
        """Пинг-сервисы (UptimeRobot и подобные) проверяют сервис HEAD-запросом.
        Без этого метода стандартная библиотека отвечает 501 Not Implemented,
        мониторинг считает сервис лежащим, перестаёт его нормально будить --
        и Render усыпляет процесс. Отвечаем теми же заголовками, что на GET,
        только без тела, как и положено для HEAD."""
        self._handle(with_body=False)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        self._handle(with_body=True)

    def _handle(self, with_body: bool = True) -> None:
        self._with_body = with_body
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        try:
            if path in API_ROUTES:
                data = API_ROUTES[path](query)
                self._send(200, "application/json; charset=utf-8",
                           json.dumps(data, ensure_ascii=False).encode("utf-8"))
                return

            if path == "/map":
                self._send(200, "text/html; charset=utf-8", _render_map(query))
                return

            if path == "/app":
                from .miniapp import MINI_APP_HTML
                self._send(200, "text/html; charset=utf-8", MINI_APP_HTML.encode("utf-8"))
                return

            self._send(200, "text/plain; charset=utf-8", b"navarea-bot: OK")
        except Exception as e:
            logger.exception("Ошибка при обработке %s", self.path)
            self._send(500, "application/json; charset=utf-8",
                       json.dumps({"error": str(e)}).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # глушим стандартный access-лог
        pass


def start_web_server(port: int, db=None, bot_token: str = "", qa=None) -> None:
    _state["db"] = db
    _state["qa"] = qa
    _state["bot_token"] = bot_token
    _state["started_at"] = time.time()
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Веб-сервер (Mini App + API + карта) поднят на порту %s", port)


def build_map_url(public_url: str, coords: list[tuple[float, float]], title: str, info: str = "") -> str:
    pts = ";".join(f"{lat},{lon}" for lat, lon in coords)
    return f"{public_url.rstrip('/')}/map?pts={quote(pts)}&title={quote(title)}&info={quote(info[:200])}"
