"""
Простой слой доступа к SQLite. Никакой ORM специально, чтобы было легко
понять и починить руками в рейсе при плохом интернете.

Каждый метод открывает короткое соединение и закрывает его сам, поэтому
класс безопасно использовать и из хендлеров, и из фоновой задачи планировщика.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    lang TEXT NOT NULL DEFAULT 'ru',
    created_at TEXT NOT NULL,
    is_premium INTEGER NOT NULL DEFAULT 0,
    premium_until TEXT,
    qa_count_today INTEGER NOT NULL DEFAULT 0,
    qa_count_date TEXT
);

CREATE TABLE IF NOT EXISTS area_subscriptions (
    user_id INTEGER NOT NULL,
    area_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, area_code)
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    area_code TEXT NOT NULL,
    msg_number TEXT,
    category TEXT,
    issued_at TEXT,
    region TEXT,
    raw_text TEXT NOT NULL,
    text_hash TEXT NOT NULL UNIQUE,
    first_seen_at TEXT NOT NULL,
    is_cancelled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sent_notifications (
    user_id INTEGER NOT NULL,
    warning_id INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (user_id, warning_id)
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    charge_id TEXT,
    stars_amount INTEGER,
    is_recurring INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


@dataclass
class User:
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    lang: str
    is_premium: bool
    premium_until: Optional[str]
    qa_count_today: int
    qa_count_date: Optional[str]


def _msgnum_sort_key(row) -> tuple[int, int]:
    """Сортируем по году и номеру предупреждения (не по времени, когда бот его нашёл) --
    иначе при первой подписке старые сообщения из архива могли попасть выше свежих."""
    msgnum = row["msg_number"] or ""
    m = re.match(r"(\d+)/(\d{2,4})", msgnum)
    if not m:
        return (0, 0)
    num, year = int(m.group(1)), m.group(2)
    year = int("20" + year) if len(year) == 2 else int(year)
    return (year, num)


class Database:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Пользователи
    # ------------------------------------------------------------------ #

    def upsert_user(self, user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, first_name, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name
                """,
                (user_id, username, first_name, _now()),
            )

    def get_user(self, user_id: int) -> Optional[User]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        return User(
            user_id=row["user_id"],
            username=row["username"],
            first_name=row["first_name"],
            lang=row["lang"],
            is_premium=bool(row["is_premium"]),
            premium_until=row["premium_until"],
            qa_count_today=row["qa_count_today"],
            qa_count_date=row["qa_count_date"],
        )

    def set_premium(self, user_id: int, until_iso: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?",
                (until_iso, user_id),
            )

    def revoke_premium(self, user_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?",
                (user_id,),
            )

    def is_premium_active(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user or not user.is_premium or not user.premium_until:
            return False
        try:
            until = datetime.fromisoformat(user.premium_until)
        except ValueError:
            return False
        return until > datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Лимит вопросов Claude в день (для бесплатного тарифа)
    # ------------------------------------------------------------------ #

    def try_consume_qa_quota(self, user_id: int, daily_limit: int) -> bool:
        """Возвращает True если вопрос разрешён (и списывает квоту)."""
        today = datetime.now(timezone.utc).date().isoformat()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT qa_count_today, qa_count_date FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                return False
            count = row["qa_count_today"] if row["qa_count_date"] == today else 0
            if count >= daily_limit:
                return False
            conn.execute(
                "UPDATE users SET qa_count_today = ?, qa_count_date = ? WHERE user_id = ?",
                (count + 1, today, user_id),
            )
            return True

    # ------------------------------------------------------------------ #
    # Подписки на районы NAVAREA
    # ------------------------------------------------------------------ #

    def get_user_areas(self, user_id: int) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT area_code FROM area_subscriptions WHERE user_id = ? ORDER BY area_code",
                (user_id,),
            ).fetchall()
        return [r["area_code"] for r in rows]

    def add_area(self, user_id: int, area_code: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO area_subscriptions (user_id, area_code, created_at) VALUES (?, ?, ?)",
                (user_id, area_code, _now()),
            )

    def remove_area(self, user_id: int, area_code: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM area_subscriptions WHERE user_id = ? AND area_code = ?",
                (user_id, area_code),
            )

    def users_subscribed_to(self, area_code: str) -> list[int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT user_id FROM area_subscriptions WHERE area_code = ?",
                (area_code,),
            ).fetchall()
        return [r["user_id"] for r in rows]

    # ------------------------------------------------------------------ #
    # Предупреждения NAVAREA
    # ------------------------------------------------------------------ #

    def warning_exists(self, raw_text: str) -> bool:
        h = text_hash(raw_text)
        with self._conn() as conn:
            row = conn.execute("SELECT 1 FROM warnings WHERE text_hash = ?", (h,)).fetchone()
        return row is not None

    def insert_warning(
        self,
        source: str,
        area_code: str,
        msg_number: Optional[str],
        category: Optional[str],
        issued_at: Optional[str],
        region: Optional[str],
        raw_text: str,
    ) -> Optional[int]:
        h = text_hash(raw_text)
        with self._conn() as conn:
            # Если у сообщения есть номер и для этого района уже есть запись с таким
            # же номером -- обновляем её, а не плодим дубль (актуально когда источник
            # переотдаёт тот же номер с чуть другим текстом, например после починки
            # парсера на нашей стороне).
            if msg_number:
                existing = conn.execute(
                    "SELECT id, text_hash FROM warnings WHERE area_code = ? AND msg_number = ?",
                    (area_code, msg_number),
                ).fetchone()
                if existing:
                    if existing["text_hash"] == h:
                        return None  # текст не поменялся, показывать как новое не нужно
                    conn.execute(
                        """
                        UPDATE warnings
                        SET source = ?, category = ?, issued_at = ?, region = ?,
                            raw_text = ?, text_hash = ?, first_seen_at = ?, is_cancelled = 0
                        WHERE id = ?
                        """,
                        (source, category, issued_at, region, raw_text, h, _now(), existing["id"]),
                    )
                    return existing["id"]

            cur = conn.execute(
                """
                INSERT OR IGNORE INTO warnings
                    (source, area_code, msg_number, category, issued_at, region, raw_text, text_hash, first_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (source, area_code, msg_number, category, issued_at, region, raw_text, h, _now()),
            )
            return cur.lastrowid if cur.rowcount else None

    def mark_cancelled(self, area_code: str, msg_number: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE warnings SET is_cancelled = 1 WHERE area_code = ? AND msg_number = ?",
                (area_code, msg_number),
            )

    def active_warnings(self, area_code: str, limit: int = 20) -> list[sqlite3.Row]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM warnings WHERE area_code = ? AND is_cancelled = 0",
                (area_code,),
            ).fetchall()
        rows = sorted(rows, key=_msgnum_sort_key, reverse=True)
        return rows[:limit]

    def get_warning(self, warning_id: int) -> Optional[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute("SELECT * FROM warnings WHERE id = ?", (warning_id,)).fetchone()

    def recent_warnings(self, area_code: str, since_iso: str) -> list[sqlite3.Row]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM warnings WHERE area_code = ? AND first_seen_at > ? ORDER BY first_seen_at",
                (area_code, since_iso),
            ).fetchall()
        return rows

    def already_notified(self, user_id: int, warning_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM sent_notifications WHERE user_id = ? AND warning_id = ?",
                (user_id, warning_id),
            ).fetchone()
        return row is not None

    def mark_notified(self, user_id: int, warning_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sent_notifications (user_id, warning_id, sent_at) VALUES (?, ?, ?)",
                (user_id, warning_id, _now()),
            )

    # ------------------------------------------------------------------ #
    # Платежи
    # ------------------------------------------------------------------ #

    def log_payment(self, user_id: int, charge_id: str, stars_amount: int, is_recurring: bool) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO payments (user_id, charge_id, stars_amount, is_recurring, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, charge_id, stars_amount, int(is_recurring), _now()),
            )

    def get_last_charge_id(self, user_id: int) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT charge_id FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return row["charge_id"] if row else None

    def get_all_user_ids(self) -> list[int]:
        with self._conn() as conn:
            rows = conn.execute("SELECT user_id FROM users").fetchall()
        return [r["user_id"] for r in rows]

    # ------------------------------------------------------------------ #
    # Статистика для админа
    # ------------------------------------------------------------------ #

    def stats(self) -> dict:
        with self._conn() as conn:
            total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            premium_users = conn.execute(
                "SELECT COUNT(*) c FROM users WHERE is_premium = 1 AND premium_until > ?",
                (_now(),),
            ).fetchone()["c"]
            total_warnings = conn.execute("SELECT COUNT(*) c FROM warnings").fetchone()["c"]
            active_warnings = conn.execute(
                "SELECT COUNT(*) c FROM warnings WHERE is_cancelled = 0"
            ).fetchone()["c"]
        return {
            "total_users": total_users,
            "premium_users": premium_users,
            "total_warnings": total_warnings,
            "active_warnings": active_warnings,
        }
