from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..config import config
from ..scheduler import format_warning_message
from ..services.claude_qa import ClaudeQA
from ..services.db import Database

# сколько предупреждений показывать в чате, прежде чем предложить Mini App
CHAT_LIMIT = 10


async def cmd_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает действующие предупреждения прямо в чате.
    Mini App (карта, поиск, фильтры, статистика) живёт на постоянной кнопке
    слева от поля ввода -- см. setup_menu_button в bot/main.py."""
    db: Database = context.bot_data["db"]
    user_id = update.effective_user.id
    areas = db.get_user_areas(user_id)

    if not areas:
        await update.message.reply_text("Сначала выбери районы -- /areas")
        return

    any_sent = False
    truncated = False
    for area in areas:
        rows = db.active_warnings(area, limit=CHAT_LIMIT + 1)
        if not rows:
            continue
        any_sent = True

        shown = rows[:CHAT_LIMIT]
        if len(rows) > CHAT_LIMIT:
            truncated = True

        await update.message.reply_text(f"NAVAREA {area}, действующие ({len(shown)}):")
        for row in shown:
            text = format_warning_message(area, row, is_new=False)
            await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

    if not any_sent:
        await update.message.reply_text(
            "Пока нет сохранённых предупреждений по твоим районам -- "
            "бот ещё не успел опросить источники или в этих районах сейчас пусто."
        )
        return

    if truncated and config.public_url:
        await update.message.reply_text(
            "Показал только последние. Все предупреждения, карта и поиск -- "
            "в приложении по кнопке «Открыть» слева от поля ввода."
        )


async def cmd_explain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    qa: ClaudeQA = context.bot_data["qa"]

    source_text = None
    if update.message.reply_to_message and update.message.reply_to_message.text:
        source_text = update.message.reply_to_message.text
    elif context.args:
        source_text = " ".join(context.args)

    if not source_text:
        await update.message.reply_text(
            "Ответь командой /explain на сообщение с текстом предупреждения, "
            "или напиши /explain <текст предупреждения>."
        )
        return

    await update.message.chat.send_action("typing")
    answer = await qa.explain_warning(source_text)
    await update.message.reply_text(answer)
