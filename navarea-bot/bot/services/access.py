"""
Владелец бота (числовые id из OWNER_IDS в .env) всегда получает Premium
без реального платежа через Stars -- это доступ разработчика, а не
подписка. Обычные пользователи по-прежнему проверяются через настоящую
оплату (db.is_premium_active).

Telegram отдаёт боту числовой user_id на каждое сообщение, а не username --
username может меняться и не подходит для надёжной проверки "это тот самый
человек или нет". Поэтому доступ владельца привязан к OWNER_IDS (шаг 2
гайда), а не к @kirk_ro напрямую.
"""
from __future__ import annotations

from ..config import config


def is_owner(user_id: int) -> bool:
    return user_id in config.owner_ids


def is_effectively_premium(db, user_id: int) -> bool:
    return is_owner(user_id) or db.is_premium_active(user_id)
