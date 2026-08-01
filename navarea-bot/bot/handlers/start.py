from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from ..config import config
from ..services.access import is_effectively_premium, is_owner
from ..services.db import Database

logger = logging.getLogger(__name__)

WELCOME = """⚓️ <b>Watchkeeper</b> — инструменты вахтенного помощника.

<b>Предупреждения</b>
Слежу за районами NAVAREA и береговыми предупреждениями, присылаю новые сразу, показываю район на карте контуром, а не точкой.

<b>Расчёты мостика</b>
Расстояние и курс, ETA, запас воды под килём, проседание, CPA/TCPA, точка перекладки руля, якорная стоянка, дифферент, восход и сумерки. Работают без связи — в рейсе это важно.

<b>Радио</b>
Станции MF/HF DSC для теста, с отметкой, от каких реально приходит подтверждение.

<b>Переход</b>
Вводишь порты — показываю, какие предупреждения попадают в коридор вдоль маршрута и на каком расстоянии от курса.

Всё это удобнее в приложении — кнопка слева от поля ввода или /app.

Важно: данные справочные. Официальный источник — штатное оборудование GMDSS/NAVTEX, ECDIS и судовые пособия. Решение принимает судоводитель."""

HELP = """<b>Watchkeeper</b> — что умеет:

<b>Приложение</b>
/app — открыть целиком: карта, расчёты, радио, переход
/tools — сразу к расчётам мостика
/radio — станции MF/HF DSC для теста
/voyage — проверить маршрут между портами
/chart — карта предупреждений

<b>Предупреждения</b>
/areas — выбрать районы для отслеживания
/active — что действует сейчас
/sources — откуда берутся данные по каждому району
/explain — разобрать текст предупреждения простым языком

<b>Прочее</b>
/status — тариф, районы, лимиты
/subscribe — оформить Premium
/cancel_subscription — отключить автопродление

Можно просто написать вопрос текстом — отвечу по судовождению, погоде, формальностям."""

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    # Кнопка Mini App ставится и глобально при запуске бота (см. setup_menu_button
    # в main.py), но Telegram не всегда обновляет её в уже открытых чатах. Здесь
    # ставим её адресно для этого чата -- так она появляется гарантированно.
    if config.public_url:
        try:
            from telegram import MenuButtonWebApp, WebAppInfo

            await context.bot.set_chat_menu_button(
                chat_id=update.effective_chat.id,
                menu_button=MenuButtonWebApp(
                    text="Открыть",
                    web_app=WebAppInfo(url=f"{config.public_url}/app"),
                ),
            )
        except Exception:
            logger.exception("Не удалось поставить кнопку Mini App для чата %s", update.effective_chat.id)

    await update.message.reply_text(WELCOME, parse_mode="HTML")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP, parse_mode="HTML")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user_id = update.effective_user.id
    areas = db.get_user_areas(user_id)
    is_premium = is_effectively_premium(db, user_id)
    user = db.get_user(user_id)

    if is_owner(user_id):
        lines = ["Тариф: Premium ⭐ (доступ владельца бота, без подписки)"]
    else:
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


async def cmd_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запасной способ открыть Mini App -- кнопкой в сообщении. Основной
    путь -- постоянная кнопка слева от поля ввода (см. setup_menu_button)."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    if not config.public_url:
        await update.message.reply_text(
            "Mini App пока недоступен: у бота нет публичного адреса. "
            "На Render он подставляется сам, на своём сервере нужно задать PUBLIC_URL в .env."
        )
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🛰 Открыть NAVAREA Monitor", web_app=WebAppInfo(url=f"{config.public_url}/app"))
    ]])
    await update.message.reply_text(
        "Панель, карта, поиск и планирование перехода:",
        reply_markup=keyboard,
    )


# Команды, открывающие приложение сразу на нужной вкладке. Вкладка
# передаётся через якорь в адресе (#tools и так далее), приложение читает
# его при запуске -- см. miniapp.py.
_APP_TABS = {
    "tools": ("Расчёты мостика", "Расстояние и курс, UKC, проседание, CPA/TCPA, якорь, дифферент и остальное. Работает без связи."),
    "radio": ("Станции MF/HF DSC", "Кому слать тест и от кого реально придёт подтверждение."),
    "voy": ("Проверка перехода", "Какие предупреждения попадают в коридор вдоль маршрута."),
    "map": ("Карта предупреждений", "Все действующие районы контурами, с подложками и слоями."),
}


async def _open_tab(update: Update, context: ContextTypes.DEFAULT_TYPE, tab: str) -> None:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    title, desc = _APP_TABS[tab]
    if not config.public_url:
        await update.message.reply_text(
            "Приложение пока недоступно: у бота нет публичного адреса. "
            "На Render он подставляется сам, на своём сервере нужно задать PUBLIC_URL в .env."
        )
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"Открыть · {title}",
                             web_app=WebAppInfo(url=f"{config.public_url}/app#{tab}"))
    ]])
    await update.message.reply_text(f"<b>{title}</b>\n{desc}", parse_mode="HTML", reply_markup=keyboard)


async def cmd_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _open_tab(update, context, "tools")


async def cmd_radio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _open_tab(update, context, "radio")


async def cmd_voyage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _open_tab(update, context, "voy")


async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _open_tab(update, context, "map")
