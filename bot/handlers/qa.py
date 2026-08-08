from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..config import config
from ..services.access import is_effectively_premium
from ..services.claude_qa import ClaudeQA
from ..services.db import Database


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    qa: ClaudeQA = context.bot_data["qa"]
    user_id = update.effective_user.id
    question = update.message.text

    is_premium = is_effectively_premium(db, user_id)
    if not is_premium:
        allowed = db.try_consume_qa_quota(user_id, config.free_qa_daily_limit)
        if not allowed:
            await update.message.reply_text(
                f"На бесплатном тарифе лимит {config.free_qa_daily_limit} вопросов в день исчерпан. "
                f"Возвращайся завтра или оформи /subscribe для безлимита."
            )
            return

    await update.message.chat.send_action("typing")
    # В чате отвечает тот же ассистент, что и в приложении: с инструментами,
    # чтобы «какая погода на переходе Констанца -- Сантос» отрабатывало
    # цифрами, а не общими словами. Позиции с устройства здесь нет -- в чате
    # её взять неоткуда, -- зато карточка судна доступна по user_id.
    ctx = {"db": db, "user_id": user_id}
    try:
        answer = await qa.ask_agent(question, ctx)
    except Exception:
        await update.message.reply_text(
            "Не получилось получить ответ от Claude (проблема с API). Попробуй ещё раз чуть позже."
        )
        raise
    await update.message.reply_text(answer)
