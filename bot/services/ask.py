"""
Ask Watchkeeper: понимание вопроса вахтенного.

Устроено в два слоя, и порядок здесь принципиален.

Сначала работает разбор на месте, без сети: он узнаёт типовые вопросы
вахтенного и вытаскивает из фразы числа. В рейсе спутниковый интернет
дорогой и ненадёжный, а вопрос "какой у меня запас под килём" нужен
именно тогда, когда некогда ждать ответа сервера. Поэтому всё, что можно
понять по числам и словам, понимается локально и мгновенно.

Если фраза не похожа ни на один из знакомых образцов -- вопрос уходит
к Claude как обычный разговор о судовождении.

Разбор намеренно не пытается быть умным: он ищет число рядом со знакомым
словом. Это надёжнее хитрых правил и понятно, когда ошибается.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------- #
# Как достаём числа
# ---------------------------------------------------------------------- #
# Число может быть с точкой или запятой: 11.5 и 11,5 -- одно и то же.
_NUM = r"(-?\d+(?:[.,]\d+)?)"


def _f(v: str) -> float:
    return float(v.replace(",", "."))


def _find(text: str, words: list[str], after: bool = True) -> float | None:
    """Ищет число рядом со словом. after=True -- число после слова
    ("осадка 11.5"), иначе перед ним ("11.5 м осадка")."""
    for w in words:
        pat = (rf"{w}\s*(?:[:=]|—|-)?\s*{_NUM}" if after
               else rf"{_NUM}\s*(?:м|m|узл\w*|kn|kt|kts)?\s*{w}")
        m = re.search(pat, text, re.I)
        if m:
            try:
                return _f(m.group(1))
            except ValueError:
                pass
    return None


# ---------------------------------------------------------------------- #
# Что умеем узнавать
# ---------------------------------------------------------------------- #
# Для каждого расчёта: по каким словам его узнать и как разобрать поля.
# Ключи полей совпадают с теми, что в приложении -- иначе подстановка
# не сработает.

def _speed(text: str) -> float | None:
    """Скорость пишут по-разному: "скорость 14", "иду 14 узлов", "на 13 узлах",
    "14 kn". Ловим все формы, а не только слово перед числом."""
    for pat in (rf"(?:скорост\w*|speed)\s*(?:[:=])?\s*{_NUM}",
                rf"(?:иду|идём|идем|следую|ход\w*|на)\s*{_NUM}\s*(?:узл\w*|kn|kts?|kt)",
                rf"{_NUM}\s*(?:узл\w*|kn|kts?|kt)\b"):
        m = re.search(pat, text, re.I)
        if m:
            try:
                return _f(m.group(1))
            except ValueError:
                pass
    return None


def _distance(text: str) -> float | None:
    """Расстояние: "480 миль", "расстояние 480", "480 nm"."""
    for pat in (rf"(?:расстояни\w*|дистанц\w*|distance)\s*(?:[:=])?\s*{_NUM}",
                rf"{_NUM}\s*(?:мил\w*|nm|n\.?m\.?)\b"):
        m = re.search(pat, text, re.I)
        if m:
            try:
                return _f(m.group(1))
            except ValueError:
                pass
    return None


DRAFT_W  = ["осадк\\w*", "draft", "draught"]
DEPTH_W  = ["глубин\\w*", "depth", "глубина по карте"]
SQUAT_W  = ["просед\\w*", "squat"]
TIDE_W   = ["прилив\\w*", "tide"]
SPEED_W  = ["скорост\\w*", "speed", "ход\\w*", "иду", "идём", "следую"]
DIST_W   = ["расстояни\\w*", "дистанц\\w*", "distance", "миль", "nm"]
CB_W     = ["cb", "коэффициент полноты", "полнот\\w*"]
HEEL_W   = ["крен\\w*", "heel", "list"]
WAVE_W   = ["волнени\\w*", "wave", "swell"]


def _ukc(text: str) -> dict | None:
    depth = _find(text, DEPTH_W)
    draft = _find(text, DRAFT_W)
    if depth is None and draft is None:
        return None
    vals = {}
    if depth is not None: vals["cd"] = depth
    if draft is not None: vals["dr"] = draft
    sq = _find(text, SQUAT_W)
    if sq is not None: vals["sq"] = sq
    td = _find(text, TIDE_W)
    if td is not None: vals["td"] = td
    hl = _find(text, HEEL_W)
    if hl is not None: vals["hl"] = hl
    wv = _find(text, WAVE_W)
    if wv is not None: vals["wv"] = wv
    out = {"tool": "ukc", "values": vals}
    # Скорость на запас под килём напрямую не влияет, но влияет через
    # проседание -- подсказываем, что его стоит посчитать отдельно.
    sp = _speed(text)
    if sp is not None and "sq" not in vals:
        out["hint_tool"] = {"tool": "squat", "values": {"v": sp}}
    return out


def _squat(text: str) -> dict | None:
    v = _speed(text)
    cb = _find(text, CB_W)
    if v is None and cb is None:
        return None
    vals = {}
    if v is not None: vals["v"] = v
    if cb is not None: vals["cb"] = cb
    # мелководье или канал упомянуты -- это меняет коэффициент в формуле
    if re.search(r"канал|фарватер|мелковод|стеснённ|стесненн|confined|channel", text, re.I):
        vals["w"] = "confined"
    return {"tool": "squat", "values": vals}


def _eta(text: str) -> dict | None:
    d = _distance(text)
    s = _speed(text)
    if d is None or s is None:
        return None
    return {"tool": "eta", "values": {"d": d, "s": s}}


def _cpa(text: str) -> dict | None:
    if not re.search(r"cpa|tcpa|расхожд\w*|разойд\w*|цел[ьи]|target", text, re.I):
        return None
    vals = {}
    oc = _find(text, ["свой курс", "мой курс", "курс\\w*"])
    if oc is not None: vals["oc"] = oc
    os_ = _speed(text)
    if os_ is not None: vals["os"] = os_
    tb = _find(text, ["пеленг\\w*", "bearing"])
    if tb is not None: vals["tb"] = tb
    tr = _find(text, ["дистанц\\w*", "range", "расстояни\\w*"])
    if tr is not None: vals["tr"] = tr
    return {"tool": "cpa", "values": vals} if vals else None


# Порядок важен: более узкие образцы проверяются раньше общих.
TOOL_MATCHERS = [
    (r"\bukc\b|запас\w*\s+(?:воды\s+)?под\s+кил|под килем|под килём|clearance", _ukc),
    (r"просед\w*|squat", _squat),
    (r"\bcpa\b|\btcpa\b|расхожд\w*|разойд\w*", _cpa),
    (r"\beta\b|через сколько (?:часов|времени)|когда прид|время в пути|сколько идти", _eta),
]


def match_tool(text: str) -> dict | None:
    for pattern, fn in TOOL_MATCHERS:
        if re.search(pattern, text, re.I):
            got = fn(text)
            if got and got.get("values"):
                return got
    # чисел хватает на запас под килём, даже если слова UKC не было
    if re.search(r"глубин\w*", text, re.I) and re.search(r"осадк\w*|draft", text, re.I):
        got = _ukc(text)
        if got and len(got["values"]) >= 2:
            return got
    return None


# ---------------------------------------------------------------------- #
# Переход и предупреждения по маршруту
# ---------------------------------------------------------------------- #
def match_route(text: str) -> dict | None:
    if not re.search(r"навари|navarea|предупрежд\w*|warning|маршрут\w*|route|переход\w*|по пути", text, re.I):
        return None
    m = re.search(r"(?:из|от|from)\s+([A-Za-zА-Яа-яёЁ\- ]{3,28}?)\s+(?:в|до|to|на)\s+([A-Za-zА-Яа-яёЁ\- ]{3,28})", text, re.I)
    out = {"view": "voy"}
    if m:
        out["from"] = m.group(1).strip()
        out["to"] = m.group(2).strip()
    return out


# ---------------------------------------------------------------------- #
# Вахта
# ---------------------------------------------------------------------- #
# Второй помощник стоит 00-04 и 12-16, это его штатная вахта.
WATCH_SCHEDULES = {
    "2nd": [(0, 4), (12, 16)],
    "3rd": [(8, 12), (20, 24)],
    "ch":  [(4, 8), (16, 20)],
}


def match_watch(text: str, now: datetime | None = None, schedule: str = "2nd") -> dict | None:
    if not re.search(r"вахт\w*|watch|когда (?:мне )?засту|через сколько.*вахт", text, re.I):
        return None
    now = now or datetime.now(timezone.utc)
    hours = WATCH_SCHEDULES.get(schedule, WATCH_SCHEDULES["2nd"])

    cur = None
    for a, b in hours:
        if a <= now.hour < b:
            cur = (a, b)
            break

    # ближайшее начало вахты
    nxt = None
    for day in (0, 1):
        for a, b in hours:
            start = (now + timedelta(days=day)).replace(hour=a % 24, minute=0, second=0, microsecond=0)
            if start > now and (nxt is None or start < nxt[0]):
                nxt = (start, (a, b))
    return {"now_on_watch": cur, "next": nxt, "schedule": hours}


def ask_payload() -> dict:
    """Подсказки для интерфейса: что вообще можно спросить."""
    return {
        "examples": [
            "Иду 14 узлов, глубина 16 м, осадка 11.5, проседание 0.8. Какой запас под килём?",
            "Какие NAVAREA влияют на мой маршрут из Одессы в Сингапур?",
            "Через сколько часов моя вахта?",
            "Проседание на 12 узлах, Cb 0.82, канал",
            "Идти 480 миль на 13 узлах, когда придём?",
        ],
        "schedules": {"2nd": "00-04 и 12-16", "3rd": "08-12 и 20-24", "ch": "04-08 и 16-20"},
    }
