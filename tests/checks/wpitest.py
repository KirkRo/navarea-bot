"""
Справочник портов World Port Index: файл на месте, поиск находит, приливы
и расстояния считаются.

Проверка нужна прежде всего на случай, если файл данных не доедет до
сервера при выкладке: без него раздел портов молча опустеет, а так
падение видно сразу.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
sys.path.insert(0, str(ROOT))

from bot.services import wpi  # noqa: E402

problems = 0
total = wpi.count()
print(f"   портов в справочнике: {total}")
if total < 3000:
    print(f"  ПРОБЛЕМА: портов всего {total}, файл данных потерян или обрезан")
    problems += 1

# Поиск по бытовому названию: в самой публикации Одесса записана как Odesa
for query, expect in (("одесса", "Odesa"), ("odessa", "Odesa"),
                      ("rotterdam", "Rotterdam"), ("hamburg", "Hamburg")):
    found = wpi.search(query, limit=5)
    if not any(p["name"].lower().startswith(expect.lower()) for p in found):
        print(f"  ПРОБЛЕМА: по запросу {query!r} не нашёлся {expect}")
        problems += 1

# Величина прилива: залив Фанди известен самыми большими приливами в мире,
# и если в справочнике там ноль, значит колонка разобралась не та
eastport = wpi.search("eastport", limit=1)
if not eastport or not eastport[0].get("tide_m"):
    print("  ПРОБЛЕМА: у Истпорта нет величины прилива")
    problems += 1
elif eastport[0]["tide_m"] < 3:
    print(f"  ПРОБЛЕМА: прилив Истпорта {eastport[0]['tide_m']} м, ожидались метры залива Фанди")
    problems += 1
else:
    print(f"   Истпорт, залив Фанди: {eastport[0]['tide_m']} м")

# Ближайшие порты к Одесскому рейду: соседи по побережью должны быть рядом
near = wpi.nearest(46.5, 30.75, limit=3)
if not near or near[0]["distance_nm"] > 10:
    print(f"  ПРОБЛЕМА: ближайший порт к одесскому рейду {near[:1]}")
    problems += 1
else:
    print(f"   ближайшие к 46.5N 30.75E: " +
          ", ".join(f"{p['name']} {p['distance_nm']}" for p in near))

# Координаты обязаны быть в границах глобуса: ошибка знака или разбора
# ГГММ вылезает именно здесь
bad = [p for p in wpi._load() if not (-90 <= p["lat"] <= 90) or not (-180 <= p["lon"] <= 180)]
if bad:
    print(f"  ПРОБЛЕМА: координаты вне глобуса у {len(bad)} портов, например {bad[0]}")
    problems += 1

with_tide = sum(1 for p in wpi._load() if p.get("tide_m"))
print(f"   с величиной прилива: {with_tide}")

print(f"   ПРОБЛЕМ: {problems}")
raise SystemExit(1 if problems else 0)
