# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
"""Проверка новых таблиц на настоящей SQLite-базе во временном файле."""
import pathlib, sys, tempfile

sys.path.insert(0, sys.argv[1])
from bot.services.db import Database

tmp = pathlib.Path(tempfile.mkdtemp()) / "t.db"
db = Database(str(tmp))
db.upsert_user(555, "kirk", "Кирк")

# --- порты ---
a = db.add_port(555, "Constanta", "Румыния", 44.17, 28.65, "12.08 06:00")
b = db.add_port(555, "Istanbul", "Турция", 41.02, 28.97)
c = db.add_port(555, "Piraeus", "Греция", 37.94, 23.63)
ports = db.get_ports(555)
assert [p["name"] for p in ports] == ["Constanta", "Istanbul", "Piraeus"], ports
assert ports[0]["eta"] == "12.08 06:00"

# перестановка местами
db.update_port(555, a, ord_num=ports[1]["ord_num"])
db.update_port(555, b, ord_num=ports[0]["ord_num"])
assert [p["name"] for p in db.get_ports(555)] == ["Istanbul", "Constanta", "Piraeus"]

db.update_port(555, c, note="бункеровка")
assert db.get_ports(555)[2]["note"] == "бункеровка"
db.delete_port(555, c)
assert len(db.get_ports(555)) == 2
print("порты: ок")

# --- поддержка ---
db.add_support_message(555, "user", "Не открывается календарь")
assert db.support_unread_for_user(555) == 0, "своё сообщение прочитанным быть должно"
db.add_support_message(555, "owner", "Поправил, обнови")
assert db.support_unread_for_user(555) == 1
th = db.support_threads()
assert th and th[0]["user_id"] == 555 and th[0]["unread"] == 1, th
db.mark_support_seen(555, "user")
assert db.support_unread_for_user(555) == 0
msgs = db.get_support_thread(555)
assert [m["author"] for m in msgs] == ["user", "owner"], msgs
print("поддержка: ок")

# --- уведомления ---
from bot.services.notify import build_feed

db.add_notice("Новая сборка", "Починил календарь")
feed = build_feed(db, 555)
titles = [i["title"] for i in feed["items"]]
assert "Новая сборка" in titles, titles
assert feed["unread"] == len(feed["items"]), feed["unread"]
db.set_notif_seen_at(555)
feed2 = build_feed(db, 555)
assert feed2["unread"] == 0, [i["title"] for i in feed2["items"] if i["unread"]]
# запись с датой в будущем не должна гореть вечно
import bot.services.notify as nt
nt.CHANGELOG.insert(0, {"at": "2099-01-01T00:00:00+00:00", "title": "Из будущего", "body": ""})
db.set_notif_seen_at(555)
feed_f = build_feed(db, 555)
assert feed_f["unread"] == 0, [i["title"] for i in feed_f["items"] if i["unread"]]
nt.CHANGELOG.pop(0)
print("запись с датой в будущем не залипает: ок")
print("уведомления: ок, в ленте", len(feed["items"]), "записей")

# срок сертификата попадает в ленту
from datetime import datetime, timedelta, timezone
soon = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()
db.add_certificate(555, "SSCEC", "12/26", soon, "")
feed3 = build_feed(db, 555)
cert = [i for i in feed3["items"] if i["kind"] == "cert"]
assert cert and cert[0]["urgent"], cert
# рубеж «7 дней» пересечён только что -> напоминание новое даже после
# того, как колокольчик уже открывали
assert cert[0]["unread"] and feed3["unread"] >= 1, (cert[0], feed3["unread"])
print("срок сертификата в ленте:", cert[0]["title"], "|", cert[0]["body"])

# а вот далёкий срок новым быть не должен
far = (datetime.now(timezone.utc) + timedelta(days=45)).date().isoformat()
db.add_certificate(555, "Load Line", "7/26", far, "")
db.set_notif_seen_at(555)
feed4 = build_feed(db, 555)
ll = [i for i in feed4["items"] if "Load Line" in i["title"]]
assert ll and not ll[0]["unread"], ll
print("далёкий срок не мигает:", ll[0]["body"])

# после продления срок уходит из ленты
db.add_certificate(555, "SSCEC", "13/27",
                   (datetime.now(timezone.utc) + timedelta(days=400)).date().isoformat(), "")
feed5 = build_feed(db, 555)
sscec = [i for i in feed5["items"] if "SSCEC" in i["title"]]
assert len(sscec) == 1, sscec  # старый ещё в базе, новый уже вне порога
print("после продления в ленте остаётся:", len(sscec))

print("\nВСЕ ПРОВЕРКИ ПРОШЛИ")
