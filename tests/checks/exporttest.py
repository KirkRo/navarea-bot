"""
Выгрузка предупреждений: форматы собираются и делятся по районам.

Главное, что проверяется, это отдельный файл на каждый район. Складывать
районы в один файл нельзя: на мостике их грузят в разные слои, и общая
свалка заставляет отделять чужие предупреждения руками.

Данные берутся из настоящих канадских выгрузок в tests/fixtures, сети в
проверке нет.
"""
from __future__ import annotations

import io
import os
import pathlib
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
sys.path.insert(0, str(ROOT))

from bot.services import export  # noqa: E402
from bot.services.db import Database  # noqa: E402
from bot.services.sources.canada_ccg import parse_messages  # noqa: E402
import bot.webapp as webapp  # noqa: E402

problems = 0

db = Database(os.path.join(tempfile.mkdtemp(), "export_check.db"))
for area, fixture in (("XVII", "canada_xvii_sample.html"),
                      ("XVIII", "canada_xviii_sample.html")):
    raw = io.open(ROOT / "tests" / "fixtures" / fixture, encoding="utf-8").read()
    for m in parse_messages(area, raw):
        db.insert_warning(source="ccg", area_code=area, msg_number=m.msg_number,
                          category=None, issued_at=None, region=m.region, raw_text=m.raw_text)
webapp._state["db"] = db

# Каждый формат обязан собраться и разложиться по районам
for fmt in export.FORMATS:
    result = webapp._api_export({"fmt": [fmt]})
    files = result.get("files") or []
    areas = sorted(f["area"] for f in files)
    if areas != ["XVII", "XVIII"]:
        print(f"  ПРОБЛЕМА: {fmt} дал районы {areas}, ожидались XVII и XVIII")
        problems += 1
        continue
    if any(f["bytes"] < 100 for f in files):
        print(f"  ПРОБЛЕМА: {fmt} собрал пустой файл: {files}")
        problems += 1
        continue
    if any(f["area"] not in f["filename"] for f in files):
        print(f"  ПРОБЛЕМА: {fmt} не положил код района в имя файла: {files}")
        problems += 1
        continue
    print(f"   {fmt:10} файлов {len(files)}: " +
          ", ".join(f"{f['filename']} ({f['count']})" for f in files))

# Отправка: по одному документу на район, а не один общий.
# Подпись Telegram и сам вызов Bot API подменяем: сети в проверках нет,
# а проверить надо именно то, сколько документов уходит.
calls = []
original_send, original_user = webapp._send_document, webapp._user_id_from_query
webapp._send_document = lambda uid, name, blob, mime, caption="": (
    calls.append(name) or True)
webapp._user_id_from_query = lambda q: 555
try:
    sent = webapp._api_export({"fmt": ["geojson"], "send": ["1"]})
finally:
    webapp._send_document, webapp._user_id_from_query = original_send, original_user

if len(calls) != 2 or sent.get("sent") != 2:
    print(f"  ПРОБЛЕМА: отправлено {len(calls)} документов вместо двух: {calls}")
    problems += 1
else:
    print(f"   отправка: {len(calls)} документа, по одному на район")

# Shapefile должен оставаться распаковываемым архивом с проекцией
blob, _mime, name = export.build("shapefile", [
    {"area": "XVII", "number": "1/26", "region": "Arctic", "issued": "2026-01-01",
     "text": "test", "shapes": [], "points": [(71.0, -80.0)]}], area="XVII")
with zipfile.ZipFile(io.BytesIO(blob)) as zf:
    names = zf.namelist()
if not any(n.endswith(".prj") for n in names) or not any(n.endswith(".shp") for n in names):
    print(f"  ПРОБЛЕМА: в архиве Shapefile нет .shp или .prj: {names}")
    problems += 1
else:
    print(f"   {name}: {len(names)} файлов внутри, проекция на месте")

print(f"   ПРОБЛЕМ: {problems}")
raise SystemExit(1 if problems else 0)
