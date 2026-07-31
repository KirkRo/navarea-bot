"""
Периодическая задача (запускается через JobQueue из python-telegram-bot).
Для каждого района, на который хоть кто-то подписан и для которого есть
рабочий источник (SOURCES из registry.py): скачать, распарсить, сохранить
новые сообщения, разослать подписчикам, отметить отменённые.

fetch_and_store_area вынесена отдельно, чтобы её же можно было вызвать
сразу в момент подписки на район (bot/handlers/areas.py) -- не дожидаясь
следующего планового цикла.

Если источник падает, владельцу (OWNER_IDS) прилетает сообщение в
Telegram с точным текстом ошибки -- не нужно лезть в логи хостинга,
чтобы узнать что именно сломалось. Чтобы не заспамить при длительном
падении источника, повторный алерт по тому же району шлётся не чаще
раза в ALERT_COOLDOWN_SECONDS.
"""
from __future__ import annotations

import asyncio
import html as html_lib
import logging
import time

from telegram.ext import ContextTypes

from .config import config
from .services.geo import extract_coordinates, google_maps_url
from .services.sources.nga import normalize_msgnum
from .services.sources.registry import SOURCES
from .webapp import build_map_url, invalidate_stats_cache

logger = logging.getLogger(__name__)

MAX_TEXT_LEN = 3800  # запас от лимита Telegram в 4096 символов
ALERT_COOLDOWN_SECONDS = 6 * 3600  # не чаще раза в 6 часов на один и тот же район

_last_alert_at: dict[str, float] = {}


async def fetch_and_store_area(db, area_code: str) -> tuple[list[int], str | None]:
    """Скачивает источник района, сохраняет новые сообщения в БД (с дедупликацией
    по тексту) и отмечает отменённые. Возвращает (id новых записей, текст ошибки или None).

    Если запрос падает, делаем одну повторную попытку через паузу -- на случай
    короткого сетевого сбоя, а не постоянной проблемы с источником."""
    source = SOURCES.get(area_code)
    if source is None:
        return [], None

    raw = None
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw = await source.fetch_raw(area_code)
            last_error = None
            break
        except Exception as e:
            last_error = e
            if attempt == 0:
                await asyncio.sleep(5)

    if last_error is not None:
        error_text = f"{type(last_error).__name__}: {last_error}"
        logger.exception("Не удалось опросить источник %s для района %s (%s)", source.source_id, area_code, error_text, exc_info=last_error)
        return [], error_text

    try:
        parsed = source.parse(area_code, raw)
    except Exception as e:
        error_text = f"{type(e).__name__}: {e}"
        logger.exception("Не удалось разобрать ответ источника %s для района %s (%s)", source.source_id, area_code, error_text)
        return [], error_text

    logger.info("Источник %s для района %s: разобрано %d сообщений в сыром ответе (%d байт)",
                source.source_id, area_code, len(parsed), len(raw or ""))

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
            shapes=getattr(warning, "shapes", None),
        )
        if wid:
            new_ids.append(wid)
        for cancelled_num in warning.cancels:
            normalized = normalize_msgnum(cancelled_num) or cancelled_num
            db.mark_cancelled(area_code, normalized)

    logger.info("Источник %s для района %s: %d новых записей сохранено", source.source_id, area_code, len(new_ids))
    if new_ids:
        invalidate_stats_cache()  # чтобы Mini App сразу показал свежие цифры
    return new_ids, None


async def _alert_owner_if_due(context: ContextTypes.DEFAULT_TYPE, area_code: str, error_text: str) -> None:
    now = time.time()
    last = _last_alert_at.get(area_code, 0)
    if now - last < ALERT_COOLDOWN_SECONDS:
        return
    _last_alert_at[area_code] = now

    text = (
        f"⚠️ Источник NAVAREA {area_code} не отвечает.\n\n"
        f"{error_text}\n\n"
        f"Если это повторяется -- возможно сайт-источник поменял формат или "
        f"блокирует запросы с сервера. Смотри bot/services/sources/ для этого района."
    )
    for owner_id in config.owner_ids:
        try:
            await context.bot.send_message(owner_id, text)
        except Exception:
            logger.exception("Не удалось отправить алерт владельцу %s", owner_id)


async def poll_sources_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.bot_data["db"]

    areas_in_use = set()
    for area in SOURCES:
        if db.users_subscribed_to(area):
            areas_in_use.add(area)

    for area_code in areas_in_use:
        new_ids, error = await fetch_and_store_area(db, area_code)
        if error:
            await _alert_owner_if_due(context, area_code, error)
            continue
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
                    await context.bot.send_message(user_id, text, parse_mode="HTML", disable_web_page_preview=True)
                    db.mark_notified(user_id, wid)
                except Exception:
                    logger.exception("Не удалось отправить уведомление пользователю %s", user_id)


def format_warning_message(area_code: str, row, is_new: bool = True) -> str:
    """HTML-разметка для Telegram (parse_mode="HTML"). Координаты из текста,
    если находятся, превращаются в ссылку на карту (свою, если задан
    PUBLIC_URL, иначе на Google Maps по центру области)."""
    num = row["msg_number"] or "—"
    region = row["region"] or ""
    icon = "🆕" if is_new else "📋"

    header = f"{icon} <b>NAVAREA {html_lib.escape(area_code)} №{html_lib.escape(num)}</b>"
    if region:
        header += f"\n📍 <i>{html_lib.escape(region)}</i>"

    footer = ""
    coords = extract_coordinates(row["raw_text"])
    if coords:
        title = f"NAVAREA {area_code} №{num}"
        map_url = (
            build_map_url(config.public_url, coords, title, region)
            if config.public_url
            else google_maps_url(coords)
        )
        label = "Показать на карте" if len(coords) == 1 else f"Показать область на карте ({len(coords)} точ.)"
        footer = f'\n\n🗺 <a href="{html_lib.escape(map_url, quote=True)}">{label}</a>'

    fixed_len = len(header) + 2 + len(footer)
    budget = max(MAX_TEXT_LEN - fixed_len, 200)
    body_raw = row["raw_text"]
    if len(body_raw) > budget:
        body_raw = body_raw[:budget].rsplit(" ", 1)[0] + "…"
    body = html_lib.escape(body_raw)

    return f"{header}\n\n{body}{footer}"
