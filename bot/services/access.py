"""
Кто что может: бесплатный тариф, пробный период, Premium, владелец.

Пробный период считается от даты первого /start (поля created_at в users)
и длится TRIAL_DAYS дней. Отдельного флага в базе нет специально: так его
нельзя обнулить и получить второй пробный, просто удалив что-нибудь.

Что закрыто платно, а что нет -- решается в PAID_FEATURES ниже. Принцип,
которого я держался: расчёты, от которых зависит безопасность (запас под
килём, проседание, расхождение с целью, точка перекладки), остаются
бесплатными навсегда -- брать за них деньги неправильно. Платно то, что
экономит время и ведёт учёт: неограниченные районы, проверка маршрута,
карточка судна, чек-листы, сертификаты, история и безлимит вопросов.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..config import config

# Длительность пробного берётся из .env (TRIAL_DAYS). Ноль -- пробного нет:
# платные разделы закрыты сразу, и человеку сразу видна кнопка оплаты.
# Именно так проверяется настоящая покупка за звёзды.
TRIAL_DAYS = config.trial_days

# Что доступно только на Premium (и в пробном периоде)
PAID_FEATURES = {
    "unlimited_areas": "Неограниченное число районов NAVAREA",
    "coastal": "Береговые предупреждения",
    "voyage": "Проверка маршрута между портами",
    "vessel": "Карточка судна и подстановка в расчёты",
    "bridge": "Чек-листы и напоминания по сертификатам",
    "history": "История и статистика за 30 дней",
    "unlimited_ai": "Вопросы к ассистенту без дневного лимита",
    "advanced_calc": "Расчёты остойчивости, груза и ECDIS",
}


def is_owner(user_id: int) -> bool:
    return user_id in config.owner_ids


def _parse(dt) -> datetime | None:
    if not dt:
        return None
    try:
        d = datetime.fromisoformat(str(dt))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def trial_state(db, user_id: int) -> dict:
    """Сколько осталось от пробного периода."""
    if TRIAL_DAYS <= 0:
        return {"active": False, "days_left": 0, "ends": None, "disabled": True}

    user = db.get_user(user_id)
    started = _parse(getattr(user, "created_at", None)) if user else None
    if started is None:
        # пользователя ещё нет в базе -- считаем, что пробный только начинается
        return {"active": True, "days_left": TRIAL_DAYS, "ends": None}

    ends = started + timedelta(days=TRIAL_DAYS)
    now = datetime.now(timezone.utc)
    left = (ends - now).days + (1 if (ends - now).seconds else 0)
    return {"active": now < ends, "days_left": max(0, left), "ends": ends.isoformat()}


def access_state(db, user_id: int) -> dict:
    """Полная картина доступа для интерфейса и проверок."""
    if not config.paywall_enabled:
        # Режим отладки: тарифов нет, открыто всё и всем.
        return {"tier": "open", "premium": True, "trial": None,
                "title": "Открытый доступ", "features": list(PAID_FEATURES)}

    if is_owner(user_id):
        return {"tier": "owner", "premium": True, "trial": None,
                "title": "Доступ владельца", "features": list(PAID_FEATURES)}

    if db.is_premium_active(user_id):
        user = db.get_user(user_id)
        return {"tier": "premium", "premium": True, "trial": None,
                "until": getattr(user, "premium_until", None),
                "title": "Premium", "features": list(PAID_FEATURES)}

    t = trial_state(db, user_id)
    if t["active"]:
        return {"tier": "trial", "premium": True, "trial": t,
                "title": f"Пробный период, осталось {t['days_left']} дн.",
                "features": list(PAID_FEATURES)}

    return {"tier": "free", "premium": False, "trial": t,
            "title": "Бесплатный тариф", "features": []}


def is_effectively_premium(db, user_id: int) -> bool:
    """Владелец, оплативший или тот, у кого идёт пробный период."""
    return access_state(db, user_id)["premium"]


def can(db, user_id: int, feature: str) -> bool:
    """Доступна ли конкретная платная возможность."""
    if not config.paywall_enabled:
        return True
    if feature not in PAID_FEATURES:
        return True  # всё, чего нет в списке платного, доступно всем
    return is_effectively_premium(db, user_id)
