# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
"""Проверка агентного цикла: подменяем клиента Anthropic и смотрим, что
уходит в модель на каждом круге и что она получает обратно."""
import asyncio, json, sys, pathlib

sys.path.insert(0, str(pathlib.Path(sys.argv[1])))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import wxfake_stub  # noqa

from bot.services.claude_qa import ClaudeQA
from agenttest import CTX


class Blk:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Resp:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class FakeMessages:
    def __init__(self, script, seen):
        self.script, self.seen = script, seen

    async def create(self, **kw):
        self.seen.append(kw)
        return self.script.pop(0)


class FakeClient:
    def __init__(self, script, seen):
        self.messages = FakeMessages(script, seen)


async def main():
    seen = []
    script = [
        Resp("tool_use", [
            Blk(type="text", text="сейчас посмотрю"),
            Blk(type="tool_use", id="t1", name="route_weather",
                input={"from_port": "Constanta", "to_port": "Istanbul"}),
        ]),
        Resp("tool_use", [
            Blk(type="tool_use", id="t2", name="navarea_warnings",
                input={"from_port": "Constanta", "to_port": "Istanbul"}),
        ]),
        Resp("end_turn", [Blk(type="text", text="Ветер до 41 узла, волна 3.3 м.")]),
    ]

    qa = ClaudeQA("test-key", "claude-haiku-4-5-20251001", 700)
    qa._clients[asyncio.get_running_loop()] = FakeClient(script, seen)

    answer = await qa.ask_agent("Какая погода на переходе Constanta - Istanbul?", CTX)
    print("ОТВЕТ:", answer)
    assert answer == "Ветер до 41 узла, волна 3.3 м."

    print("\nкругов к модели:", len(seen))
    assert len(seen) == 3

    assert "WatchKeeper" in seen[0]["system"] and "MERIDIAN" in seen[0]["system"]
    assert [t["name"] for t in seen[0]["tools"]][0] == "route_weather"

    print("\n--- сообщения на последнем круге ---")
    for m in seen[-1]["messages"]:
        c = m["content"]
        if isinstance(c, str):
            print(f"  {m['role']}: {c[:70]}")
        else:
            for b in c:
                if isinstance(b, dict):
                    body = str(b.get("content", ""))[:90]
                    print(f"  {m['role']}: {b['type']} {b.get('tool_use_id','')} {body}")
                else:
                    print(f"  {m['role']}: {b.type} {getattr(b,'name','')}")

    msgs = seen[-1]["messages"]
    assert msgs[0]["role"] == "user"
    # у каждого tool_use должен быть ровно один tool_result с тем же id
    used, got = [], []
    for m in msgs:
        c = m["content"]
        if isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    got.append(b["tool_use_id"])
                elif getattr(b, "type", None) == "tool_use":
                    used.append(b.id)
    assert used == got == ["t1", "t2"], (used, got)
    # ответы инструментов -- валидный JSON со свежей погодой
    for m in msgs:
        if isinstance(m["content"], list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    json.loads(b["content"])

    # круги ограничены: если модель просит инструменты бесконечно
    seen2 = []
    endless = [Resp("tool_use", [Blk(type="text", text=f"шаг {i}"),
                                 Blk(type="tool_use", id=f"x{i}", name="ship_and_position", input={})])
               for i in range(5)]
    endless_qa = ClaudeQA("k", "m", 700)
    endless_qa._clients[asyncio.get_running_loop()] = FakeClient(
        endless + [Resp("end_turn", [Blk(type="text", text="хватит")])], seen2)
    out = await endless_qa.ask_agent("зациклись", CTX)
    print("\nпри бесконечных запросах инструментов:", out, "| кругов:", len(seen2))
    assert out == "хватит" and len(seen2) == 6, (out, len(seen2))
    assert "tools" not in seen2[-1], "последний круг должен идти без инструментов"
    # роли обязаны чередоваться: подряд двух user быть не должно
    roles = [m["role"] for m in seen2[-1]["messages"]]
    assert all(a != b for a, b in zip(roles, roles[1:])), roles
    print("чередование ролей:", " ".join(roles))

    # а если последний ответ пуст -- отдаём то, что модель уже сказала
    seen3 = []
    silent_qa = ClaudeQA("k", "m", 700)
    silent_qa._clients[asyncio.get_running_loop()] = FakeClient(
        endless + [Resp("end_turn", [])], seen3)
    out3 = await silent_qa.ask_agent("зациклись", CTX)
    print("при пустом финальном ответе:", repr(out3))
    assert "шаг 0" in out3 and "шаг 4" in out3, out3

    print("\nВСЕ ПРОВЕРКИ ПРОШЛИ")

asyncio.run(main())
