# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
"""Разбор координат из настоящих формулировок предупреждений."""
import pathlib, sys
sys.path.insert(0, sys.argv[1])
from bot.services.geo import extract_coordinates, extract_shapes

def close(a, b, tol=0.0005):
    return abs(a - b) <= tol

CASES = [
    # NGA / UKHO: градусы-минуты через дефис
    ("DRIFTING OBJECT IN 44-30.5N 030-15.2E.", [(44.50833, 30.25333)]),
    # с секундами
    ("BUOY ADRIFT 44-30-15N 030-15-40E.", [(44.50417, 30.26111)]),
    # знаки градуса и минуты (UKHO и Европа)
    ("LIGHT UNLIT 44°30'.5N 030°15'.2E.", [(44.50833, 30.25333)]),
    # с секундами и знаком секунд
    ("WRECK 44°30'15\"N 030°15'40\"E.", [(44.50417, 30.26111)]),
    # пробел вместо дефиса
    ("SURVEY 44 30.5N 030 15.2E.", [(44.50833, 30.25333)]),
    # полушарие впереди (Франция, Испания, Норвегия)
    ("POSITION N44 30.5 E030 15.2", [(44.50833, 30.25333)]),
    # десятичные градусы с запятой (испанские источники)
    ("SITUACION 44,5N 30,25E", [(44.5, 30.25)]),
    # косая черта без пробела
    ("MARK 44-30.0N/030-15.0E", [(44.5, 30.25)]),
    # южное и западное полушарие
    ("VESSEL 33-55.0S 018-25.0E", [(-33.91667, 18.41667)]),
    ("RIG AT 27-30.0N 090-15.0W", [(27.5, -90.25)]),
    # запятая между широтой и долготой
    ("AREA 10-00.0N, 020-00.0W", [(10.0, -20.0)]),
]

bad = 0
for text, want in CASES:
    got = extract_coordinates(text)
    ok = len(got) == len(want) and all(close(g[0], w[0]) and close(g[1], w[1])
                                       for g, w in zip(got, want))
    print(("OK  " if ok else "FAIL"), repr(text[:44]), "->", got, "" if ok else f"ждали {want}")
    if not ok:
        bad += 1

print("\n--- мусор не должен становиться координатами ---")
JUNK = [
    "NAVAREA III 123/26 ISSUED 151200 UTC AUG 26",   # номер и дата
    "FREQUENCY 12577.0 KHZ AND 8414.5 KHZ",          # частоты
    "CHART 2323 EDITION 2019",                        # номер карты
    "LAT 44-75.0N 030-15.0E",                         # минут больше 60
    "TIME 25-70-99N 030-15.0E",                       # заведомая чушь
    "POSITION 95-30.0N 030-15.0E",                    # широта больше 90
]
for text in JUNK:
    got = extract_coordinates(text)
    ok = not got
    print(("OK  " if ok else "FAIL"), repr(text[:46]), "->", got)
    if not ok:
        bad += 1

print("\n--- фигуры ---")
poly = ("HAZARDOUS OPERATIONS IN AREA BOUND BY 44-00.0N 030-00.0E, "
        "44-00.0N 031-00.0E, 43-00.0N 031-00.0E, 43-00.0N 030-00.0E.")
sh = extract_shapes(poly)
print("polygon:", [(s["type"], len(s["points"])) for s in sh])
assert sh and sh[0]["type"] == "polygon" and len(sh[0]["points"]) == 4, sh

line = "CABLE OPERATIONS ALONG TRACKLINE JOINING 44-00.0N 030-00.0E AND 45-00.0N 031-00.0E."
sh = extract_shapes(line)
print("line:   ", [(s["type"], len(s["points"])) for s in sh])
assert sh and sh[0]["type"] == "line", sh

pts = ("LIGHTS UNLIT: BUOY ALFA 44-00.0N 030-00.0E. BUOY BRAVO 45-00.0N 031-00.0E.")
sh = extract_shapes(pts)
print("points: ", [(s["type"], len(s["points"])) for s in sh])
assert all(s["type"] == "point" for s in sh) and len(sh) == 2, sh

print("\n--- реальные выгрузки из tests/fixtures ---")
root = pathlib.Path(sys.argv[1]) / "tests" / "fixtures"
for f in sorted(root.glob("*.txt")):
    t = f.read_text(encoding="utf-8", errors="ignore")
    c = extract_coordinates(t, max_points=200)
    s = extract_shapes(t)
    print(f"{f.name:38s} координат {len(c):3d}  фигур {len(s):3d}")
    for lat, lon in c:
        assert -90 <= lat <= 90 and -180 <= lon <= 180, (f.name, lat, lon)

print("\nПРОБЛЕМ:", bad)
sys.exit(1 if bad else 0)
