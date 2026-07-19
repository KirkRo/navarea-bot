from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..services.claude_qa import ClaudeQA
from ..services.db import Database


async def cmd_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user_id = update.effective_user.id
    areas = db.get_user_areas(user_id)

    if not areas:
        await update.message.reply_text("Сначала выбери районы -- /areas")
        return

    any_sent = False
    for area in areas:
        rows = db.active_warnings(area, limit=10)
        if not rows:
            continue
        any_sent = True
        lines = [f"NAVAREA {area}, действующие ({len(rows)}):\n"]
        for r in rows:
            num = r["msg_number"] or "—"
            region = r["region"] or ""
            preview = r["raw_text"][:200].replace("\n", " ")
            lines.append(f"№{num} {region}\n{preview}…\n")
        text = "\n".join(lines)
        for i in range(0, len(text), 3500):
            await update.message.reply_text(text[i:i + 3500])

    if not any_sent:
        await update.message.reply_text(
            "Пока нет сохранённых предупреждений по твоим районам -- "
            "бот ещё не успел опросить источники или в этих районах сейчас пусто."
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
