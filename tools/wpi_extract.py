"""
Достаёт справочник портов из World Port Index (NGA Pub. 150) в JSON.

Запуск разовый, при выходе нового издания:

    python tools/wpi_extract.py "C:\\путь\\Pub150bk.pdf" bot/data/wpi_ports.json

Pub. 150 -- работа правительства США, авторские права на неё не заявлены
(«NO COPYRIGHT CLAIMED UNDER TITLE 17 U.S.C.» на титуле), поэтому данные
можно возить с собой в приложении.

Как устроен разбор. В текстовом слое строка порта выглядит так:

    11205 PUERTO YABUCOA PR 1803N 06550W CP05 25661 V OR F Y G E H H 01 L Y Y

Позиции колонок в тексте не сохраняются, а пропущенные значения просто
исчезают, поэтому разбор идёт не по местам, а по якорям. Надёжно
опознаются номер, название, страна и координаты. Дальше ищется
двухбуквенный код типа гавани (Cn, Cb, Or, Rn и прочие) -- он уникален
среди однобуквенных кодов и служит точкой отсчёта для укрытия и величины
прилива. Что не опознано, в JSON не попадает: пустое поле честнее
угаданного.
"""
from __future__ import annotations

import io
import json
import re
import sys

# Типы гавани из CODE KEY публикации
HARBOR_TYPES = {"CN": "прибрежная природная", "CB": "прибрежная с молом",
                "CT": "прибрежная со шлюзом", "RN": "речная природная",
                "RB": "речной бассейн", "RT": "речная со шлюзом",
                "LC": "озеро или канал", "OR": "открытый рейд",
                "TH": "тайфунная гавань"}
HARBOR_SIZES = {"L": "большая", "M": "средняя", "S": "малая", "V": "очень малая"}
SHELTER = {"E": "отличное", "G": "хорошее", "F": "среднее", "P": "плохое", "N": "нет"}

ROW = re.compile(
    r"^(\d{4,5})\s+"                 # номер по указателю
    r"([A-Z0-9''.\-/() ]+?)\s+"      # название порта
    r"([A-Z]{2})\s+"                 # код страны
    r"(\d{4})([NS])\s+"              # широта ГГММ
    r"(\d{5})([EW])"                 # долгота ГГГММ
    r"(.*)$"                         # хвост с кодами
)
TAIL_TYPE = re.compile(r"\b(CN|CB|CT|RN|RB|RT|LC|OR|TH)\b")


def _deg(value: str, hemi: str, wide: bool) -> float:
    """ГГММ или ГГГММ в градусы. Долгота шире широты на разряд."""
    cut = 3 if wide else 2
    degrees = int(value[:cut])
    minutes = int(value[cut:])
    out = degrees + minutes / 60.0
    return -out if hemi in ("S", "W") else out


def parse_row(line: str) -> dict | None:
    m = ROW.match(line.strip())
    if not m:
        return None
    index, name, country, lat_v, lat_h, lon_v, lon_h, tail = m.groups()

    name = " ".join(name.split()).title()
    if len(name) < 2:
        return None

    port = {
        "id": int(index),
        "name": name,
        "cc": country,
        "lat": round(_deg(lat_v, lat_h, wide=False), 4),
        "lon": round(_deg(lon_v, lon_h, wide=True), 4),
    }

    tokens = tail.split()
    t = TAIL_TYPE.search(tail)
    if t:
        port["type"] = t.group(1)
        pos = tokens.index(t.group(1)) if t.group(1) in tokens else -1
        # Размер гавани стоит прямо перед типом, укрытие сразу после него.
        if pos > 0 and tokens[pos - 1] in HARBOR_SIZES:
            port["size"] = tokens[pos - 1]
        if pos >= 0 and pos + 1 < len(tokens) and tokens[pos + 1] in SHELTER:
            port["shelter"] = tokens[pos + 1]

    # Величина прилива печатается двузначным числом в футах и стоит после
    # букв глубин. Номер карты тоже число, но он идёт до типа гавани,
    # поэтому ищем только в хвосте после него.
    after = tokens[tokens.index(t.group(1)) + 1:] if t and t.group(1) in tokens else []
    tide = [tok for tok in after if re.fullmatch(r"\d{2}", tok)]
    if tide:
        feet = int(tide[-1])
        if feet:
            port["tide_ft"] = feet
            port["tide_m"] = round(feet * 0.3048, 1)
    return port


def main(pdf_path: str, out_path: str) -> None:
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    ports: dict[int, dict] = {}
    for page in reader.pages:
        for line in (page.extract_text() or "").splitlines():
            row = parse_row(line)
            if row:
                # Каждый порт напечатан дважды: основные данные и услуги.
                # Строка услуг названия не содержит и сюда не проходит.
                ports.setdefault(row["id"], row)

    data = sorted(ports.values(), key=lambda p: p["id"])
    io.open(out_path, "w", encoding="utf-8", newline="").write(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    with_tide = sum(1 for p in data if p.get("tide_ft"))
    with_type = sum(1 for p in data if p.get("type"))
    print(f"портов: {len(data)}, с типом гавани: {with_type}, с величиной прилива: {with_tide}")
    print(f"записано: {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
