"""
Вся конфигурация бота берётся из переменных окружения (файл .env).
Смотри .env.example для полного списка с комментариями.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int_list(name: str, default: list[int]) -> list[int]:
    val = os.getenv(name)
    if not val:
        return default
    return [int(x.strip()) for x in val.split(",") if x.strip()]


@dataclass
class Config:
    # --- Telegram ---
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    owner_ids: list[int] = field(default_factory=lambda: _get_int_list("OWNER_IDS", []))

    # --- Anthropic (Claude Q&A) ---
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001"))
    claude_max_tokens: int = field(default_factory=lambda: _get_int("CLAUDE_MAX_TOKENS", 700))

    # --- База данных ---
    # Если задан DATABASE_URL -- используется Postgres (Neon и т.п, вариант хостинга Render).
    # Если пусто -- локальный SQLite по пути DB_PATH (вариант хостинга Oracle Cloud).
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "data/navarea.db"))

    # --- Веб-сервер для проверки "жив ли процесс" (нужен только на Render,
    # чтобы бесплатный Web Service не считал бота неактивным и не усыплял).
    # На Oracle просто не используется.
    port: int = field(default_factory=lambda: _get_int("PORT", 8080))

    # --- Публичный адрес бота, чтобы строить ссылки на карту предупреждений.
    # Приоритет: свой PUBLIC_URL, если задан -> RENDER_EXTERNAL_URL, который
    # Render проставляет сам для веб-сервисов -> пусто (тогда бот даёт ссылку
    # на Google Maps без своей страницы карты, актуально для Oracle без домена).
    public_url: str = field(
        default_factory=lambda: (os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip()
    )

    # --- Опрос источников NAVAREA ---
    poll_interval_minutes: int = field(default_factory=lambda: _get_int("POLL_INTERVAL_MINUTES", 30))

    # --- Тарифы ---
    free_areas_limit: int = field(default_factory=lambda: _get_int("FREE_AREAS_LIMIT", 2))
    free_qa_daily_limit: int = field(default_factory=lambda: _get_int("FREE_QA_DAILY_LIMIT", 5))
    premium_areas_limit: int = field(default_factory=lambda: _get_int("PREMIUM_AREAS_LIMIT", 10))

    # --- Подписка через Telegram Stars ---
    stars_price_monthly: int = field(default_factory=lambda: _get_int("STARS_PRICE_MONTHLY", 150))

    # --- Sealagom (платный агрегатор всех 21 района NAVAREA, $20/мес) ---
    # Если задан -- используется вместо собственных скрейперов (NGA/UKHO/Peru/Spain)
    # сразу для всех районов. Если пусто -- работают только свои источники.
    sealagom_api_token: str = field(default_factory=lambda: os.getenv("SEALAGOM_API_TOKEN", "").strip())

    def __post_init__(self) -> None:
        if self.public_url and not self.public_url.startswith(("http://", "https://")):
            self.public_url = f"https://{self.public_url}"
        self.public_url = self.public_url.rstrip("/")

    def validate(self) -> list[str]:
        """Возвращает список проблем конфигурации (пусто = всё ок)."""
        problems = []
        if not self.bot_token:
            problems.append("BOT_TOKEN не задан в .env")
        if not self.anthropic_api_key:
            problems.append("ANTHROPIC_API_KEY не задан в .env (Q&A ассистент работать не будет)")
        if not self.owner_ids:
            problems.append("OWNER_IDS не задан в .env (админ-команды будут недоступны никому)")
        return problems


config = Config()