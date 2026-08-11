# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
import asyncio, json, sys, pathlib
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, str(pathlib.Path(__file__).parent))
import wxfake_stub  # noqa
from bot.services import assistant
from agenttest import CTX

async def main():
    for a, b in [("Constanta","Santos"),("Odesa","Istanbul"),("Rotterdam","New York"),
                 ("Piraeus","Singapore"),("Constanta","Rotterdam")]:
        out = json.loads(await assistant.run_tool("ocean_passage", {"from_port":a,"to_port":b}, CTX))
        print(f"\n=== {a} -> {b} ===  {out.get('planned_distance_nm')} миль")
        print("путь:", (out.get("route") or out.get("note"))[:150])
        for c in out.get("chokepoints", []):
            print("   *", c["point"] + ":", c["note"][:80])
        assert out.get("source","").startswith("Admiralty"), out
    print("\nВСЕ ПРОВЕРКИ ПРОШЛИ")

asyncio.run(main())
