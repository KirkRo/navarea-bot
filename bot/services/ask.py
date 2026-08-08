"""
Ask Watchkeeper: понимание вопроса вахтенного.

Порядок работы взят из спецификации и важен именно в таком виде:

  1. Определить намерение (о чём вообще вопрос).
  2. Вытащить из фразы числа и названия.
  3. Дополнить тем, что приложение уже знает: карточка судна, позиция
     с устройства, текущий маршрут.
  4. Понять, чего не хватает.
  5. Если хватает -- отдать готовое действие.
  6. Если нет -- спросить ТОЛЬКО недостающее, а не весь список заново.

Ключевая мысль -- пункт 3. Человек не должен диктовать осадку своего
судна каждый раз: она уже записана в карточке. Поэтому "какой у меня
запас под килём" -- законченный вопрос, если известны позиция и осадка.

Разбор работает без сети. В рейсе спутниковый канал дорогой и рвётся,
а вопрос про запас под килём нужен именно тогда, когда некогда ждать.
К модели уходит только то, что не разобралось здесь.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_NUM = r"(-?\d+(?:[.,]\d+)?)"


def _f(v: str) -> float:
    return float(v.replace(",", "."))


def _pick(text: str, patterns: list[str]) -> float | None:
    """Первое число, найденное по любому из образцов."""
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            try:
                return _f(m.group(1))
            except (ValueError, IndexError):
                pass
    return None


# ---------------------------------------------------------------------- #
# Извлечение величин
# ---------------------------------------------------------------------- #
def x_speed(t):    return _pick(t, [rf"(?:скорост\w*|speed|sog)\s*(?:[:=])?\s*{_NUM}",
                                    rf"(?:иду|идём|идем|следую|ход\w*|на)\s*{_NUM}\s*(?:узл\w*|kn|kts?|kt)",
                                    rf"{_NUM}\s*(?:узл\w*|kn|kts?|kt)\b"])
def x_dist(t):     return _pick(t, [rf"(?:расстояни\w*|дистанц\w*|distance|до)\s*\w*\s*(?:[:=])?\s*{_NUM}\s*(?:мил\w*|nm)",
                                    rf"(?:расстояни\w*|дистанц\w*|distance)\s*(?:[:=])?\s*{_NUM}",
                                    rf"{_NUM}\s*(?:мил\w*|nm|n\.?m\.?)\b"])
def x_draft(t):    return _pick(t, [rf"(?:осадк\w*|draft|draught)\s*(?:[:=])?\s*{_NUM}"])
def x_depth(t):    return _pick(t, [rf"(?:глубин\w*|depth)\s*(?:по карте)?\s*(?:[:=])?\s*{_NUM}"])
def x_squat(t):    return _pick(t, [rf"(?:просед\w*|squat)\s*(?:[:=])?\s*{_NUM}"])
def x_tide(t):     return _pick(t, [rf"(?:прилив\w*|tide)\s*(?:[:=])?\s*{_NUM}"])
def x_heel(t):     return _pick(t, [rf"(?:крен\w*|heel|list)\s*(?:[:=])?\s*{_NUM}"])
def x_wave(t):     return _pick(t, [rf"(?:волнени\w*|wave|swell)\s*(?:[:=])?\s*{_NUM}"])
def x_cb(t):       return _pick(t, [rf"(?:cb|коэффициент полноты|полнот\w*)\s*(?:[:=])?\s*{_NUM}"])
def x_bearing(t):  return _pick(t, [rf"(?:пеленг\w*|bearing|brg)\s*(?:[:=])?\s*{_NUM}"])
def x_range(t):    return _pick(t, [rf"(?:дистанц\w*|range|до цели)\s*(?:[:=])?\s*{_NUM}"])
def x_rot(t):      return _pick(t, [rf"(?:rot|скорость поворота|угловая)\s*(?:[:=])?\s*{_NUM}"])
def x_radius(t):   return _pick(t, [rf"(?:радиус\w*|radius)\s*(?:[:=])?\s*{_NUM}"])
def x_chain(t):    return _pick(t, [rf"(?:смычек|смычк\w*|цеп\w*|shackles?|chain)\s*(?:[:=])?\s*{_NUM}",
                                    rf"{_NUM}\s*смычек"])


def x_courses(t):
    """Изменение курса: '090 -> 180', 'с 090 на 180'."""
    m = re.search(rf"{_NUM}\s*°?\s*(?:->|→|на|to)\s*{_NUM}\s*°?", t, re.I)
    if m:
        try:
            return _f(m.group(1)), _f(m.group(2))
        except ValueError:
            pass
    return None, None


def x_own_course(t):
    return _pick(t, [rf"(?:свой курс|мой курс|own course)\s*(?:[:=])?\s*{_NUM}",
                     rf"(?:курс\w*|course)\s*(?:[:=])?\s*{_NUM}"])


def x_time(t):
    """Время прибытия: 'в 06:00', 'к 0600'."""
    m = re.search(r"(?:в|к|at|by)\s*(\d{1,2})[:\.]?(\d{2})", t, re.I)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h < 24 and 0 <= mi < 60:
            return f"{h:02d}:{mi:02d}"
    return None


def x_ports(t):
    """Пара портов: 'из X в Y', 'от X до Y'."""
    m = re.search(r"(?:из|от|from)\s+([A-Za-zА-Яа-яёЁ\-' ]{3,28}?)\s+(?:в|до|на|to)\s+([A-Za-zА-Яа-яёЁ\-' ]{3,28})", t, re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"(?:до|в|to)\s+([A-Za-zА-Яа-яёЁ\-' ]{3,28})", t, re.I)
    if m:
        return None, m.group(1).strip()
    return None, None


def confined(t):
    return bool(re.search(r"канал|фарватер|мелковод|стеснённ|стесненн|confined|channel", t, re.I))


# ---------------------------------------------------------------------- #
# Намерения
# ---------------------------------------------------------------------- #
# Каждое: как узнать, какой расчёт открыть, какие поля обязательны и что
# из этого приложение может подставить само.
#
# ctx -- откуда берётся значение, если человек его не назвал:
#   vessel:<ключ>  -- из карточки судна
#   position       -- с устройства
#   route          -- из текущего маршрута

INTENTS = [
    {
        "id": "UKC", "tool": "ukc",
        "match": r"\bukc\b|запас\w*\s+(?:воды\s+)?под\s+кил|под килем|под килём|clearance",
        "fields": {
            "cd": {"get": x_depth,  "req": True,  "label": "Глубина по карте", "unit": "м"},
            "dr": {"get": x_draft,  "req": True,  "label": "Осадка", "unit": "м", "ctx": "vessel:draft"},
            "sq": {"get": x_squat,  "req": False, "label": "Проседание", "unit": "м"},
            "td": {"get": x_tide,   "req": False, "label": "Высота прилива", "unit": "м"},
            "hl": {"get": x_heel,   "req": False, "label": "Поправка на крен", "unit": "м"},
            "wv": {"get": x_wave,   "req": False, "label": "Поправка на волнение", "unit": "м"},
        },
    },
    {
        "id": "SQUAT", "tool": "squat",
        "match": r"просед\w*|squat",
        "fields": {
            "cb": {"get": x_cb,    "req": True,  "label": "Коэффициент полноты Cb", "ctx": "vessel:cb"},
            "v":  {"get": x_speed, "req": True,  "label": "Скорость", "unit": "узлов", "ctx": "vessel:speed"},
            "w":  {"get": None,    "req": False, "label": "Акватория"},
        },
    },
    {
        "id": "CPA_TCPA", "tool": "cpa",
        "match": r"\bcpa\b|\btcpa\b|расхожд\w*|разойд\w*|цель\b|цели\b|target",
        "not": r"что делать|кто уступ|мои действия|как расходит|правил\w*\s+\d",
        "fields": {
            "oc": {"get": x_own_course, "req": True, "label": "Свой курс", "unit": "°"},
            "os": {"get": x_speed,      "req": True, "label": "Своя скорость", "unit": "узлов", "ctx": "vessel:speed"},
            "tb": {"get": x_bearing,    "req": True, "label": "Пеленг на цель", "unit": "°"},
            "tr": {"get": x_range,      "req": True, "label": "Дистанция до цели", "unit": "миль"},
            "tc": {"get": None,         "req": False, "label": "Курс цели", "unit": "°"},
            "ts": {"get": None,         "req": False, "label": "Скорость цели", "unit": "узлов"},
        },
    },
    {
        "id": "ETA", "tool": "eta",
        "match": r"\beta\b|когда прид|через сколько (?:часов|времени|прид)|время в пути|сколько идти|когда будем",
        "not": r"вахт\w*|watch|смена",
        "fields": {
            "d": {"get": x_dist,  "req": True, "label": "Расстояние", "unit": "миль", "ctx": "route:distance"},
            "s": {"get": x_speed, "req": True, "label": "Скорость", "unit": "узлов", "ctx": "vessel:speed"},
        },
    },
    {
        "id": "SPEED_TO_ARRIVE", "tool": "eta",
        "match": r"как(?:ую|ой)\s+скорость|чтобы прийти|чтобы успеть|нужно прибыть|держать чтобы",
        "fields": {
            "d":  {"get": x_dist, "req": True, "label": "Расстояние", "unit": "миль", "ctx": "route:distance"},
            "ha": {"get": None,   "req": True, "label": "Времени в запасе", "unit": "часов"},
        },
    },
    {
        "id": "WHEEL_OVER", "tool": "wop",
        "match": r"wheel over|\bwop\b|точк\w*\s+перекладк|перекладк\w*\s+рул",
        "fields": {
            "r":  {"get": x_radius, "req": True, "label": "Радиус циркуляции", "unit": "миль"},
            "cc": {"get": None,     "req": True, "label": "Изменение курса", "unit": "°"},
            "sp": {"get": x_speed,  "req": False, "label": "Скорость", "unit": "узлов", "ctx": "vessel:speed"},
        },
    },
    {
        "id": "ANCHOR", "tool": "anchor",
        "match": r"якор\w*|anchor|смычек|радиус разворот",
        "fields": {
            "ch":  {"get": x_chain, "req": True,  "label": "Вытравлено цепи", "unit": "смычек"},
            "dp":  {"get": x_depth, "req": True,  "label": "Глубина", "unit": "м"},
            "hh":  {"get": None,    "req": False, "label": "Высота клюза", "unit": "м", "ctx": "vessel:hawse"},
            "loa": {"get": None,    "req": False, "label": "Длина судна", "unit": "м", "ctx": "vessel:loa"},
        },
    },
    {
        "id": "COURSE_DISTANCE", "tool": "dist",
        "match": r"расстояни\w*\s+и\s+курс|курс\w*\s+и\s+расстояни|great circle|ортодром|локсодром",
        "fields": {
            "la1": {"get": None, "req": True, "label": "Широта отхода", "ctx": "position:lat"},
            "lo1": {"get": None, "req": True, "label": "Долгота отхода", "ctx": "position:lon"},
            "la2": {"get": None, "req": True, "label": "Широта прихода"},
            "lo2": {"get": None, "req": True, "label": "Долгота прихода"},
        },
    },
    {
        "id": "SUN", "tool": "sun",
        "match": r"восход|заход|сумерк|twilight|sunrise|sunset|темно",
        "fields": {
            "la": {"get": None, "req": True,  "label": "Широта", "ctx": "position:lat"},
            "lo": {"get": None, "req": True,  "label": "Долгота", "ctx": "position:lon"},
            "dt": {"get": None, "req": False, "label": "Дата"},
        },
    },
    {
        "id": "MOON", "tool": "moon",
        "match": r"лун\w*|moon|фаза",
        "fields": {
            "la": {"get": None, "req": True, "label": "Широта", "ctx": "position:lat"},
            "lo": {"get": None, "req": True, "label": "Долгота", "ctx": "position:lon"},
        },
    },
    {
        "id": "AIR_DRAFT", "tool": "air",
        "match": r"под мост|air draft|air draught|надводн\w*\s+габарит|высот\w*\s+мост",
        "fields": {
            "cc":  {"get": None,    "req": True,  "label": "Габарит по карте", "unit": "м"},
            "hat": {"get": None,    "req": False, "label": "HAT", "unit": "м"},
            "tn":  {"get": x_tide,  "req": False, "label": "Текущий прилив", "unit": "м"},
            "ad":  {"get": None,    "req": True,  "label": "Надводный габарит судна", "unit": "м", "ctx": "vessel:air_draft"},
        },
    },
    {
        "id": "FUEL", "tool": "fuel",
        "match": r"топлив\w*|бункер\w*|fuel|bunker|хватит ли",
        "fields": {
            "d":   {"get": x_dist,  "req": True,  "label": "Расстояние", "unit": "миль", "ctx": "route:distance"},
            "s":   {"get": x_speed, "req": True,  "label": "Скорость", "unit": "узлов", "ctx": "vessel:speed"},
            "c":   {"get": None,    "req": True,  "label": "Расход в сутки", "unit": "т", "ctx": "vessel:cons"},
            "rob": {"get": None,    "req": False, "label": "Топлива на борту", "unit": "т"},
        },
    },
    {
        "id": "MAGNETRON", "tool": "magnetron",
        "match": r"магнетрон|magnetron|ресурс радар",
        "fields": {
            "rx":   {"get": None, "req": True,  "label": "RX time", "unit": "часов"},
            "life": {"get": None, "req": False, "label": "Ресурс", "unit": "часов"},
        },
    },
    {
        "id": "CONVERTER", "tool": "units",
        "match": r"переведи|конверт|сколько будет|в километр|в узл|в метр|в фут|в градус|knots?\s*(?:в|to)",
        "fields": {"val": {"get": lambda t: _pick(t, [rf"{_NUM}"]), "req": True, "label": "Значение"}},
    },
]


def _ctx_value(spec: str, ctx: dict):
    """Значение из контекста приложения: карточка судна, позиция, маршрут."""
    if not spec or not ctx:
        return None
    kind, _, key = spec.partition(":")
    src = ctx.get(kind) or {}
    v = src.get(key)
    if v in ("", None):
        return None
    return v


def match_intent(text: str, ctx: dict | None = None) -> dict | None:
    """Определяет намерение и собирает параметры."""
    ctx = ctx or {}
    for spec in INTENTS:
        if not re.search(spec["match"], text, re.I):
            continue
        # Некоторые вопросы похожи по словам, но относятся к другому:
        # «через сколько часов моя вахта» -- это не ETA, а расписание,
        # «судно справа, что делать» -- не расчёт CPA, а правила расхождения.
        if spec.get("not") and re.search(spec["not"], text, re.I):
            continue

        values, from_ctx, missing = {}, {}, []
        for key, f in spec["fields"].items():
            v = f["get"](text) if f.get("get") else None
            if v is None and f.get("ctx"):
                v = _ctx_value(f["ctx"], ctx)
                if v is not None:
                    from_ctx[key] = f["ctx"]
            if v is not None:
                values[key] = v
            elif f.get("req"):
                missing.append({"k": key, "label": f["label"], "unit": f.get("unit", "")})

        # частные доводки
        if spec["id"] == "SQUAT" and confined(text):
            values["w"] = "confined"
        if spec["id"] == "UKC":
            sp = x_speed(text)
            if sp is not None and "sq" not in values:
                values["_hint"] = {"tool": "squat", "values": {"v": sp}}
        if spec["id"] == "WHEEL_OVER":
            c1, c2 = x_courses(text)
            if c1 is not None and c2 is not None:
                d = (c2 - c1) % 360
                values["cc"] = d if d <= 180 else d - 360
                missing = [m for m in missing if m["k"] != "cc"]
            rot = x_rot(text)
            if rot and "r" not in values and values.get("sp"):
                # Радиус циркуляции из скорости и угловой скорости.
                # За полный оборот (360/ROT минут) судно проходит длину
                # окружности, отсюда R = V * 3 / (ROT * pi).
                # Проверка: 14 узлов при 20 град/мин дают 0.67 мили.
                import math
                values["r"] = round(values["sp"] * 3 / (rot * math.pi), 3)
                missing = [m for m in missing if m["k"] != "r"]
        if spec["id"] == "SPEED_TO_ARRIVE":
            at = x_time(text)
            if at:
                values["_arrive_at"] = at
                missing = [m for m in missing if m["k"] != "ha"]

        # ничего не нашли и подставить неоткуда -- значит это не то намерение
        if not values and missing:
            continue

        return {
            "intent": spec["id"], "action": "calculate", "tool": spec["tool"],
            "values": {k: v for k, v in values.items() if not k.startswith("_")},
            "from_context": from_ctx,
            "missing": missing,
            "hint_tool": values.get("_hint"),
            "arrive_at": values.get("_arrive_at"),
        }
    return None


# ---------------------------------------------------------------------- #
# Намерения без расчёта: разделы приложения
# ---------------------------------------------------------------------- #
VIEW_INTENTS = [
    {"id": "NAVAREA", "view": "voy",
     "match": r"навари|navarea|предупрежд\w*|warning|влияют на маршрут|по маршруту|по пути"},
    {"id": "PASSAGE_PLAN", "view": "voy",
     "match": r"passage plan|проверь маршрут|проверь мой маршрут|проложи|переход\w*\s+из"},
    {"id": "MSI", "view": "areas",
     "match": r"\bmsi\b|навтекс|navtex|безопасност\w*\s+мореплав"},
    {"id": "VESSEL", "view": "ship",
     "match": r"мо[её]\w*\s+судн\w*|данные судна|карточк\w*\s+судна|my vessel|параметры судна|моё судно"},
    {"id": "GMDSS_EQUIPMENT", "view": "epirb",
     "match": r"epirb|аварийн\w*\s+радиобу|когда.*(?:провер|тест).*(?:epirb|буй)"},
    {"id": "GMDSS_SART", "view": "sart",
     "match": r"\bsart\b|транспондер|радиолокационн\w*\s+ответчик"},
    {"id": "GMDSS_DSC", "view": "dsc",
     "match": r"\bцив\b|\bdsc\b|тренаж|вызов бедствия|distress call"},
    {"id": "RADIO", "view": "radio",
     "match": r"радиостанц\w*|coast (?:radio )?station|станци\w*\s+для теста|mf/hf"},
    {"id": "CHECKLIST", "view": "bridge",
     "match": r"чек-?лист|checklist|перед прих|перед отход|сдач\w*\s+вахты|handover"},
    {"id": "MAP", "view": "map",
     "match": r"покажи на карте|на карте|карт[уы]\b"},
    {"id": "POSITION", "view": None,
     "match": r"где я|моя позиц|current position|мои координат|позиция сейчас"},
]


def match_view(text: str) -> dict | None:
    for spec in VIEW_INTENTS:
        if re.search(spec["match"], text, re.I):
            out = {"intent": spec["id"], "action": "open", "view": spec["view"]}
            if spec["id"] in ("NAVAREA", "PASSAGE_PLAN"):
                a, b = x_ports(text)
                if a: out["from"] = a
                if b: out["to"] = b
            return out
    return None


# ---------------------------------------------------------------------- #
# Вахта
# ---------------------------------------------------------------------- #
WATCH_SCHEDULES = {
    "2nd": [(0, 4), (12, 16)],
    "3rd": [(8, 12), (20, 24)],
    "ch":  [(4, 8), (16, 20)],
}


def match_watch(text: str, now: datetime | None = None, schedule: str = "2nd") -> dict | None:
    if not re.search(r"вахт\w*|watch|когда (?:мне )?засту|смена", text, re.I):
        return None
    now = now or datetime.now(timezone.utc)
    hours = WATCH_SCHEDULES.get(schedule, WATCH_SCHEDULES["2nd"])
    cur = next(((a, b) for a, b in hours if a <= now.hour < b), None)
    nxt = None
    for day in (0, 1):
        for a, b in hours:
            start = (now + timedelta(days=day)).replace(hour=a % 24, minute=0, second=0, microsecond=0)
            if start > now and (nxt is None or start < nxt[0]):
                nxt = (start, (a, b))
    return {"now_on_watch": cur, "next": nxt, "schedule": hours}


# ---------------------------------------------------------------------- #
# COLREG: какое правило применимо
# ---------------------------------------------------------------------- #
def match_colreg(text: str) -> dict | None:
    """Какое правило расхождения применимо.

    Признаки ищем независимо друг от друга: фраза «судно справа, пеленг
    035, что делать» и «что делать, если цель слева» одинаково законны,
    а требовать определённый порядок слов было бы придиркой."""
    direct = re.search(r"colreg|мппсс|правил\w*\s+\d|кто уступ|обгон|расхожден\w*\s+прав|навстреч|лоб в лоб|head.?on|ограниченн\w*\s+видим|restricted visibility", text, re.I)
    asks = re.search(r"что делать|как расходит|как расход|мои действия|кто кого", text, re.I)
    about = re.search(r"судн\w*|цел[ьи]\b|target|встречн\w*|справа|слева|туман|пеленг", text, re.I)
    if not direct and not (asks and about):
        return None

    brg = x_bearing(text)
    # Сторону могут назвать словом, без пеленга
    if brg is None:
        if re.search(r"справа|starboard", text, re.I):
            brg = 45.0
        elif re.search(r"слева|port side|по левому", text, re.I):
            brg = 315.0
    situation, rule, action = None, None, None

    if re.search(r"обгон|overtaking", text, re.I) or (brg is not None and (brg > 112.5 and brg < 247.5)):
        situation, rule = "OVERTAKING", "Правило 13"
        action = "Обгоняющий уступает дорогу. Держись в стороне до полного расхождения."
    elif re.search(r"навстреч|лоб в лоб|head.?on", text, re.I) or (brg is not None and (brg <= 5 or brg >= 355)):
        situation, rule = "HEAD_ON", "Правило 14"
        action = "Оба поворачивают вправо и расходятся левыми бортами."
    elif brg is not None and 5 < brg <= 112.5:
        situation, rule = "CROSSING", "Правило 15"
        action = "Цель справа -- уступаешь ты. Поворот вправо, за корму цели. Правило 16: действуй заблаговременно и решительно."
    elif brg is not None and 247.5 <= brg < 355:
        situation, rule = "CROSSING", "Правило 15"
        action = "Цель слева -- ты сохраняешь курс и скорость (Правило 17). Следи: если цель не уступает, действуй сам."
    else:
        situation, rule = "UNKNOWN", None
        action = "Нужен пеленг на цель, чтобы определить ситуацию."

    if re.search(r"туман|ограниченн\w*\s+видим|restricted visibility", text, re.I):
        situation, rule = "RESTRICTED_VISIBILITY", "Правило 19"
        action = ("В ограниченной видимости преимущественного права нет ни у кого. "
                  "Сбавь ход до безопасного, будь готов остановиться. Избегай поворота влево "
                  "на цель впереди траверза и поворота на цель на траверзе или позади.")

    return {"intent": "COLREG", "situation": situation, "rule": rule,
            "action": action, "bearing": brg}


def ask_payload() -> dict:
    return {
        "examples": [
            "Посчитай UKC: глубина 15.8, осадка 11.4, прилив 0.8, squat 0.6",
            "До Singapore 426 миль, скорость 14.5. Когда придём?",
            "Какие NAVAREA влияют на мой маршрут?",
            "Судно справа, пеленг 035, что делать?",
            "Какой squat при 13 узлах?",
            "Через сколько часов моя вахта?",
        ],
        "intents": [i["id"] for i in INTENTS] + [v["id"] for v in VIEW_INTENTS] + ["WATCH", "COLREG", "GENERAL"],
    }
