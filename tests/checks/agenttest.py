# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
"""Проверка инструментов ассистента без сети и без обращения к модели."""
import asyncio, json, sys, pathlib
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(sys.argv[1])))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import wxfake_stub  # подменяет weather._get

from bot.services import assistant


class FakeRow(dict):
    def __getitem__(self, k):
        return dict.get(self, k)


class FakeDB:
    def get_vessels(self, user_id):
        return ([{"_id": "v1", "name": "MERIDIAN", "type": "Bulk carrier",
                  "callsign": "UBXY", "mmsi": "273123456", "loa": 190.0,
                  "draft_now": 11.4, "air_draft": 42.0, "speed": 13.5, "cb": 0.83}], "v1")

    def all_active_warnings(self):
        return [FakeRow(id=1, area_code="NAVAREA III", msg_number="123/26",
                        region="Black Sea",
                        raw_text="BLACK SEA. 1. DRIFTING OBJECT REPORTED IN 44-30.0N 030-15.0E. "
                                 "WIDE BERTH REQUESTED. 2. CANCEL THIS MSG 152359Z AUG 26.")]

    def search_warnings(self, query="", areas=None, include_archived=False, limit=20):
        return self.all_active_warnings()


CTX = {"db": FakeDB(), "user_id": 42,
       "position": {"lat": 44.17, "lon": 28.65}, "watch": "2nd", "route": None}


async def main():
    print("--- контекст, который видит модель ---")
    print(assistant.context_note(CTX))
    assert "MERIDIAN" in assistant.context_note(CTX)

    for name, args in [
        ("ship_and_position", {}),
        ("distance_and_eta", {"from_port": "Constanta", "to_port": "Istanbul"}),
        ("route_weather", {"from_port": "Constanta", "to_port": "Istanbul"}),
        ("point_weather", {"place": ""}),
        ("navarea_warnings", {"from_port": "Constanta", "to_port": "Istanbul"}),
        ("navarea_warnings", {"query": "drifting"}),
        ("unknown_tool", {}),
    ]:
        out = await assistant.run_tool(name, args, CTX)
        data = json.loads(out)
        short = json.dumps(data, ensure_ascii=False)
        print(f"\n[{name}] {args}\n  -> {short[:340]}")

    # скорость должна браться из карточки судна, а не по умолчанию
    d = json.loads(await assistant.run_tool(
        "distance_and_eta", {"from_port": "Constanta", "to_port": "Istanbul"}, CTX))
    assert d["speed_kn"] == 13.5, d
    d2 = json.loads(await assistant.run_tool(
        "distance_and_eta", {"from_port": "Constanta", "to_port": "Istanbul", "speed_kn": 9}, CTX))
    assert d2["speed_kn"] == 9.0 and d2["passage_hours"] > d["passage_hours"]

    # пустое место -> берётся позиция с устройства
    p = json.loads(await assistant.run_tool("point_weather", {"place": ""}, CTX))
    assert p.get("place") == "текущая позиция", p

    # без позиции и без места инструмент честно говорит, что не смог
    p2 = json.loads(await assistant.run_tool("point_weather", {"place": ""}, {"db": FakeDB()}))
    assert "error" in p2, p2

    # места нет в справочнике портов -> подхватывает геокодер
    e = json.loads(await assistant.run_tool(
        "route_weather", {"from_port": "Ushuaia", "to_port": "Istanbul"}, CTX))
    assert e["from"].startswith("Ushuaia"), e
    assert "Мыс Горн" in e["via"] and "Босфор" in e["via"], e["via"]
    print("\ngeocoder fallback:", e["from"], "->", e["to"], "via", e["via"])

    w = json.loads(await assistant.run_tool(
        "navarea_warnings", {"from_port": "Constanta", "to_port": "Istanbul"}, CTX))
    assert w["count"] == 1 and w["results"][0]["area"] == "NAVAREA III", w

    print("\nВСЕ ПРОВЕРКИ ПРОШЛИ")

asyncio.run(main())
