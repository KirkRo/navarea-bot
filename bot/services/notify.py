"""
Лента уведомлений для колокольчика.

Собирается на лету из того, что уже есть в базе, плюс объявления бота:

  * ответ поддержки, который человек ещё не читал;
  * сертификаты, у которых подходит срок;
  * батареи EPIRB и SART, которым пора на замену;
  * новые предупреждения в отмеченных районах за последние сутки;
  * новости и обновления бота (таблица notices).

Отдельной таблицы «уведомления пользователя» нет специально. Сроки и
предупреждения и так живут в своих таблицах, а дублировать их в ленту --
значит рано или поздно разойтись с источником и показывать напоминание
о сертификате, который уже продлили.

Непрочитанным считается всё, что появилось позже отметки о последнем
просмотре (users.notif_seen_at). Открыл колокольчик -- отметка сдвинулась,
счётчик обнулился.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Что нового в самом боте. Строка сверху -- самая свежая, дата в ISO: по ней
# же считается, прочитал человек запись или нет.
#
# Сюда пишутся правки кода, которые видит пользователь. Разовые объявления
# владелец добавляет из панели («Связь» -> «Написать всем в колокольчик»),
# они ложатся в таблицу notices и в этот список не попадают.
CHANGELOG = [
    {"at": "2026-08-12T11:00:00+00:00",
     "title": "Тренажёр ЭКНИС Furuno FMD-3300",
     "title_en": "ECDIS simulator: Furuno FMD-3300",
     "body": "В разделе тренажёров появилась ЭКНИС: строка состояния с режимами NAVI, PLAN и "
             "CHARTS, InstantAccess bar, боксы датчиков и маршрута, измерение пеленга и "
             "дистанции через EBL и VRM, тревоги с квитированием и пульт RCU-024. Раскладка "
             "сверена с мануалом станции.",
     "body_en": "An ECDIS has been added to the simulators: status bar with the NAVI, PLAN and "
                "CHARTS modes, InstantAccess bar, sensor and route boxes, bearing and range "
                "measurement with EBL and VRM, alerts with acknowledgement and the RCU-024 "
                "control unit. The layout follows the equipment manual."},
    {"at": "2026-08-12T10:00:00+00:00",
     "title": "Порты мира, астрономия и планшет расхождения",
     "title_en": "World ports, celestial sights and the manoeuvring plot",
     "body": "Добавлен справочник на 3559 портов из World Port Index: гавань, укрытие и средняя "
             "величина прилива, всё работает без сети. Появились альманах Солнца и Луны с "
             "линией положения и маневренный планшет в расчёте расхождения. Предупреждения "
             "выгружаются девятью форматами, включая Shapefile и GeoPackage.",
     "body_en": "A directory of 3559 ports from the World Port Index has been added: harbour "
                "type, shelter and mean tide range, all of it working offline. There is now a "
                "Sun and Moon almanac with the position line, and a manoeuvring plot in the "
                "passing distance tool. Warnings export in nine formats, Shapefile and "
                "GeoPackage among them."},
    {"at": "2026-08-12T09:00:00+00:00",
     "title": "Канадская Арктика и выгрузка файлов",
     "title_en": "The Canadian Arctic and file export",
     "body": "Заработали районы XVII и XVIII: море Бофорта, Гудзонов залив и Северо-Западный "
             "проход теперь отслеживаются автоматически. Предупреждения можно выгрузить "
             "в GeoJSON, KML или CSV, файл придёт сообщением в чат.",
     "body_en": "NAVAREA XVII and XVIII are live: the Beaufort Sea, Hudson Bay and the "
                "Northwest Passage are now polled automatically. Warnings can be exported "
                "as GeoJSON, KML or CSV, and the file arrives as a message in the chat."},
    {"at": "2026-08-12T00:00:00+00:00",
     "title": "Подпиской можно управлять в приложении",
     "title_en": "The subscription is now managed inside the app",
     "body": "Автопродление включается и выключается в «Настройках», раздел «Доступ». "
             "Оплаченный период после отключения дорабатывает до конца. Раньше отмена "
             "жила только командой в чате.",
     "body_en": "Auto-renewal is switched on and off in Settings, under Access. After you "
                "switch it off, the period already paid for runs to its end. Cancelling "
                "used to be possible only through a command in the chat."},
    {"at": "2026-08-09T02:00:00+00:00",
     "title": "Полный английский интерфейс",
     "title_en": "Full English interface",
     "body": "Кнопка языка теперь переводит всё: своды сигналов, правила расхождения, "
             "справочник ЦИВ, тренажёры EPIRB и SART, справку и единицы измерения.",
     "body_en": "The language button now translates everything: the code of signals, the "
                "COLREG summaries, the DSC reference, the EPIRB and SART simulators, the "
                "help section and the units."},
    {"at": "2026-08-08T12:00:00+00:00",
     "title": "Ассистент научился брать данные сам",
     "title_en": "The assistant now fetches data itself",
     "body": "Ask AI теперь сам достаёт погоду на переходе, предупреждения по маршруту, "
             "сводку циклонов и карточку судна. Появилась библиотека готовых сценариев "
             "и режимы ответа: коротко, чек-лист, расчёт, аварийно.",
     "body_en": "Ask AI now pulls the weather on passage, the warnings along the route, the "
                "cyclone summary and the vessel card by itself. A library of ready prompts "
                "and answer modes has been added: brief, checklist, calculation, emergency."},
    {"at": "2026-08-08T11:00:00+00:00",
     "title": "Тренажёр ПВ/КВ переделан",
     "title_en": "The MF/HF simulator has been rebuilt",
     "body": "Меню станции как на настоящей FS-2575C, экраны COMPOSE и WATCH KEEPING, "
             "сканирование частот, режимы яркости BRILL и звук посылки ЦИВ. "
             "Экран стал вдвое крупнее.",
     "body_en": "The set’s menu as on a real FS-2575C, the COMPOSE and WATCH KEEPING screens, "
                "frequency scanning, the BRILL brilliance modes and the sound of a DSC burst. "
                "The display is twice the size."},
    {"at": "2026-08-08T10:00:00+00:00",
     "title": "Оплата подписки прямо в приложении",
     "title_en": "Subscription payment inside the app",
     "body": "Кнопка «Оформить» открывает окно оплаты Telegram, а не закрывает приложение.",
     "body_en": "The Subscribe button opens the Telegram payment window instead of closing the app."},
]


def _parse(dt) -> datetime | None:
    if not dt:
        return None
    try:
        d = datetime.fromisoformat(str(dt).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat()


def _days_left(value) -> int | None:
    d = _parse(value)
    if d is None:
        return None
    return (d - datetime.now(timezone.utc)).days


def _threshold_at(expires, thresholds: tuple[int, ...]) -> str:
    """Когда срок пересёк ближайший рубеж напоминания.

    Срок -- не событие, а состояние: сертификат не «происходит», он просто
    подходит к концу. Чтобы его можно было честно считать прочитанным,
    берём момент пересечения рубежа (за 60, 30, 14, 7, 3, 1 день) как время
    появления записи. Тогда напоминание становится новым ровно один раз на
    каждом рубеже, а не висит непрочитанным вечно и не пропадает навсегда
    после первого открытия колокольчика.
    """
    d = _parse(expires)
    if d is None:
        return _iso(datetime.now(timezone.utc))
    left = (d - datetime.now(timezone.utc)).days
    if left < 0:
        return _iso(d)                       # просрочен -- считаем от даты окончания
    for t in sorted(thresholds):
        if left <= t:
            return _iso(d - timedelta(days=t))
    return _iso(d - timedelta(days=max(thresholds)))


def build_feed(db, user_id: int) -> dict:
    """Лента и число непрочитанного."""
    now = datetime.now(timezone.utc)
    seen = _parse(db.get_notif_seen_at(user_id)) or (now - timedelta(days=365))
    items: list[dict] = []

    # --- ответ поддержки ---
    try:
        unread = db.support_unread_for_user(user_id)
        if unread:
            thread = db.get_support_thread(user_id, limit=5)
            last = next((m for m in reversed(thread) if m["author"] == "owner"), None)
            items.append({
                "kind": "support",
                "title": "Ответ поддержки",
                "title_en": "Reply from support",
                "body": (last["text"][:160] if last else "Есть новое сообщение"),
                "body_en": (last["text"][:160] if last else "There is a new message"),
                "at": (last["created_at"] if last else _iso(now)),
                "go": "support",
                "urgent": False,
            })
    except Exception:
        logger.exception("Уведомления: поддержка")

    # --- сроки сертификатов ---
    try:
        for c in db.get_certificates(user_id):
            left = _days_left(c["expires"])
            if left is None or left > 60:
                continue
            items.append({
                "kind": "cert",
                "title": ("Истёк срок: " if left < 0 else "Подходит срок: ") + str(c["name"]),
                "title_en": ("Expired: " if left < 0 else "Expiring: ") + str(c["name"]),
                "body": ("Просрочен на %d дн." % abs(left)) if left < 0
                        else ("Осталось %d дн., до %s" % (left, str(c["expires"])[:10])),
                "body_en": ("Overdue by %d days" % abs(left)) if left < 0
                           else ("%d days left, until %s" % (left, str(c["expires"])[:10])),
                # Новым считается позднее из двух: когда срок пересёк рубеж
                # и когда сертификат вообще завели. Иначе только что
                # добавленный сертификат с близким сроком не подсветился бы:
                # рубеж он пересёк ещё до того, как о нём узнали.
                "at": max(_threshold_at(c["expires"], (60, 30, 14, 7, 3, 1)),
                          str(c.get("created_at") or "")),
                "go": "bridge",
                "urgent": left <= 7,
            })
    except Exception:
        logger.exception("Уведомления: сертификаты")

    # --- батареи EPIRB и SART ---
    try:
        eq = db.get_gmdss(user_id) or {}
        for kind, name in (("epirb", "EPIRB"), ("sart", "SART")):
            exp = (eq.get(kind) or {}).get("battery_expires")
            left = _days_left(exp)
            if left is None or left > 90:
                continue
            items.append({
                "kind": "gmdss",
                "title": ("Батарея %s просрочена" % name) if left < 0
                         else ("Батарея %s: замена" % name),
                "title_en": ("%s battery overdue" % name) if left < 0
                            else ("%s battery: replacement" % name),
                "body": ("Просрочена на %d дн." % abs(left)) if left < 0
                        else ("Осталось %d дн., до %s" % (left, str(exp)[:10])),
                "body_en": ("Overdue by %d days" % abs(left)) if left < 0
                           else ("%d days left, until %s" % (left, str(exp)[:10])),
                "at": _threshold_at(exp, (90, 30, 7, 1)),
                "go": kind,
                "urgent": left <= 30,
            })
    except Exception:
        logger.exception("Уведомления: ГМССБ")

    # --- новые предупреждения в отмеченных районах ---
    try:
        favs = db.get_favorites(user_id) or []
        if favs:
            stats = db.area_stats()
            fresh = [(code, stats.get(code, {}).get("added_today", 0)) for code in favs]
            total = sum(n for _c, n in fresh if n)
            if total:
                where = ", ".join(c for c, n in fresh if n)
                items.append({
                    "kind": "warning",
                    "title": "Новые предупреждения: %d" % total,
                    "title_en": "New warnings: %d" % total,
                    "body": "За сегодня в твоих районах: " + where,
                    "body_en": "Today in your areas: " + where,
                    # Сводка за сутки, поэтому и время у неё -- начало суток.
                    # Раньше здесь стояло «час назад», и запись снова
                    # становилась непрочитанной каждый час: человек читал
                    # ленту, выходил, возвращался -- и она опять горела.
                    "at": _iso(now.replace(hour=0, minute=0, second=0, microsecond=0)),
                    "go": "areas",
                    "urgent": False,
                })
    except Exception:
        logger.exception("Уведомления: предупреждения")

    # --- новости и обновления бота ---
    try:
        for n in CHANGELOG:
            items.append({"kind": "release", "title": n["title"], "body": n["body"],
                          "title_en": n.get("title_en"), "body_en": n.get("body_en"),
                          "at": n["at"], "go": None, "urgent": False})
        for n in db.get_notices(user_id, limit=20):
            # Объявления владелец пишет на одном языке -- переводить их
            # некому, поэтому отдаём как есть.
            items.append({"kind": n.get("kind") or "news", "title": n["title"],
                          "body": n.get("body") or "", "at": n["created_at"],
                          "go": None, "urgent": False})
    except Exception:
        logger.exception("Уведомления: новости")

    items.sort(key=lambda x: str(x.get("at") or ""), reverse=True)
    for it in items:
        at = _parse(it.get("at"))
        # Непрочитанное -- то, что появилось после последнего просмотра и
        # уже наступило. Верхняя граница обязательна: запись с датой в
        # будущем (опечатка в объявлении) иначе всегда «новее» отметки о
        # прочтении, и колокольчик горел бы вечно. Когда её время придёт,
        # она станет непрочитанной сама.
        it["unread"] = bool(at and seen < at <= now)

    return {
        "items": items[:40],
        "unread": sum(1 for i in items if i["unread"]),
        "seen_at": _iso(seen),
    }
