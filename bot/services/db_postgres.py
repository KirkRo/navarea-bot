"""
То же самое хранилище, что db.py, но поверх Postgres (Neon и любой другой
Postgres по DATABASE_URL) вместо локального файла SQLite.

Нужен для варианта хостинга Render + Neon, где у процесса нет надёжного
локального диска между перезапусками -- база должна жить отдельно, во
внешнем сервисе. Набор методов и их поведение полностью совпадают с
db.py, чтобы хендлеры не знали и не заботились, какое хранилище
используется на самом деле (см. bot/services/db_factory.py).
"""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

import psycopg2
import psycopg2.extras

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
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
    user_id BIGINT NOT NULL,
    area_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, area_code)
);

CREATE TABLE IF NOT EXISTS warnings (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    area_code TEXT NOT NULL,
    msg_number TEXT,
    category TEXT,
    issued_at TEXT,
    region TEXT,
    raw_text TEXT NOT NULL,
    text_hash TEXT NOT NULL UNIQUE,
    first_seen_at TEXT NOT NULL,
    is_cancelled INTEGER NOT NULL DEFAULT 0,
    shapes_json TEXT
);

CREATE TABLE IF NOT EXISTS sent_notifications (
    user_id BIGINT NOT NULL,
    warning_id INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (user_id, warning_id)
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    charge_id TEXT,
    stars_amount INTEGER,
    is_recurring INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id BIGINT NOT NULL,
    area_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, area_code)
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


class PostgresDatabase:
    def __init__(self, dsn: str):
        self.dsn = dsn
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator["psycopg2.extensions.connection"]:
        conn = psycopg2.connect(self.dsn, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Пользователи
    # ------------------------------------------------------------------ #

    def upsert_user(self, user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, username, first_name, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
                """,
                (user_id, username, first_name, _now()),
            )

    def get_user(self, user_id: int) -> Optional[User]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
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
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_premium = 1, premium_until = %s WHERE user_id = %s",
                (until_iso, user_id),
            )

    def revoke_premium(self, user_id: int) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = %s",
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
        today = datetime.now(timezone.utc).date().isoformat()
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT qa_count_today, qa_count_date FROM users WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if row is None:
                return False
            count = row["qa_count_today"] if row["qa_count_date"] == today else 0
            if count >= daily_limit:
                return False
            cur.execute(
                "UPDATE users SET qa_count_today = %s, qa_count_date = %s WHERE user_id = %s",
                (count + 1, today, user_id),
            )
            return True

    # ------------------------------------------------------------------ #
    # Подписки на районы NAVAREA
    # ------------------------------------------------------------------ #

    def get_user_areas(self, user_id: int) -> list[str]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT area_code FROM area_subscriptions WHERE user_id = %s ORDER BY area_code",
                (user_id,),
            )
            rows = cur.fetchall()
        return [r["area_code"] for r in rows]

    def add_area(self, user_id: int, area_code: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO area_subscriptions (user_id, area_code, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, area_code) DO NOTHING
                """,
                (user_id, area_code, _now()),
            )

    def remove_area(self, user_id: int, area_code: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM area_subscriptions WHERE user_id = %s AND area_code = %s",
                (user_id, area_code),
            )

    def users_subscribed_to(self, area_code: str) -> list[int]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM area_subscriptions WHERE area_code = %s",
                (area_code,),
            )
            rows = cur.fetchall()
        return [r["user_id"] for r in rows]

    # ------------------------------------------------------------------ #
    # Предупреждения NAVAREA
    # ------------------------------------------------------------------ #

    def warning_exists(self, raw_text: str) -> bool:
        h = text_hash(raw_text)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM warnings WHERE text_hash = %s", (h,))
            row = cur.fetchone()
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
        shapes: Optional[list] = None,
    ) -> Optional[int]:
        h = text_hash(raw_text)
        shapes_json = json.dumps(shapes, ensure_ascii=False) if shapes else None
        with self._conn() as conn, conn.cursor() as cur:
            if msg_number:
                cur.execute(
                    "SELECT id, text_hash FROM warnings WHERE area_code = %s AND msg_number = %s",
                    (area_code, msg_number),
                )
                existing = cur.fetchone()
                if existing:
                    if existing["text_hash"] == h:
                        return None
                    cur.execute(
                        """
                        UPDATE warnings
                        SET source = %s, category = %s, issued_at = %s, region = %s,
                            raw_text = %s, text_hash = %s, first_seen_at = %s, is_cancelled = 0,
                            shapes_json = %s
                        WHERE id = %s
                        """,
                        (source, category, issued_at, region, raw_text, h, _now(), shapes_json, existing["id"]),
                    )
                    return existing["id"]

            cur.execute(
                """
                INSERT INTO warnings
                    (source, area_code, msg_number, category, issued_at, region, raw_text, text_hash, first_seen_at, shapes_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (text_hash) DO NOTHING
                RETURNING id
                """,
                (source, area_code, msg_number, category, issued_at, region, raw_text, h, _now(), shapes_json),
            )
            row = cur.fetchone()
            return row["id"] if row else None

    def mark_cancelled(self, area_code: str, msg_number: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE warnings SET is_cancelled = 1 WHERE area_code = %s AND msg_number = %s",
                (area_code, msg_number),
            )

    def active_warnings(self, area_code: str, limit: int = 20) -> list[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM warnings WHERE area_code = %s AND is_cancelled = 0",
                (area_code,),
            )
            rows = cur.fetchall()
        rows = sorted(rows, key=_msgnum_sort_key, reverse=True)
        return rows[:limit]

    def get_warning(self, warning_id: int) -> Optional[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM warnings WHERE id = %s", (warning_id,))
            return cur.fetchone()

    def recent_warnings(self, area_code: str, since_iso: str) -> list[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM warnings WHERE area_code = %s AND first_seen_at > %s ORDER BY first_seen_at",
                (area_code, since_iso),
            )
            return cur.fetchall()

    def already_notified(self, user_id: int, warning_id: int) -> bool:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM sent_notifications WHERE user_id = %s AND warning_id = %s",
                (user_id, warning_id),
            )
            row = cur.fetchone()
        return row is not None

    def mark_notified(self, user_id: int, warning_id: int) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sent_notifications (user_id, warning_id, sent_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, warning_id) DO NOTHING
                """,
                (user_id, warning_id, _now()),
            )

    # ------------------------------------------------------------------ #
    # Платежи
    # ------------------------------------------------------------------ #

    def log_payment(self, user_id: int, charge_id: str, stars_amount: int, is_recurring: bool) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments (user_id, charge_id, stars_amount, is_recurring, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, charge_id, stars_amount, int(is_recurring), _now()),
            )

    def get_last_charge_id(self, user_id: int) -> Optional[str]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT charge_id FROM payments WHERE user_id = %s ORDER BY id DESC LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
        return row["charge_id"] if row else None

    def get_all_user_ids(self) -> list[int]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users")
            rows = cur.fetchall()
        return [r["user_id"] for r in rows]

    # ------------------------------------------------------------------ #
    # Статистика для админа
    # ------------------------------------------------------------------ #

    def stats(self) -> dict:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM users")
            total_users = cur.fetchone()["c"]
            cur.execute(
                "SELECT COUNT(*) c FROM users WHERE is_premium = 1 AND premium_until > %s",
                (_now(),),
            )
            premium_users = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) c FROM warnings")
            total_warnings = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) c FROM warnings WHERE is_cancelled = 0")
            active_warnings = cur.fetchone()["c"]
        return {
            "total_users": total_users,
            "premium_users": premium_users,
            "total_warnings": total_warnings,
            "active_warnings": active_warnings,
        }

    # ------------------------------------------------------------------ #
    # Данные для Mini App: статистика, избранное, поиск
    # ------------------------------------------------------------------ #

    def area_stats(self) -> dict[str, dict]:
        today = datetime.now(timezone.utc).date().isoformat()
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        result: dict[str, dict] = {}
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT area_code,
                       SUM(CASE WHEN is_cancelled = 0 THEN 1 ELSE 0 END) AS in_force,
                       SUM(CASE WHEN is_cancelled = 1 THEN 1 ELSE 0 END) AS archived,
                       SUM(CASE WHEN is_cancelled = 0 AND first_seen_at >= %s THEN 1 ELSE 0 END) AS today,
                       SUM(CASE WHEN is_cancelled = 0 AND first_seen_at >= %s THEN 1 ELSE 0 END) AS week,
                       MAX(first_seen_at) AS last_update
                FROM warnings GROUP BY area_code
                """,
                (today, week_ago),
            )
            for row in cur.fetchall():
                result[row["area_code"]] = {
                    "in_force": int(row["in_force"] or 0),
                    "archived": int(row["archived"] or 0),
                    "added_today": int(row["today"] or 0),
                    "added_week": int(row["week"] or 0),
                    "last_update": row["last_update"],
                }
        return result

    def search_warnings(self, query: str = "", areas: Optional[list[str]] = None,
                        include_archived: bool = False, limit: int = 2000) -> list[dict]:
        sql = "SELECT * FROM warnings WHERE 1=1"
        params: list = []
        if not include_archived:
            sql += " AND is_cancelled = 0"
        if areas:
            sql += " AND area_code = ANY(%s)"
            params.append(areas)
        if query:
            sql += " AND (raw_text ILIKE %s OR msg_number ILIKE %s OR region ILIKE %s)"
            like = f"%{query}%"
            params.extend([like, like, like])
        sql += " LIMIT %s"
        params.append(limit)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return sorted(rows, key=_msgnum_sort_key, reverse=True)

    def all_active_warnings(self, limit: int = 3000) -> list[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM warnings WHERE is_cancelled = 0 LIMIT %s", (limit,))
            return cur.fetchall()

    def get_favorites(self, user_id: int) -> list[str]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT area_code FROM favorites WHERE user_id = %s ORDER BY area_code", (user_id,))
            return [r["area_code"] for r in cur.fetchall()]

    def toggle_favorite(self, user_id: int, area_code: str) -> bool:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM favorites WHERE user_id = %s AND area_code = %s", (user_id, area_code))
            if cur.fetchone():
                cur.execute("DELETE FROM favorites WHERE user_id = %s AND area_code = %s", (user_id, area_code))
                return False
            cur.execute(
                "INSERT INTO favorites (user_id, area_code, created_at) VALUES (%s, %s, %s)",
                (user_id, area_code, _now()),
            )
            return True
