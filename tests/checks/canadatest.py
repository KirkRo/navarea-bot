"""
Разбор канадских предупреждений (NAVAREA XVII и XVIII) на настоящих
выгрузках, сохранённых в tests/fixtures.

Смысл проверки не в числе сообщений, а в том, что вёрстка источника
разобралась: номера на месте, служебные перечни отброшены, координаты
из текста читаются. Если Canadian Coast Guard поменяет шаблон страницы,
проверка упадёт здесь, а не тихо на боевом сервере пустым списком.
"""
from __future__ import annotations

import io
import pathlib
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
sys.path.insert(0, str(ROOT))

from bot.services.geo import extract_coordinates  # noqa: E402
from bot.services.sources.canada_ccg import parse_messages  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"

problems = 0

for area, fixture in (("XVII", "canada_xvii_sample.html"),
                      ("XVIII", "canada_xviii_sample.html")):
    path = FIXTURES / fixture
    raw = io.open(path, encoding="utf-8").read()
    msgs = parse_messages(area, raw)

    with_coords = sum(1 for m in msgs if extract_coordinates(m.raw_text))
    cancels = sum(len(m.cancels) for m in msgs)
    print(f"   {fixture:28} сообщений {len(msgs):3}  с координатами {with_coords:3}  отмен {cancels}")

    if not msgs:
        print(f"  ПРОБЛЕМА: {area} не разобрался вовсе")
        problems += 1
        continue

    for m in msgs:
        if not m.msg_number or "/" not in m.msg_number:
            print(f"  ПРОБЛЕМА: {area} сообщение без номера: {m.raw_text[:60]}")
            problems += 1
            break
        if "WARNINGS IN FORCE AT" in m.raw_text.upper():
            # перечень действующих номеров переиздаётся постоянно и в базу
            # попадать не должен, иначе людям каждый раз уходит уведомление
            print(f"  ПРОБЛЕМА: {area} служебный перечень попал в выдачу: {m.msg_number}")
            problems += 1
            break
        if "<" in m.raw_text and ">" in m.raw_text:
            print(f"  ПРОБЛЕМА: {area} в тексте осталась вёрстка: {m.msg_number}")
            problems += 1
            break

    # хотя бы часть сообщений обязана давать координаты: канадские тексты
    # почти всегда содержат точку, и ноль здесь означает сломанный разбор
    if with_coords == 0:
        print(f"  ПРОБЛЕМА: {area} ни одной координаты")
        problems += 1

print(f"   ПРОБЛЕМ: {problems}")
raise SystemExit(1 if problems else 0)
