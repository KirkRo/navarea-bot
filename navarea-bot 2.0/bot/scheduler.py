"""
Периодическая задача (запускается через JobQueue из python-telegram-bot).
Для каждого района, на который хоть кто-то подписан и для которого есть
рабочий источник (SOURCES из registry.py): скачать, распарсить, сохранить
новые сообщения, разослать подписчикам, отметить отменённые.
"""
from __future__ import annotations

import logging

from telegram.ext import ContextTypes

from .services.db import Database
from .services.sources.nga import normalize_msgnum
from .services.sources.registry import SOURCES

logger = logging.getLogger(__name__)

MAX_TEXT_LEN = 3500  # запас от лимита Telegram в 4096 символов


async def poll_sources_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]

    areas_in_use = set()
    for area in SOURCES:
        if db.users_subscribed_to(area):
            areas_in_use.add(area)

    for area_code in areas_in_use:
        source = SOURCES[area_code]
        try:
            raw = await source.fetch_raw(area_code)
            parsed = source.parse(area_code, raw)
        except Exception:
            logger.exception("Не удалось опросить источник %s для района %s", source.source_id, area_code)
            continue

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

        if not new_ids:
            continue

        subscribers = db.users_subscribed_to(area_code)
        for wid in new_ids:
            row = db.get_warning(wid)
            if not row:
                continue
            text = _format_notification(area_code, row)
            for user_id in subscribers:
                if db.already_notified(user_id, wid):
                    continue
                try:
                    await context.bot.send_message(user_id, text[:MAX_TEXT_LEN])
                    db.mark_notified(user_id, wid)
                except Exception:
                    logger.exception("Не удалось отправить уведомление пользователю %s", user_id)


def _format_notification(area_code: str, row) -> str:
    num = row["msg_number"] or "—"
    region = row["region"] or ""
    header = f"🆕 NAVAREA {area_code} №{num}"
    if region:
        header += f" — {region}"
    return f"{header}\n\n{row['raw_text']}"
