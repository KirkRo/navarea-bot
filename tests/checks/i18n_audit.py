# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
"""
Что в приложении осталось непереведённым.

Собирает из mini app все строки с кириллицей -- из разметки, из строковых
литералов JS и из атрибутов -- и сверяет со словарём DICT. Всё, чего в
словаре нет, попадает в отчёт: это и есть то, что пользователь увидит
по-русски при английском интерфейсе.
"""
import json, pathlib, re, sys
from collections import Counter

src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
tok = 'MINI_APP_HTML = r"""'
i = src.index(tok) + len(tok)
html = src[i:src.rindex('"""')]

CYR = re.compile(r"[А-Яа-яЁё]")

# --- словарь ---
dict_keys = set()
for m in re.finditer(r"'((?:[^'\\]|\\.)*)'\s*:\s*'((?:[^'\\]|\\.)*)'", html):
    k = m.group(1)
    if CYR.search(k):
        dict_keys.add(k)
# многострочные значения: 'ключ':\n  'значение'
for m in re.finditer(r"'((?:[^'\\]|\\.)*)'\s*:\s*\n\s*'", html):
    if CYR.search(m.group(1)):
        dict_keys.add(m.group(1))

found = Counter()
where = {}


def add(s, kind):
    s = s.strip()
    if not s or not CYR.search(s):
        return
    if len(s) > 400:
        return
    found[s] += 1
    where.setdefault(s, kind)


# --- строковые литералы JS (одинарные и двойные кавычки) ---
for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'", html):
    add(m.group(1), "js")
for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"', html):
    add(m.group(1), "js")

# --- атрибуты разметки, которые видит пользователь ---
for attr in ("placeholder", "title", "aria-label", "alt"):
    for m in re.finditer(attr + r'="([^"]*)"', html):
        add(m.group(1), "attr:" + attr)

# --- текстовые узлы разметки ---
body = html
for m in re.finditer(r">([^<>{}`$]+)<", body):
    for part in re.split(r"[\n]+", m.group(1)):
        add(part, "html")

# --- текст внутри шаблонных строк между тегами ---
for m in re.finditer(r">([^<>`]{2,120})<", body):
    t = m.group(1)
    if "${" in t:
        for part in re.split(r"\$\{[^}]*\}", t):
            add(part, "tpl")

missing = {s: n for s, n in found.items() if s not in dict_keys}

# служебное отсеиваем: чистая пунктуация, одиночные символы, комментарии кода
def useful(s):
    if len(s) < 2:
        return False
    if s.startswith(("--", "/*", "*")):
        return False
    if not re.search(r"[А-Яа-яЁё]{2}", s):
        return False
    return True


missing = {s: n for s, n in missing.items() if useful(s)}
out = sorted(missing.items(), key=lambda kv: (-kv[1], kv[0]))

pathlib.Path(sys.argv[2]).write_text(
    json.dumps([s for s, _ in out], ensure_ascii=False, indent=1), encoding="utf-8")

print("strings with cyrillic:", len(found))
print("in dictionary:", len(dict_keys))
print("MISSING:", len(out))
