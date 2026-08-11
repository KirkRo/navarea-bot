# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
"""Пробный период -- один на устройство."""
import pathlib, sys, tempfile
sys.path.insert(0, sys.argv[1])
from bot.services.db import Database
from bot.services import antiabuse

tmp = pathlib.Path(tempfile.mkdtemp()) / "t.db"
db = Database(str(tmp))

DEV = "a1b2c3d4e5f6a1b2c3d4e5f6"
FP = "Europe/Kyiv|ru|1170x2532|24|iPhone|6|5"

# первый аккаунт на устройстве -- пробный положен
antiabuse.register(db, 111, DEV, FP)
ok, why = antiabuse.trial_allowed(db, 111, DEV, FP)
assert ok, (ok, why)
print("первый аккаунт: пробный выдан")

# он же заходит снова -- по-прежнему положен
ok, _ = antiabuse.trial_allowed(db, 111, DEV, FP)
assert ok
print("тот же аккаунт повторно: пробный сохранён")

# второй аккаунт с того же устройства -- отказ
antiabuse.register(db, 222, DEV, FP)
ok, why = antiabuse.trial_allowed(db, 222, DEV, FP)
assert not ok and why == "device", (ok, why)
print("второй аккаунт на том же устройстве: отказ по", why)

# очистил хранилище -> новый device_id, но отпечаток тот же
DEV2 = "ffffffff11112222333344445555"
antiabuse.register(db, 333, DEV2, FP)
ok, why = antiabuse.trial_allowed(db, 333, DEV2, FP)
assert not ok and why == "fingerprint", (ok, why)
print("новый идентификатор, тот же отпечаток: отказ по", why)

# другое устройство -- пробный положен
DEV3 = "999988887777666655554444"
FP3 = "Asia/Singapore|en|1080x2400|24|Linux armv8l|8|5"
antiabuse.register(db, 444, DEV3, FP3)
ok, _ = antiabuse.trial_allowed(db, 444, DEV3, FP3)
assert ok
print("другое устройство: пробный выдан")

# без идентификатора устройства не отказываем: старая версия, приватный режим
ok, _ = antiabuse.trial_allowed(db, 555, "", "")
assert ok
print("устройство неизвестно: не отказываем")

# мусор в идентификаторе отбрасывается
assert antiabuse.clean_device_id("../../etc/passwd") == ""
assert antiabuse.clean_device_id("' OR 1=1 --") == ""
assert antiabuse.clean_device_id(DEV) == DEV
print("мусорный идентификатор отброшен")

# отпечаток хранится хешем, а не как есть
fp = antiabuse.fingerprint(FP)
assert fp and FP not in fp and len(fp) == 32, fp
print("отпечаток хранится хешем:", fp)

# отчёт владельцу
rows = db.device_accounts(min_accounts=2)
assert rows and rows[0]["n"] == 2, rows
print("в отчёте владельцу:", rows[0]["n"], "аккаунта на устройстве", rows[0]["device_id"][:10])

print("\nВСЕ ПРОВЕРКИ ПРОШЛИ")
