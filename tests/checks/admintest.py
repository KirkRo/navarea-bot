# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
"""
Панель владельца и управление подпиской.

Сети здесь нет: Bot API подменяется заглушкой той же формы, что настоящие
ответы Telegram (ok/result/description). Проверяется именно наша логика --
кому что видно, что записывается в базу и что уходит в Telegram.
"""
import hashlib, hmac, json, pathlib, sys, tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

sys.path.insert(0, sys.argv[1])
from bot.config import config
from bot.services.db import Database

OWNER, BUYER, GUEST = 777, 555, 999
TOKEN = "111:TEST-TOKEN"

tmp = pathlib.Path(tempfile.mkdtemp()) / "t.db"
db = Database(str(tmp))
db.upsert_user(OWNER, "kirk", "Кирк")
db.upsert_user(BUYER, "sailor", "Матрос")
db.upsert_user(GUEST, None, "Гость")

# ---------------------------------------------------------------- база --- #

# Выдача бонусных дней тому, у кого подписка ещё идёт, не должна её укорачивать.
far = (datetime.now(timezone.utc) + timedelta(days=40)).isoformat()
db.set_premium(BUYER, far, source="stars")
until = db.grant_premium(BUYER, 10)
assert datetime.fromisoformat(until) > datetime.fromisoformat(far), (until, far)
assert db.get_user(BUYER).premium_source == "granted"
print("выдача поверх оплаченного срока продлевает, а не укорачивает:", until[:10])

# Отмена автопродления помнится у нас: Telegram состояние подписки не отдаёт.
db.set_sub_cancelled(BUYER, True)
assert db.get_user(BUYER).sub_cancelled is True
# ...и новая оплата снимает пометку, иначе переключатель врал бы после оплаты
db.set_premium(BUYER, far, source="stars")
assert db.get_user(BUYER).sub_cancelled is False
print("отмена помнится, новая оплата её снимает: ок")

db.log_payment(BUYER, "chg_1", 100, is_recurring=False)
db.log_payment(BUYER, "chg_2", 100, is_recurring=True)
db.log_payment(GUEST, "chg_3", 250, is_recurring=False)
db.mark_payment_refunded("chg_3")

s = db.payments_summary()
assert s["payments"] == 3 and s["stars_total"] == 450, s
assert s["refunds"] == 1 and s["refunded_stars"] == 250, s
assert s["stars_net"] == 200, s
print("сводка по платежам:", s["stars_total"], "получено,", s["refunded_stars"], "возвращено")

# Возвращённый платёж не должен считаться оплатой пользователя.
row = [u for u in db.admin_users(q=str(GUEST))][0]
assert row["paid_stars"] == 0, row
assert [u for u in db.admin_users(q="sailor")][0]["paid_stars"] == 200

db.touch_user(BUYER)
assert [u["user_id"] for u in db.admin_users(only="active")] == [BUYER]
paid_ids = [u["user_id"] for u in db.admin_users(only="paid")]
assert paid_ids == [BUYER], paid_ids
summary = db.admin_summary()
assert summary["users"] == 3 and summary["premium"] == 1, summary
assert summary["active_week"] == 1 and summary["granted"] == 0, summary
print("списки и фильтры: всего", summary["users"], "| платных", summary["premium"],
      "| активных за неделю", summary["active_week"])

# ----------------------------------------------------------------- API --- #

from bot import webapp

webapp._state["db"] = db
webapp._state["bot_token"] = TOKEN
config.owner_ids = [OWNER]

CALLS = []


def fake_bot_api(method: str, payload: dict | None = None) -> dict:
    """Ответы той же формы, что у настоящего Telegram."""
    CALLS.append((method, payload or {}))
    if method == "getMyStarBalance":
        return {"ok": True, "result": {"amount": 340, "nanostar_amount": 0}}
    if method in ("refundStarPayment", "editUserStarSubscription", "sendMessage"):
        return {"ok": True, "result": True}
    return {"ok": False, "description": "неизвестный метод " + method}


webapp._call_bot_api = fake_bot_api


def init_data(user_id: int) -> str:
    """Настоящая подпись Telegram Mini App -- ту же проверяет сервер."""
    pairs = {"auth_date": "1000000000",
             "user": json.dumps({"id": user_id, "first_name": "T"}, separators=(",", ":"))}
    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    sig = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return "&".join([f"{k}={quote(v, safe='')}" for k, v in pairs.items()] + [f"hash={sig}"])


def q(who: int, **kw) -> dict:
    """Запрос от имени пользователя. Имя параметра не user_id специально:
    именно так называется поле в самих запросах панели."""
    query = {"initData": [init_data(who)]}
    for k, v in kw.items():
        query[k] = [str(v)]
    return query


# Чужой в панель не попадает, даже зная адрес: user_id берётся из подписи.
assert webapp._api_admin(q(BUYER)) == {"error": "forbidden"}
assert webapp._api_admin({}) == {"error": "forbidden"}
print("панель закрыта для всех, кроме владельца: ок")

overview = webapp._api_admin(q(OWNER))
assert overview["balance"]["stars"] == 340, overview["balance"]
assert overview["summary"]["users"] == 3
assert overview["withdraw"]["min"] == 1000 and overview["withdraw"]["hold_days"] == 21
assert len(overview["payments"]) == 3
# Владелец в списке помечается отдельно: его доступ из OWNER_IDS, а не из
# базы, и без пометки он выглядел бы как бесплатный тариф.
by_id = {u["user_id"]: u for u in overview["users"]}
assert by_id[OWNER]["owner"] is True and by_id[BUYER]["owner"] is False, overview["users"]
print("сводка владельцу: баланс", overview["balance"]["stars"], "⭐, платежей",
      len(overview["payments"]))

# Баланс не пришёл -- панель должна открыться и без него.
webapp._call_bot_api = lambda m, p=None: {"ok": False, "description": "Unauthorized"}
assert "error" in webapp._api_admin(q(OWNER))["balance"]
webapp._call_bot_api = fake_bot_api
print("панель открывается и когда Telegram не отдал баланс: ок")

granted = webapp._api_admin(q(OWNER, action="grant", user_id=GUEST, days=30))
assert granted["done"] == "grant"
assert db.get_user(GUEST).premium_source == "granted"
assert db.is_premium_active(GUEST)
assert any(c[0] == "sendMessage" for c in CALLS), "человеку не сообщили о выдаче"
print("выдача без оплаты:", granted["until"][:10])

webapp._api_admin(q(OWNER, action="revoke", user_id=GUEST))
assert not db.is_premium_active(GUEST)
print("снятие Premium: ок")

CALLS.clear()
refund = webapp._api_admin(q(OWNER, action="refund", user_id=BUYER, charge_id="chg_2"))
assert refund["done"] == "refund", refund
assert ("refundStarPayment", {"user_id": BUYER, "telegram_payment_charge_id": "chg_2"}) in CALLS
assert db.payment_by_charge("chg_2")["refunded_at"], "платёж не помечен возвращённым"
assert not db.is_premium_active(BUYER), "после возврата Premium должен сниматься"
print("возврат звёзд: помечен в базе, доступ снят")

# Возврат без номера операции вызывать нечем.
assert webapp._api_admin(q(OWNER, action="refund", user_id=BUYER))["error"] == "bad_args"

# ---------------------------------------------------- подписка в приложении --- #

db.set_premium(BUYER, far, source="stars")
st = webapp._api_subscription(q(BUYER))
assert st["autorenew"] is True and st["can_manage"] is True, st

CALLS.clear()
off = webapp._api_subscription(q(BUYER, action="cancel"))
assert off["autorenew"] is False and off["done"] == "cancel", off
method, payload = CALLS[0]
assert method == "editUserStarSubscription" and payload["is_canceled"] is True, CALLS
assert db.get_user(BUYER).sub_cancelled is True
print("отмена автопродления из приложения: ок")

on = webapp._api_subscription(q(BUYER, action="resume"))
assert on["autorenew"] is True and CALLS[-1][1]["is_canceled"] is False, CALLS
assert db.get_user(BUYER).sub_cancelled is False
print("возврат автопродления: ок")

# Telegram отказал -- состояние в базе меняться не должно, иначе переключатель
# показывал бы отключённое автопродление при живой подписке.
webapp._call_bot_api = lambda m, p=None: {"ok": False, "description": "CHARGE_NOT_FOUND"}
bad = webapp._api_subscription(q(BUYER, action="cancel"))
assert bad["error"] == "telegram_error" and bad["autorenew"] is True, bad
assert db.get_user(BUYER).sub_cancelled is False
webapp._call_bot_api = fake_bot_api
print("отказ Telegram не ломает состояние подписки: ок")

# Выданному вручную управлять нечем: платежа у Telegram нет.
db.grant_premium(GUEST, 30)
gst = webapp._api_subscription(q(GUEST))
assert gst["can_manage"] is False and gst["autorenew"] is False, gst
assert webapp._api_subscription(q(GUEST, action="cancel"))["error"] == "no_payment"
print("выданный вручную Premium не предлагает отмену: ок")

# ------------------------------------------------------------- доступ --- #

config.paywall_enabled = True
acc_owner = webapp._api_access(q(OWNER))
assert acc_owner["owner"] is True, acc_owner
acc_buyer = webapp._api_access(q(BUYER))
assert acc_buyer["owner"] is False and acc_buyer["can_manage_sub"] is True, acc_buyer
config.paywall_enabled = False
# при выключенных тарифах владелец тоже должен видеть панель
assert webapp._api_access(q(OWNER))["owner"] is True
assert webapp._api_access(q(BUYER))["owner"] is False
print("признак владельца в /api/access: ок при любых тарифах")

print("\nВСЕ ПРОВЕРКИ ПРОШЛИ")
