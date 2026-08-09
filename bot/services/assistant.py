"""
Ассистент вахтенного: Claude, которому дали инструменты.

Смысл в том, что модель сама решает, каких данных ей не хватает, и берёт
их из бота: погоду на переходе, действующие предупреждения, циклоны,
карточку судна, позицию с устройства. Без этого на вопрос «какая будет
погода на переходе Констанца -- Сантос» можно ответить только общими
словами, а с инструментами -- цифрами на конкретные сутки пути.

Инструменты намеренно крупные. Мелкие («дай широту порта») заставляли бы
модель делать по пять кругов на каждый вопрос: каждый круг -- это лишний
запрос к API, деньги и секунды ожидания в рейсе на спутниковом канале.
Поэтому route_weather сразу отдаёт и маршрут, и время прихода, и погоду
по точкам.

Никаких действий наружу инструменты не совершают: только читают. Модель
не может ничего отправить, оплатить или изменить в чужих данных.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_ROUNDS = 5          # столько раз подряд модель может попросить инструмент
MAX_WARNINGS = 12       # больше в ответ не кладём: съедает контекст без пользы


TOOLS = [
    {
        "name": "route_weather",
        "description": (
            "Погода и состояние моря на переходе между двумя портами с учётом времени "
            "прихода в каждую точку маршрута. Маршрут прокладывается через проливы и каналы, "
            "а не по прямой через сушу. Использовать для любых вопросов вида «какая будет "
            "погода на переходе», «попадём ли в шторм», «сколько идти»."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_port": {"type": "string", "description": "Порт отправления: название или координаты."},
                "to_port": {"type": "string", "description": "Порт прибытия: название или координаты."},
                "speed_kn": {"type": "number", "description": "Скорость в узлах. Если не сказана, взять из карточки судна или 12."},
            },
            "required": ["from_port", "to_port"],
        },
    },
    {
        "name": "point_weather",
        "description": (
            "Погода и состояние моря в одной точке: порт, город или координаты. "
            "Ветер, порывы, волна, зыбь, давление, видимость."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "place": {"type": "string", "description": "Название места или координаты. Пусто -- текущая позиция судна."},
                "hours_ahead": {"type": "number", "description": "Через сколько часов нужен прогноз. По умолчанию сейчас."},
            },
            "required": [],
        },
    },
    {
        "name": "navarea_warnings",
        "description": (
            "Действующие предупреждения NAVAREA и береговые. Либо вдоль маршрута между "
            "двумя портами, либо по району, либо поиском по тексту."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_port": {"type": "string", "description": "Порт отправления, если нужны предупреждения на маршруте."},
                "to_port": {"type": "string", "description": "Порт прибытия."},
                "area": {"type": "string", "description": "Код района, например NAVAREA III."},
                "query": {"type": "string", "description": "Слово или фраза для поиска по тексту предупреждений."},
            },
            "required": [],
        },
    },
    {
        "name": "tropical_cyclones",
        "description": "Активные тропические циклоны: положение, ветер, давление, прогноз пути.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "ship_and_position",
        "description": (
            "Карточка судна пользователя (название, позывной, MMSI, размеры, осадка, скорость) "
            "и его текущая позиция с устройства. Вызывать, когда для ответа нужны данные судна."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "distance_and_eta",
        "description": "Расстояние по маршруту между двумя портами и время в пути на заданной скорости.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_port": {"type": "string"},
                "to_port": {"type": "string"},
                "speed_kn": {"type": "number"},
            },
            "required": ["from_port", "to_port"],
        },
    },
    {
        "name": "ocean_passage",
        "description": (
            "Рекомендации по океанскому переходу между двумя портами по Admiralty "
            "Ocean Passages for the World (NP136): рекомендованный путь, сезонные "
            "соображения, преобладающие ветры и течения, на что обратить внимание. "
            "Использовать при вопросах «как лучше идти», «каким путём», «что учитывать "
            "на переходе», «когда лучше выходить»."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_port": {"type": "string"},
                "to_port": {"type": "string"},
            },
            "required": ["from_port", "to_port"],
        },
    },
]


SYSTEM = """Ты -- ассистент вахтенного помощника внутри приложения WatchKeeper.
Спрашивают моряки торгового флота: судоводители, механики, курсанты.

Отвечай по-русски (или на языке вопроса), коротко и по существу, без вежливых
предисловий и без списка того, что ты сейчас будешь делать. Числа -- в морских
единицах: мили, узлы, метры, градусы, время UTC.

Как работать:
- Не хватает данных -- возьми их инструментом, а не спрашивай у человека то,
  что бот и так знает. Осадка, скорость, позиция, маршрут уже есть в приложении.
- Спросили про погоду на переходе -- бери route_weather, а не общие рассуждения
  о сезонах. Дай ветер, волну и где именно на маршруте будет хуже всего.
- Прогноз дальше недели недостоверен. Если переход длиннее -- так и скажи:
  первые сутки по цифрам, дальше только по климатологии района.
- Отвечай и на вопросы, не связанные с ботом: правила расхождения, конвенции,
  устройство судна, документы, портовые формальности, бытовые вопросы рейса.
  Если вопрос совсем не морской -- всё равно ответь, коротко.
- Не выдумывай номера предупреждений, координаты, даты и пункты конвенций.
  Не уверен -- скажи, к какому первоисточнику свериться.
- Расчёты, от которых зависит безопасность, подавай как справочные: решение
  принимает судоводитель по судовым пособиям и официальным данным.
- Спросили про путь и порядок перехода между портами -- бери ocean_passage.
  Отвечая по нему, ссылайся на Ocean Passages for the World (NP136) и
  напоминай, что окончательный план строится по самому изданию и картам.
- Про предупреждения всегда помни: бот не заменяет приём MSI штатным
  оборудованием GMDSS и NAVTEX. Напоминай об этом, когда речь о них.

Форматирование: обычный текст, короткие абзацы, при перечислении -- строки,
начинающиеся с «— ». Никакого Markdown со звёздочками и решётками: он уходит
в Telegram как есть и выглядит мусором."""


# ---------------------------------------------------------------------- #
# Выполнение инструментов
# ---------------------------------------------------------------------- #

def _vessel_of(ctx: dict) -> dict:
    """Активная карточка судна, если она есть."""
    db, user_id = ctx.get("db"), ctx.get("user_id")
    if not db or not user_id:
        return {}
    try:
        vessels, active_id = db.get_vessels(user_id)
    except Exception:
        return {}
    for v in vessels or []:
        if v.get("_id") == active_id:
            return v
    return (vessels or [{}])[0] if vessels else {}


def _speed_of(ctx: dict, asked: float | None) -> float:
    if asked:
        return float(asked)
    v = _vessel_of(ctx)
    try:
        if v.get("speed"):
            return float(str(v["speed"]).replace(",", "."))
    except (TypeError, ValueError):
        pass
    return 12.0


def _resolve(text: str, ctx: dict):
    """Порт из справочника, координаты или что-то, что нашлось геокодером."""
    from .voyage import Port, resolve_point

    if not text:
        pos = ctx.get("position") or {}
        if pos.get("lat") is not None:
            return Port(name="текущая позиция", country="", lat=pos["lat"], lon=pos["lon"])
        return None
    p = resolve_point(text)
    if p:
        return p
    return None


async def _resolve_async(text: str, ctx: dict):
    p = _resolve(text, ctx)
    if p:
        return p
    from .voyage import Port
    from .weather import geocode

    g = await geocode(text)
    if g and g.get("lat") is not None:
        return Port(name=g["label"], country="", lat=g["lat"], lon=g["lon"])
    return None


async def _tool_route_weather(args: dict, ctx: dict) -> dict:
    from .voyage import planned_route
    from .weather import route_forecast

    a = await _resolve_async(args.get("from_port", ""), ctx)
    b = await _resolve_async(args.get("to_port", ""), ctx)
    if not a or not b:
        missing = "отправления" if not a else "прибытия"
        return {"error": f"не удалось определить порт {missing}"}

    plan = planned_route(a, b)
    speed = _speed_of(ctx, args.get("speed_kn"))
    wx = await route_forecast(plan["points"], speed_kn=speed)
    wx["from"] = a.label
    wx["to"] = b.label
    wx["via"] = [leg.get("title") for leg in plan.get("legs", []) if leg.get("title")]
    return wx


async def _tool_point_weather(args: dict, ctx: dict) -> dict:
    from datetime import timedelta

    from .weather import point_forecast

    p = await _resolve_async(args.get("place", ""), ctx)
    if not p:
        return {"error": "не удалось определить место; позиция с устройства тоже недоступна"}
    when = datetime.now(timezone.utc)
    hours = args.get("hours_ahead")
    if hours:
        when += timedelta(hours=float(hours))
    data = await point_forecast(p.lat, p.lon, when=when)
    data["place"] = p.label
    return data


def _warnings_brief(rows) -> list[dict]:
    out = []
    for w in rows[:MAX_WARNINGS]:
        text = (w["raw_text"] or "").strip().replace("\n", " ")
        out.append({
            "area": w["area_code"],
            "number": w["msg_number"],
            "issued": str(w["issued_at"])[:16] if w["issued_at"] else None,
            "text": text[:600],
        })
    return out


async def _tool_warnings(args: dict, ctx: dict) -> dict:
    db = ctx.get("db")
    if not db:
        return {"error": "база предупреждений недоступна"}

    frm, to = args.get("from_port"), args.get("to_port")
    if frm and to:
        from .voyage import planned_route, warnings_on_route

        a = await _resolve_async(frm, ctx)
        b = await _resolve_async(to, ctx)
        if not a or not b:
            return {"error": "не удалось определить порты"}
        plan = planned_route(a, b)
        found = warnings_on_route(plan["points"], db.all_active_warnings(), corridor_nm=150.0)
        return {"mode": "route", "from": a.label, "to": b.label,
                "corridor_nm": 150, "count": len(found),
                "results": [{"area": f["area_code"], "number": f["msg_number"],
                             "region": f.get("region"),
                             "distance_nm": f["distance_nm"],
                             "text": (f["raw_text"] or "").replace("\n", " ")[:600]}
                            for f in found[:MAX_WARNINGS]]}

    areas = [args["area"]] if args.get("area") else None
    rows = db.search_warnings(query=args.get("query", "") or "", areas=areas,
                              include_archived=False, limit=MAX_WARNINGS)
    return {"mode": "search", "area": args.get("area"), "query": args.get("query"),
            "count": len(rows), "results": _warnings_brief(rows)}


async def _tool_cyclones(args: dict, ctx: dict) -> dict:
    from .cyclone import fetch_storms

    try:
        storms = await fetch_storms(with_forecast=True)
    except Exception as e:
        return {"error": f"сводка недоступна: {e}"}
    return {"count": len(storms), "storms": storms[:6]}


async def _tool_ship(args: dict, ctx: dict) -> dict:
    v = _vessel_of(ctx)
    pos = ctx.get("position") or {}
    return {
        "vessel": v or None,
        "position": {"lat": pos.get("lat"), "lon": pos.get("lon")} if pos.get("lat") is not None else None,
        "watch": ctx.get("watch"),
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


async def _tool_distance(args: dict, ctx: dict) -> dict:
    from .voyage import haversine_nm, planned_route

    a = await _resolve_async(args.get("from_port", ""), ctx)
    b = await _resolve_async(args.get("to_port", ""), ctx)
    if not a or not b:
        return {"error": "не удалось определить порты"}
    plan = planned_route(a, b)
    speed = _speed_of(ctx, args.get("speed_kn"))
    hours = plan["distance_nm"] / speed
    return {
        "from": a.label, "to": b.label,
        "distance_nm": round(plan["distance_nm"]),
        "direct_nm": round(haversine_nm(a.lat, a.lon, b.lat, b.lon)),
        "via": [leg.get("title") for leg in plan.get("legs", []) if leg.get("title")],
        "speed_kn": speed,
        "passage_hours": round(hours, 1),
        "passage_days": round(hours / 24, 1),
    }


async def _tool_passage(args: dict, ctx: dict) -> dict:
    from .np136 import passage_note

    a = await _resolve_async(args.get("from_port", ""), ctx)
    b = await _resolve_async(args.get("to_port", ""), ctx)
    if not a or not b:
        return {"error": "не удалось определить порты"}
    # Сперва прокладываем маршрут: по проливам на пути находятся замечания
    # даже там, где отдельной статьи по паре районов нет.
    via, dist = [], None
    try:
        from .voyage import planned_route
        plan = planned_route(a, b)
        dist = round(plan["distance_nm"])
        via = [l.get("title") for l in plan.get("legs", []) if l.get("title")]
    except Exception:
        logger.exception("Не удалось проложить маршрут для рекомендации")

    out = passage_note(a.lat, a.lon, b.lat, b.lon, via=via)
    out["from"] = a.label
    out["to"] = b.label
    out["planned_distance_nm"] = dist
    out["planned_via"] = via
    return out


RUNNERS = {
    "ocean_passage": _tool_passage,
    "route_weather": _tool_route_weather,
    "point_weather": _tool_point_weather,
    "navarea_warnings": _tool_warnings,
    "tropical_cyclones": _tool_cyclones,
    "ship_and_position": _tool_ship,
    "distance_and_eta": _tool_distance,
}


async def run_tool(name: str, args: dict, ctx: dict) -> str:
    runner = RUNNERS.get(name)
    if runner is None:
        return json.dumps({"error": f"неизвестный инструмент {name}"}, ensure_ascii=False)
    try:
        result = await runner(args or {}, ctx)
    except Exception as e:
        logger.exception("Инструмент %s не отработал", name)
        result = {"error": str(e)}
    return json.dumps(result, ensure_ascii=False, default=str)


def context_note(ctx: dict) -> str:
    """Короткая сводка того, что боту известно и так -- чтобы модель не
    дёргала инструменты за очевидным."""
    bits = [f"Сейчас {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC."]
    v = _vessel_of(ctx)
    if v.get("name"):
        parts = [str(v["name"])]
        if v.get("type"):
            parts.append(str(v["type"]))
        if v.get("callsign"):
            parts.append(f"позывной {v['callsign']}")
        if v.get("mmsi"):
            parts.append(f"MMSI {v['mmsi']}")
        if v.get("loa"):
            parts.append(f"длина {v['loa']} м")
        if v.get("draft_now") or v.get("draft_summer"):
            parts.append(f"осадка {v.get('draft_now') or v.get('draft_summer')} м")
        if v.get("air_draft"):
            parts.append(f"надводный габарит {v['air_draft']} м")
        if v.get("speed"):
            parts.append(f"скорость {v['speed']} уз")
        bits.append("Судно: " + ", ".join(parts) + ".")
    pos = ctx.get("position") or {}
    if pos.get("lat") is not None:
        bits.append(f"Позиция с устройства: {pos['lat']:.3f}, {pos['lon']:.3f}.")
    if ctx.get("route"):
        bits.append(f"Открыт маршрут: {ctx['route']}.")
    return " ".join(bits)
