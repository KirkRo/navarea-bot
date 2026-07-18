from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..config import config
from ..services.claude_qa import ClaudeQA
from ..services.db import Database


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    qa: ClaudeQA = context.bot_data["qa"]
    user_id = update.effective_user.id
    question = update.message.text

    is_premium = db.is_premium_active(user_id)
    if not is_premium:
        allowed = db.try_consume_qa_quota(user_id, config.free_qa_daily_limit)
        if not allowed:
            await update.message.reply_text(
                f"На бесплатном тарифе лимит {config.free_qa_daily_limit} вопросов в день исчерпан. "
                f"Возвращайся завтра или оформи /subscribe для безлимита."
            )
            return

    await update.message.chat.send_action("typing")
    try:
        answer = await qa.ask(question)
    except Exception:
        await update.message.reply_text(
            "Не получилось получить ответ от Claude (проблема с API). Попробуй ещё раз чуть позже."
        )
        raise
    await update.message.reply_text(answer)
