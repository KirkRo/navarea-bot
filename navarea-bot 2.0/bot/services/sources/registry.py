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
    "I": AreaInfo("I", "Северо-восточная Атлантика, Северное море, Ла-Манш", "Великобритания (UKHO)",
                  "https://msi.admiralty.co.uk/RadioNavigationalWarnings", "live"),
    "I-COASTAL": AreaInfo("I-COASTAL", "Прибрежные предупреждения Великобритании (WZ)", "Великобритания (UKHO)",
                           "https://msi.admiralty.co.uk/RadioNavigationalWarnings", "live"),
    "II": AreaInfo("II", "Северо-восточная Атлантика (французская зона)", "Франция (SHOM)",
                   "https://gan.shom.fr/navarea/", "unknown"),
    "III": AreaInfo("III", "Средиземное море, Чёрное море, Азовское море", "Испания (Instituto Hidrografico de la Marina)",
                     "https://armada.defensa.gob.es/ihm/XML/navareas_crudo.xml", "experimental"),
    "IV": AreaInfo("IV", "Западная Атлантика (Карибы, восточное побережье США)", "США (NGA)",
                    "https://msi.nga.mil/NavWarnings", "live"),
    "V": AreaInfo("V", "Юго-западная Атлантика (Бразилия)", "Бразилия (DHN)",
                   "https://www1.mar.mil.br/dhn/index", "unknown"),
    "VI": AreaInfo("VI", "Юго-западная Атлантика (Аргентина)", "Аргентина (SHN)",
                    "http://www.hidro.gov.ar/", "unknown"),
    "VII": AreaInfo("VII", "Юго-восточная Атлантика (Южная Африка)", "ЮАР (SANHO)",
                     "http://www.sanho.co.za/", "unknown"),
    "VIII": AreaInfo("VIII", "Индийский океан (север)", "Индия (Naval Hydrographic Department)",
                      "http://www.hydrobharat.nic.in/", "unknown"),
    "IX": AreaInfo("IX", "Аравийское море, Персидский залив", "Пакистан (Pakistan Navy)",
                    "http://www.paknavy.gov.pk/hydro/", "unknown"),
    "X": AreaInfo("X", "Юго-восточная часть Индийского и западная часть Тихого океана (Австралия)",
                   "Австралия (AMSA)", None, "unknown"),
    "XI": AreaInfo("XI", "Северо-западная часть Тихого океана (Япония)", "Япония (Japan Coast Guard)",
                    "https://www1.kaiho.mlit.go.jp/", "blocked"),
    "XII": AreaInfo("XII", "Восточная часть Тихого океана (западное побережье США)", "США (NGA)",
                     "https://msi.nga.mil/NavWarnings", "live"),
    "XIII": AreaInfo("XIII", "Северная часть Тихого океана (российский сектор)", "Россия",
                      None, "none"),
    "XIV": AreaInfo("XIV", "Юго-западная часть Тихого океана (Новая Зеландия)", "Новая Зеландия (Maritime NZ)",
                     "https://www.maritimenz.govt.nz/navarea", "blocked"),
    "XV": AreaInfo("XV", "Юго-восточная часть Тихого океана (Чили)", "Чили (SHOA)",
                    "http://www.shoa.mil.cl/", "unknown"),
    "XVI": AreaInfo("XVI", "Юго-восточная часть Тихого океана (Перу)", "Перу (DHN)",
                     "https://www.dhn.mil.pe/radioavisos_warnings", "unknown"),
    "XVII": AreaInfo("XVII", "Северо-восточная часть Тихого океана (западная Канада)", "Канада (CCG)",
                      None, "unknown"),
    "XVIII": AreaInfo("XVIII", "Канадская Арктика / Гудзонов залив", "Канада (CCG)",
                       None, "unknown"),
    "XIX": AreaInfo("XIX", "Баренцево и Норвежское море", "Норвегия (Norwegian Coastal Administration)",
                     "http://www.navarea-xix.no/", "blocked"),
    "XX": AreaInfo("XX", "Баренцево море (российский сектор)", "Россия", None, "none"),
    "XXI": AreaInfo("XXI", "Дальний Восток (российский сектор)", "Россия", None, "none"),
    "HYDROLANT": AreaInfo("HYDROLANT", "Региональные предупреждения NGA, Атлантика", "США (NGA)",
                           "https://msi.nga.mil/NavWarnings", "live"),
    "HYDROPAC": AreaInfo("HYDROPAC", "Региональные предупреждения NGA, Тихий океан", "США (NGA)",
                          "https://msi.nga.mil/NavWarnings", "live"),
}

# Какой класс-источник реально умеет скачивать/парсить каждый live/experimental район.
_nga = NgaSource()
_ukho = UkhoSource()
_spain = SpainIhmSource()

SOURCES: dict[str, WarningSource] = {
    "I": _ukho,
    "I-COASTAL": _ukho,
    "III": _spain,
    "IV": _nga,
    "XII": _nga,
    "HYDROLANT": _nga,
    "HYDROPAC": _nga,
}

LIVE_AREAS = [code for code, info in AREAS.items() if info.status == "live"]
EXPERIMENTAL_AREAS = [code for code, info in AREAS.items() if info.status == "experimental"]
POLLABLE_AREAS = LIVE_AREAS + EXPERIMENTAL_AREAS  # то, что реально можно отслеживать автоматически


def area_choice_label(code: str) -> str:
    info = AREAS[code]
    icon = {"live": "🟢", "experimental": "🟡", "blocked": "🔒", "unknown": "❔", "none": "🚫"}[info.status]
    return f"{icon} NAVAREA {code} — {info.name}"
