"""
Все проверки одной командой:

    python tests/checks/run_all.py

Сети в них нет специально: внешние ответы (Open-Meteo, Anthropic, Bot API)
подменяются заглушками той же формы. Проверки должны проходить на любой
машине без ключей и без интернета.

Что нужно поставить, если запускается впервые:
    pip install httpx anthropic python-dotenv
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]

CHECKS = [
    ("синтаксис всех модулей", "check.py"),
    ("разбор координат", "geotest.py"),
    ("защита от мультиаккаунтов", "abusetest.py"),
    ("база: порты, поддержка, уведомления", "dbtest.py"),
    ("панель владельца и подписка", "admintest.py"),
    ("рекомендации NP136", "np136test.py"),
    ("инструменты ассистента", "agenttest.py"),
    ("агентный цикл Claude", "looptest.py"),
    ("погода и маршрут", "wxfake.py"),
]


def main() -> int:
    bad = []
    for title, name in CHECKS:
        print(f"\n=== {title} ({name}) ===")
        r = subprocess.run([sys.executable, str(HERE / name), str(ROOT)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-3:]
        for ln in tail:
            print("  ", ln)
        if r.returncode != 0:
            bad.append(name)
            err = (r.stderr or "").strip().splitlines()[-6:]
            for ln in err:
                print("  !", ln)

    print("\n" + "=" * 50)
    if bad:
        print("НЕ ПРОШЛИ:", ", ".join(bad))
        return 1
    print("ВСЕ ПРОВЕРКИ ПРОШЛИ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
