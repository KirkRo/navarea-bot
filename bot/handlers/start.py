from __future__ import annotations

from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from ..config import config
from ..services.db import Database

WELCOME = """Привет! Это бот-монитор навигационных предупреждений (NAVAREA/NAVTEX) для моряков.

Что умеет:
• следить за выбранными районами NAVAREA и присылать новые предупреждения
• показывать список действующих предупреждений по команде
• отвечать на вопросы по судовождению (спроси что угодно текстом)
• разбирать текст конкретного предупреждения простым языком

Важно: бот берёт данные с открытых сайтов официальных координаторов NAVAREA \
(NGA, UKHO и так далее) и не заменяет получение MSI через штатное оборудование \
GMDSS/NAVTEX на судне. Это вспомогательный инструмент, а не источник для \
официального подтверждения безопасности перехода.

С чего начать -- /areas, чтобы выбрать районы."""

HELP = """Команды:

/areas -- выбрать районы NAVAREA для отслеживания
/sources -- официальный источник по каждому из 21 района NAVAREA
/active -- действующие предупреждения по твоим районам
/status -- тариф, районы, лимиты
/subscribe -- оформить Premium
/cancel_subscription -- отключить автопродление Premium

Просто напиши текстом вопрос по судовождению, погоде, MSI и так далее -- отвечу через Claude."""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    await update.message.reply_text(WELCOME)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user_id = update.effective_user.id
    areas = db.get_user_areas(user_id)
    is_premium = db.is_premium_active(user_id)
    user = db.get_user(user_id)

    lines = [f"Тариф: {'Premium ⭐' if is_premium else 'Бесплатный'}"]
    if is_premium and user and user.premium_until:
        until = datetime.fromisoformat(user.premium_until)
        lines.append(f"Действует до {until.strftime('%d.%m.%Y')}")

    limit = config.premium_areas_limit if is_premium else config.free_areas_limit
    lines.append(f"Районы ({len(areas)}/{limit}): {', '.join(areas) if areas else '—'}")

    if not is_premium:
        today = datetime.now(timezone.utc).date().isoformat()
        used = user.qa_count_today if user and user.qa_count_date == today else 0
        lines.append(f"Вопросы Claude сегодня: {used}/{config.free_qa_daily_limit}")
    else:
        lines.append("Вопросы Claude: без лимита")

    await update.message.reply_text("\n".join(lines))
