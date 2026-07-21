"""
Реестр всех 21 района NAVAREA (плюс HYDROLANT/HYDROPAC как бонус от NGA).

Для каждого района указано:
  - name        человекочитаемое название/покрытие
  - coordinator кто официально координирует район
  - url         официальный сайт координатора (там где удалось найти рабочий)
  - status      "live"          -- бот реально опрашивает источник автоматически
                "experimental"  -- источник подключен, но разбор текста нужно
                                   проверить на реальных данных (см. модуль)
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

from dataclasses import dataclass
from typing import Optional

from .base import WarningSource
from .nga import NgaSource
from .peru_dhn import PeruDhnSource
from .spain_ihm import SpainIhmSource
from .ukho import UkhoSource


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
                   "https://gan.shom.fr/navarea/", "unknown"),
    "III": AreaInfo("III", "Средиземное и Чёрное море", "Испания (Instituto Hidrografico de la Marina)",
                     "https://armada.defensa.gob.es/ihm/XML/navareas_crudo.xml", "experimental"),
    "IV": AreaInfo("IV", "Карибы, вост. побережье США", "США (NGA)",
                    "https://msi.nga.mil/NavWarnings", "live"),
    "V": AreaInfo("V", "Атлантика (Бразилия)", "Бразилия (DHN)",
                   "https://www1.mar.mil.br/dhn/index", "unknown"),
    "VI": AreaInfo("VI", "Атлантика (Аргентина)", "Аргентина (SHN)",
                    "http://www.hidro.gov.ar/", "unknown"),
    "VII": AreaInfo("VII", "Атлантика (ЮАР)", "ЮАР (SANHO)",
                     "http://www.sanho.co.za/", "unknown"),
    "VIII": AreaInfo("VIII", "Индийский океан (Индия)", "Индия (National Hydrographic Office)",
                      "https://hydrobharat.gov.in/navarea-warnings", "unknown"),
    "IX": AreaInfo("IX", "Аравийское море (Пакистан)", "Пакистан (Pakistan Navy)",
                    "https://www.paknavy.gov.pk/hydro/", "blocked"),
    "X": AreaInfo("X", "Австралия", "Австралия (AMSA)", None, "unknown"),
    "XI": AreaInfo("XI", "Япония", "Япония (Japan Coast Guard)",
                    "https://www1.kaiho.mlit.go.jp/", "blocked"),
    "XII": AreaInfo("XII", "Зап. побережье США", "США (NGA)",
                     "https://msi.nga.mil/NavWarnings", "live"),
    "XIII": AreaInfo("XIII", "Тихий океан (Россия)", "Россия",
                      None, "none"),
    "XIV": AreaInfo("XIV", "Новая Зеландия", "Новая Зеландия (Maritime NZ)",
                     "https://www.maritimenz.govt.nz/navarea", "blocked"),
    "XV": AreaInfo("XV", "Чили", "Чили (SHOA)",
                    "http://www.shoa.mil.cl/php/info_radioavisos.php?idioma=en", "unknown"),
    "XVI": AreaInfo("XVI", "Перу", "Перу (DHN)",
                     "https://www.dhn.mil.pe/portal/navarea/radioavisos-warnings", "live"),
    "XVII": AreaInfo("XVII", "Зап. Канада", "Канада (CCG)",
                      None, "unknown"),
    "XVIII": AreaInfo("XVIII", "Канадская Арктика", "Канада (CCG)",
                       None, "unknown"),
    "XIX": AreaInfo("XIX", "Норвегия", "Норвегия (Norwegian Coastal Administration)",
                     "http://www.navarea-xix.no/", "blocked"),
    "XX": AreaInfo("XX", "Баренцево море (Россия)", "Россия", None, "none"),
    "XXI": AreaInfo("XXI", "Дальний Восток (Россия)", "Россия", None, "none"),
    "HYDROLANT": AreaInfo("HYDROLANT", "Атлантика (доп. от NGA)", "США (NGA)",
                           "https://msi.nga.mil/NavWarnings", "live"),
    "HYDROPAC": AreaInfo("HYDROPAC", "Тихий океан (доп. от NGA)", "США (NGA)",
                          "https://msi.nga.mil/NavWarnings", "live"),
}

# Какой класс-источник реально умеет скачивать/парсить каждый live/experimental район.
_nga = NgaSource()
_ukho = UkhoSource()
_spain = SpainIhmSource()
_peru = PeruDhnSource()

SOURCES: dict[str, WarningSource] = {
    "I": _ukho,
    "I-COASTAL": _ukho,
    "III": _spain,
    "IV": _nga,
    "XII": _nga,
    "HYDROLANT": _nga,
    "HYDROPAC": _nga,
    "XVI": _peru,
}

LIVE_AREAS = [code for code, info in AREAS.items() if info.status == "live"]
EXPERIMENTAL_AREAS = [code for code, info in AREAS.items() if info.status == "experimental"]
POLLABLE_AREAS = LIVE_AREAS + EXPERIMENTAL_AREAS  # то, что реально можно отслеживать автоматически


def area_choice_label(code: str) -> str:
    info = AREAS[code]
    icon = {"live": "🟢", "experimental": "🟡", "blocked": "🔒", "unknown": "❔", "none": "🚫"}[info.status]
    return f"{icon} {code} — {info.name}"
