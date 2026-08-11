# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
"""Проверка разбора ответов Open-Meteo без сети: подсовываем ряды той же
формы, что отдаёт настоящий API, и смотрим, что получается на выходе."""
import asyncio, json, sys, pathlib
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(sys.argv[1])))
from bot.services import weather
from bot.services.voyage import planned_route, resolve_point

START = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
HOURS = 24 * 7
TIMES = [(START + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00") for h in range(HOURS)]


async def fake_get(client, url, params):
    if "marine" in url:
        return {"hourly": {
            "time": TIMES,
            "wave_height": [round(1.0 + (h % 24) * 0.1, 1) for h in range(HOURS)],
            "wave_direction": [210] * HOURS,
            "wave_period": [7.5] * HOURS,
            "swell_wave_height": [0.8] * HOURS,
            "swell_wave_period": [9.0] * HOURS,
        }}
    if "geocoding" in url:
        return {"results": [{"name": "Ushuaia", "country": "Аргентина",
                             "latitude": -54.8, "longitude": -68.3}]}
    return {"hourly": {
        "time": TIMES,
        # ветер приходит уже в узлах: мы просим wind_speed_unit=kn
        "wind_speed_10m": [10 + (h % 48) for h in range(HOURS)],
        "wind_gusts_10m": [15 + (h % 48) for h in range(HOURS)],
        "wind_direction_10m": [270] * HOURS,
        "pressure_msl": [1013.2] * HOURS,
        "visibility": [18520] * HOURS,
        "precipitation": [0.0] * HOURS,
        "temperature_2m": [21.4] * HOURS,
    }}


weather._get = fake_get


async def main():
    ok = True
    p = await weather.point_forecast(44.17, 28.65, when=START + timedelta(hours=5))
    print("point:", json.dumps(p, ensure_ascii=False))
    assert p["wind_kn"] == 15.0, p["wind_kn"]
    assert p["beaufort"] == 4 and p["beaufort_name"] == "умеренный", p
    assert p["wind_from"] == "W", p["wind_from"]
    assert p["visibility_nm"] == 10.0, p["visibility_nm"]
    assert p["sea_state"] in ("небольшое волнение", "умеренное волнение"), p["sea_state"]

    # проверяем шкалу Бофорта на границах
    # границы по стандартной шкале: F4 = 11-16 уз, F9 = 41-47 уз
    for kn, force in ((0.5, 0), (3, 1), (6, 2), (10, 3), (12, 4), (20, 5),
                      (25, 6), (30, 7), (36, 8), (45, 9), (50, 10), (60, 11), (70, 12)):
        f, name = weather.beaufort(kn)
        assert f == force, (kn, f, force)
    print("beaufort scale OK")

    a, b = resolve_point("Constanta"), resolve_point("Istanbul")
    plan = planned_route(a, b)
    wx = await weather.route_forecast(plan["points"], speed_kn=12.0, samples=4)
    print("route:", a.label, "->", b.label, wx["distance_nm"], "nm,",
          wx["passage_hours"], "h, eta", wx["eta"])
    for leg in wx["legs"]:
        print("   ", leg["distance_nm"], "nm", leg["at"], leg.get("wind_kn"), "kn",
              "B" + str(leg.get("beaufort")), "wave", leg.get("wave_m"))
    assert wx["legs"][0]["distance_nm"] == 0
    assert wx["legs"][-1]["distance_nm"] == wx["distance_nm"]
    assert wx["worst"] is not None and wx["worst"]["wind_kn"] > 0
    assert all(l.get("wind_kn") for l in wx["legs"]), "короткий переход не должен уходить за горизонт"

    # длинный переход: дальние точки помечаются как за горизонтом прогноза
    c = resolve_point("Santos")
    long_plan = planned_route(a, c)
    lwx = await weather.route_forecast(long_plan["points"], speed_kn=13.5, samples=5)
    beyond = [l for l in lwx["legs"] if l.get("beyond_forecast")]
    print("long passage:", lwx["distance_nm"], "nm,", lwx["passage_hours"], "h,",
          len(beyond), "legs beyond forecast")
    assert beyond, "на 20-суточном переходе часть точек обязана быть за горизонтом"
    assert lwx["legs"][0].get("wind_kn"), "первая точка должна иметь прогноз"

    g = await weather.geocode("Ushuaia")
    print("geocode:", g)
    assert g["lat"] == -54.8

    print("\nВСЕ ПРОВЕРКИ ПРОШЛИ")

asyncio.run(main())
