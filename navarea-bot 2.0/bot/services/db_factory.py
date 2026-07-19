"""
Если в .env задан DATABASE_URL -- используем Postgres (Neon и подобные,
вариант хостинга Render+Neon). Если нет -- обычный локальный SQLite-файл
(вариант хостинга Oracle Cloud, где диск постоянный и внешняя БД не нужна).

Обе реализации отдают один и тот же набор методов, так что весь
остальной код бота (хендлеры, планировщик) не знает и не должен знать,
какое хранилище используется на самом деле.
"""
from __future__ import annotations

from typing import Union

from .db import Database as SqliteDatabase
from .db_postgres import PostgresDatabase

AnyDatabase = Union[SqliteDatabase, PostgresDatabase]


def build_database(database_url: str, sqlite_path: str) -> AnyDatabase:
    if database_url:
        return PostgresDatabase(database_url)
    return SqliteDatabase(sqlite_path)
