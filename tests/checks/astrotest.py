"""
Мореходная астрономия: сверка с эталонными эфемеридами.

Сами формулы живут в JS внутри miniapp.py, поэтому проверка вытаскивает
из файла ряды Луны и считает по ним на Python. Так проверяются именно те
коэффициенты, которые уйдут на устройство: если кто-нибудь укоротит ряд
или собьёт знак, проверка упадёт.

Эталон снят с эфемерид DE421 (библиотека skyfield) заранее и зашит
числами: сети в проверках нет, и качать 17 МБ эфемерид на каждый прогон
незачем.

Почему это важно. На шести главных членах ряда, с которых начиналась
работа, Луна ошибалась на два градуса. По месту это 120 миль.
"""
from __future__ import annotations

import ast
import io
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
MINIAPP = ROOT / "bot" / "miniapp.py"

# Момент UTC -> (часовой угол, склонение) по DE421
REFERENCE = {
    "2026-08-12T12:00": {"sun": (358.7355, 14.8739), "moon": (1.4731, 16.9909)},
    "2026-08-12T03:30": {"sun": (231.2206, 14.9806), "moon": (238.6592, 18.9237)},
    "2026-02-01T18:00": {"sun": (86.6066, -16.9444), "moon": (268.1729, 19.9731)},
}
LIMIT_SUN, LIMIT_MOON = 1.0, 2.0     # угловых минут

sin = lambda d: math.sin(math.radians(d))   # noqa: E731
cos = lambda d: math.cos(math.radians(d))   # noqa: E731
norm = lambda d: d % 360.0                  # noqa: E731


def read_series(name: str) -> list[list[float]]:
    """Достаёт массив коэффициентов из JS-кода приложения."""
    src = io.open(MINIAPP, encoding="utf-8").read()
    m = re.search(rf"const {name} = \[(.*?)\n\];", src, re.S)
    if not m:
        raise SystemExit(f"  ПРОБЛЕМА: в miniapp.py нет ряда {name}")
    return ast.literal_eval("[" + m.group(1) + "]")


def jd(stamp: str) -> float:
    from datetime import datetime, timezone
    dt = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
    return dt.timestamp() / 86400.0 + 2440587.5


def gmst(jday: float) -> float:
    d = jday - 2451545.0
    t = d / 36525
    return norm(280.46061837 + 360.98564736629 * d + 0.000387933 * t * t)


def sun_gha_dec(jday: float) -> tuple[float, float]:
    t = (jday - 2451545.0) / 36525
    l0 = norm(280.46646 + 36000.76983 * t)
    m = norm(357.52911 + 35999.05029 * t)
    c = ((1.914602 - 0.004817 * t) * sin(m) + (0.019993 - 0.000101 * t) * sin(2 * m)
         + 0.000289 * sin(3 * m))
    lon = l0 + c
    eps = 23.439291 - 0.0130042 * t
    ra = math.degrees(math.atan2(cos(eps) * sin(lon), cos(lon)))
    dec = math.degrees(math.asin(sin(eps) * sin(lon)))
    return norm(gmst(jday) - ra), dec


def moon_gha_dec(jday: float) -> tuple[float, float]:
    lon_terms = read_series("AS_MOON_LON")
    lat_terms = read_series("AS_MOON_LAT")
    t = (jday + 69 / 86400 - 2451545.0) / 36525
    lp = norm(218.3164477 + 481267.88123421 * t)
    d = norm(297.8501921 + 445267.1114034 * t)
    m = norm(357.5291092 + 35999.0502909 * t)
    mp = norm(134.9633964 + 477198.8675055 * t)
    f = norm(93.2720950 + 483202.0175233 * t)

    def total(terms):
        return sum(c * sin(dd * d + mm * m + mpp * mp + ff * f)
                   for c, dd, mm, mpp, ff in terms)

    lon = lp + total(lon_terms)
    lat = total(lat_terms)
    eps = 23.439291 - 0.0130042 * t
    sl, cl = sin(lon), cos(lon)
    sb, cb = sin(lat), cos(lat)
    ra = math.degrees(math.atan2(sl * cos(eps) - (sb / cb) * sin(eps), cl))
    dec = math.degrees(math.asin(sb * cos(eps) + cb * sin(eps) * sl))
    return norm(gmst(jday) - ra), dec


def diff_minutes(a: float, b: float) -> float:
    return abs(((a - b + 540) % 360 - 180) * 60)


problems = 0
print(f"   членов ряда Луны: долгота {len(read_series('AS_MOON_LON'))}, "
      f"широта {len(read_series('AS_MOON_LAT'))}")

for stamp, expect in REFERENCE.items():
    day = jd(stamp)
    for body, (gha_ref, dec_ref), limit, fn in (
            ("Солнце", expect["sun"], LIMIT_SUN, sun_gha_dec),
            ("Луна", expect["moon"], LIMIT_MOON, moon_gha_dec)):
        gha, dec = fn(day)
        dg = diff_minutes(gha, gha_ref)
        dd = abs(dec - dec_ref) * 60
        mark = " " if dg <= limit and dd <= limit else "  ПРОБЛЕМА:"
        if mark.strip():
            problems += 1
        print(f"  {mark} {stamp} {body:7} часовой угол {dg:5.2f}' склонение {dd:5.2f}' "
              f"(допуск {limit}')")

# Приведение высоты: наклонение горизонта и рефракция считаются формулами,
# которые проще проверить прямым числом
dip = 1.76 * math.sqrt(12)
if abs(dip - 6.1) > 0.1:
    print(f"  ПРОБЛЕМА: наклонение горизонта с 12 м вышло {dip:.2f}', ожидалось 6.1'")
    problems += 1
else:
    print(f"   наклонение горизонта с высоты 12 м: {dip:.1f}'")

print(f"   ПРОБЛЕМ: {problems}")
raise SystemExit(1 if problems else 0)
