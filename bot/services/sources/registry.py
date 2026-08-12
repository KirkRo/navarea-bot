"""
Реестр всех 21 района NAVAREA (плюс HYDROLANT/HYDROPAC как бонус от NGA).

Для каждого района указано:
  - name        человекочитаемое название/покрытие
  - coordinator кто официально координирует район
  - url         официальный сайт координатора (там где удалось найти рабочий)
  - status      "live"          -- бот реально опрашивает источник автоматически
                "experimental"  -- источник подключен, но разбор текста нужно
                                   проверить на реальных данных (см. модуль)
                "listed"        -- официальный адрес координатора известен и
                                   проверен, но своего разборщика под него ещё
                                   нет: приложение даёт прямую ссылку, а сами
                                   сообщения в базу не попадают
                "blocked"       -- официальный сайт есть, но запрещает
                                   автоматический доступ (robots.txt) -- бот
                                   только даёт ссылку
                "unknown"       -- координатор известен, а рабочий адрес сайта
                                   на момент разработки не нашёлся или устарел
                "none"          -- координатор не публикует данные в сети

Это результат ручного разбора (см. README, раздел "Источники данных") --
если find появится новый рабочий адрес, его легко прописать сюда и
добавить в SOURCES ниже.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ...config import config
from .base import FallbackSource, WarningSource
from .canada_ccg import CanadaCcgSource
from .nga import NgaSource
from .peru_dhn import PeruDhnSource
from .sealagom import SealagomCoastalSource, SealagomSource
from .spain_ihm import SpainIhmSource
from .ukho import UkhoSource

logger = logging.getLogger(__name__)


@dataclass
class AreaInfo:
    code: str
    name: str
    coordinator: str
    url: Optional[str]
    status: str  # live | experimental | blocked | unknown | none


AREAS: dict[str, AreaInfo] = {
    "I": AreaInfo("I", "Северное море, Ла-Манш", "Великобритания (UKHO)",
                  "https://msi.admiralty.co.uk/RadioNavigationalWarnings", "live"),
    "I-COASTAL": AreaInfo("I-COASTAL", "Побережье Великобритании", "Великобритания (UKHO)",
                           "https://msi.admiralty.co.uk/RadioNavigationalWarnings", "live"),
    "II": AreaInfo("II", "СВ Атлантика (Франция)", "Франция (SHOM)",
                   "https://portail.ping-info-nautique.fr/avurnav-notice", "listed"),
    "III": AreaInfo("III", "Средиземное и Чёрное море", "Испания (Instituto Hidrografico de la Marina)",
                     "https://armada.defensa.gob.es/ihm/XML/navareas_crudo.xml", "experimental"),
    "IV": AreaInfo("IV", "Карибы, вост. побережье США", "США (NGA)",
                    "https://msi.nga.mil/NavWarnings", "live"),
    "V": AreaInfo("V", "Атлантика (Бразилия)", "Бразилия (DHN)",
                   "https://www.marinha.mil.br/chm/dados-do-segnav-aviso-radio-nautico-tela/avisos-radio-nauticos-e-sar", "listed"),
    "VI": AreaInfo("VI", "Атлантика (Аргентина)", "Аргентина (SHN)",
                    "https://www.hidro.gov.ar/nautica/RadioavisosNauticos.asp?op=8", "listed"),
    "VII": AreaInfo("VII", "Атлантика (ЮАР)", "ЮАР (SANHO)",
                     "https://www.sanho.co.za/notices_mariners/navarea_v11_messages.htm?b2=NAVAREA+VII", "listed"),
    "VIII": AreaInfo("VIII", "Индийский океан (Индия)", "Индия (National Hydrographic Office)",
                      "https://hydrobharat.gov.in/navarea-warnings", "listed"),
    "IX": AreaInfo("IX", "Аравийское море (Пакистан)", "Пакистан (Pakistan Navy)",
                    "https://hydrography.paknavy.gov.pk/navarea-ix-warnings/", "listed"),
    "X": AreaInfo("X", "Австралия", "Австралия (AMSA)", "https://www.operations.amsa.gov.au/AMSA.Web.MSIPublication/Home", "listed"),
    "XI": AreaInfo("XI", "Япония", "Япония (Japan Coast Guard)",
                    "https://www1.kaiho.mlit.go.jp/TUHO/keiho/navarea11_en.html", "listed"),
    "XII": AreaInfo("XII", "Зап. побережье США", "США (NGA)",
                     "https://msi.nga.mil/NavWarnings", "live"),
    "XIII": AreaInfo("XIII", "Тихий океан (Россия)", "Россия",
                      None, "none"),
    "XIV": AreaInfo("XIV", "Новая Зеландия", "Новая Зеландия (Maritime NZ)",
                     "https://www.maritimenz.govt.nz/navigational-warnings", "listed"),
    "XV": AreaInfo("XV", "Чили", "Чили (SHOA)",
                    "https://www.shoa.cl/php/radioAvisosPDF.php?documento=NAVAREA&tipo=3", "listed"),
    "XVI": AreaInfo("XVI", "Перу", "Перу (DHN)",
                     "https://www.dhn.mil.pe/portal/navarea/radioavisos-warnings", "live"),
    "XVII": AreaInfo("XVII", "Зап. Канада", "Канада (CCG)",
                      "https://nis.ccg-gcc.gc.ca/public/rest/messages/en/search-navareas?navareas=2&status=PUBLISHED&sortBy=DATE&maxHits=50", "live"),
    "XVIII": AreaInfo("XVIII", "Канадская Арктика", "Канада (CCG)",
                       "https://nis.ccg-gcc.gc.ca/public/rest/messages/en/search-navareas?navareas=4&status=PUBLISHED&sortBy=DATE&maxHits=50", "live"),
    "XIX": AreaInfo("XIX", "Норвегия", "Норвегия (Norwegian Coastal Administration)",
                     "https://kyvreports.kystverket.no/NavcoReport/navareaxixvarsler.aspx", "listed"),
    "XX": AreaInfo("XX", "Баренцево море (Россия)", "Россия", None, "none"),
    "XXI": AreaInfo("XXI", "Дальний Восток (Россия)", "Россия", None, "none"),
    "HYDROLANT": AreaInfo("HYDROLANT", "Атлантика (доп. от NGA)", "США (NGA)",
                           "https://msi.nga.mil/NavWarnings", "live"),
    "HYDROPAC": AreaInfo("HYDROPAC", "Тихий океан (доп. от NGA)", "США (NGA)",
                          "https://msi.nga.mil/NavWarnings", "live"),
}

# Какой класс-источник реально умеет скачивать/парсить каждый район.
#
# Если задан SEALAGOM_API_TOKEN -- Sealagom накрывает сразу все 21 район
# NAVAREA (I-XXI) одним платным API ($20/мес), заменяя собственные
# скрейперы для этих районов. Свои скрейперы (NGA/UKHO/Peru/Spain) при
# этом никуда не деваются и используются как есть для HYDROLANT/HYDROPAC
# (это не NAVAREA-номера, Sealagom их отдельно не отдаёт), а также
# остаются в коде на случай если решишь отключить Sealagom обратно --
# тогда достаточно убрать токен из .env, ничего больше менять не нужно.
_nga = NgaSource()
_ukho = UkhoSource()
_spain = SpainIhmSource()
_peru = PeruDhnSource()
_canada = CanadaCcgSource()

_OWN_SOURCES: dict[str, WarningSource] = {
    "I": _ukho,
    "I-COASTAL": _ukho,
    "III": _spain,
    "IV": _nga,
    "XII": _nga,
    "HYDROLANT": _nga,
    "HYDROPAC": _nga,
    "XVI": _peru,
    "XVII": _canada,
    "XVIII": _canada,
}

SOURCES: dict[str, WarningSource] = dict(_OWN_SOURCES)

if config.sealagom_api_token:
    _sealagom = SealagomSource(config.sealagom_api_token)
    for _roman_code in SealagomSource.covers_areas:
        if _roman_code in _OWN_SOURCES:
            # для этого района уже есть свой скрейпер -- используем Sealagom
            # как основной источник, а свой скрейпер как запасной на случай
            # если Sealagom прямо сейчас недоступен (см. FallbackSource)
            SOURCES[_roman_code] = FallbackSource(_sealagom, _OWN_SOURCES[_roman_code])
        else:
            SOURCES[_roman_code] = _sealagom
        if _roman_code not in AREAS:
            AREAS[_roman_code] = AreaInfo(_roman_code, _roman_code, "Sealagom", "https://www.sealagom.com/", "live")

# Статус "live" считаем динамически: если Sealagom настроен, все районы,
# которые он покрывает, живые независимо от того, что написано в AREAS
# статически (та таблица -- результат ручного разбора БЕЗ Sealagom).
# Отдельно III остаётся "experimental" пока Sealagom не настроен -- в
# одиночку это по-прежнему разбор с оговорками (см. spain_ihm.py).
def _effective_status(code: str, info: "AreaInfo") -> str:
    if code not in SOURCES:
        return info.status
    if config.sealagom_api_token and code in SealagomSource.covers_areas:
        return "live"
    if code == "III":
        return "experimental"
    return "live"


LIVE_AREAS = [code for code, info in AREAS.items() if _effective_status(code, info) == "live"]
EXPERIMENTAL_AREAS = [code for code, info in AREAS.items() if _effective_status(code, info) == "experimental"]
POLLABLE_AREAS = LIVE_AREAS + EXPERIMENTAL_AREAS  # то, что реально можно отслеживать автоматически


def area_choice_label(code: str) -> str:
    info = AREAS[code]
    status = _effective_status(code, info)
    icon = {"live": "🟢", "experimental": "🟡", "blocked": "🔒", "unknown": "❔", "none": "🚫"}[status]
    return f"{icon} {code} — {info.name}"


# ---------------------------------------------------------------------- #
# Береговые предупреждения (Coastal / NAVTEX)
# ---------------------------------------------------------------------- #
#
# В отличие от NAVAREA, у береговых регионов нет фиксированной нумерации
# I-XXI -- это произвольный список стран и зон, который знает только сам
# Sealagom. Поэтому их нельзя прописать в таблицу заранее: список
# запрашивается один раз при запуске бота (см. register_coastal_areas,
# вызывается из main.py) и добавляется в те же AREAS/SOURCES, что и
# остальные районы. Дальше они работают наравне: выбираются в /areas,
# попадают в Mini App, рассылаются подписчикам.
#
# Код района для них -- "COASTAL:<id>", чтобы не столкнуться с римскими
# номерами NAVAREA.

_coastal_source: "SealagomCoastalSource | None" = None


async def register_coastal_areas() -> int:
    """Запрашивает список береговых регионов и регистрирует их.
    Возвращает, сколько зарегистрировано (0 -- если Sealagom не настроен
    или недоступен, это не ошибка, бот просто работает без них)."""
    global _coastal_source

    if not config.sealagom_api_token:
        return 0

    if _coastal_source is None:
        _coastal_source = SealagomCoastalSource(config.sealagom_api_token)

    try:
        regions = await _coastal_source.list_regions()
    except Exception as e:
        # Обычно это 403: береговые предупреждения входят не во всякий тариф
        # Sealagom. Бот от этого не страдает -- просто работает без них,
        # поэтому пишем одну понятную строку, а не полный стектрейс.
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code == 403:
            logger.warning("Береговые предупреждения Sealagom недоступны (403). "
                           "Проверь, входят ли они в оплаченный тариф. "
                           "Всё остальное работает как обычно.")
        else:
            logger.warning("Не удалось получить список береговых регионов Sealagom: %s", e)
        return 0

    added = 0
    for r in regions:
        rid, title = r.get("id"), (r.get("title") or "").strip()
        if rid is None:
            continue
        code = f"COASTAL:{rid}"
        if code in AREAS:
            continue
        AREAS[code] = AreaInfo(
            code=code,
            name=title or f"Береговой район {rid}",
            coordinator="Sealagom (береговые предупреждения)",
            url="https://www.sealagom.com/",
            status="live",
        )
        SOURCES[code] = _coastal_source
        added += 1

    if added:
        _rebuild_area_lists()
        logger.info("Зарегистрировано береговых регионов: %d", added)
    return added


def _rebuild_area_lists() -> None:
    """AREAS пополняется уже после импорта модуля, поэтому производные
    списки нужно пересобрать, иначе новые районы не появятся в выборе."""
    global LIVE_AREAS, EXPERIMENTAL_AREAS, POLLABLE_AREAS
    LIVE_AREAS = [c for c, i in AREAS.items() if _effective_status(c, i) == "live"]
    EXPERIMENTAL_AREAS = [c for c, i in AREAS.items() if _effective_status(c, i) == "experimental"]
    POLLABLE_AREAS = LIVE_AREAS + EXPERIMENTAL_AREAS


def area_display_name(code: str) -> str:
    """Человекочитаемое имя для кнопок и сообщений. Для береговых районов
    убирает служебный префикс COASTAL:."""
    info = AREAS.get(code)
    base = info.name if info else code
    if code.startswith("COASTAL:"):
        return f"{base} (берег)"
    return base
