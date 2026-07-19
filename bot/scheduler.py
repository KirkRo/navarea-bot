"""
Периодическая задача (запускается через JobQueue из python-telegram-bot).
Для каждого района, на который хоть кто-то подписан и для которого есть
рабочий источник (SOURCES из registry.py): скачать, распарсить, сохранить
новые сообщения, разослать подписчикам, отметить отменённые.

fetch_and_store_area вынесена отдельно, чтобы её же можно было вызвать
сразу в момент подписки на район (bot/handlers/areas.py) -- не дожидаясь
следующего планового цикла.
"""
from __future__ import annotations

import logging

from telegram.ext import ContextTypes

from .services.sources.nga import normalize_msgnum
from .services.sources.registry import SOURCES

logger = logging.getLogger(__name__)

MAX_TEXT_LEN = 3500  # запас от лимита Telegram в 4096 символов


async def fetch_and_store_area(db, area_code: str) -> list[int]:
    """Скачивает источник района, сохраняет новые сообщения в БД (с дедупликацией
    по тексту) и отмечает отменённые. Возвращает id только НОВЫХ записей."""
    source = SOURCES.get(area_code)
    if source is None:
        return []

    try:
        raw = await source.fetch_raw(area_code)
        parsed = source.parse(area_code, raw)
    except Exception:
        logger.exception("Не удалось опросить источник %s для района %s", source.source_id, area_code)
        return []

    new_ids: list[int] = []
    for warning in parsed:
        if db.warning_exists(warning.raw_text):
            continue
        wid = db.insert_warning(
            source=source.source_id,
            area_code=area_code,
            msg_number=warning.msg_number,
            category=warning.category,
            issued_at=warning.issued_at_raw,
            region=warning.region,
            raw_text=warning.raw_text,
        )
        if wid:
            new_ids.append(wid)
        for cancelled_num in warning.cancels:
            normalized = normalize_msgnum(cancelled_num) or cancelled_num
            db.mark_cancelled(area_code, normalized)

    return new_ids


async def poll_sources_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.bot_data["db"]

    areas_in_use = set()
    for area in SOURCES:
        if db.users_subscribed_to(area):
            areas_in_use.add(area)

    for area_code in areas_in_use:
        new_ids = await fetch_and_store_area(db, area_code)
        if not new_ids:
            continue

        subscribers = db.users_subscribed_to(area_code)
        for wid in new_ids:
            row = db.get_warning(wid)
            if not row:
                continue
            text = format_warning_message(area_code, row, is_new=True)
            for user_id in subscribers:
                if db.already_notified(user_id, wid):
                    continue
                try:
                    await context.bot.send_message(user_id, text[:MAX_TEXT_LEN])
                    db.mark_notified(user_id, wid)
                except Exception:
                    logger.exception("Не удалось отправить уведомление пользователю %s", user_id)


def format_warning_message(area_code: str, row, is_new: bool = True) -> str:
    num = row["msg_number"] or "—"
    region = row["region"] or ""
    icon = "🆕" if is_new else "📋"
    header = f"{icon} NAVAREA {area_code} №{num}"
    if region:
        header += f" — {region}"
    return f"{header}\n\n{row['raw_text']}"
