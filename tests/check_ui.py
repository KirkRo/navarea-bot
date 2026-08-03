"""
Проверка целостности интерфейса.

Появилась после того, как в CSS попала лишняя кавычка перед правилом
.hidden -- правило стало невалидным, разделы перестали скрываться, и
нижнее меню внешне выглядело нерабочим, хотя код переключения был цел.
Такие вещи глазами не видно, поэтому проверяем машинно.

Запуск: python tests/check_ui.py
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, ".")
from bot.miniapp import MINI_APP_HTML as H  # noqa: E402

problems: list[str] = []

css = H[H.index("<style>") + 7 : H.index("</style>")]
body = H[H.index("</style>") : H.rindex("<script>")]
js = H[H.rindex("<script>") + 8 : H.rindex("</script>")]

# 1. структура документа
if not H.strip().endswith("</html>"):
    problems.append("документ не заканчивается на </html>")
if H.count("</script>") != 3:
    problems.append(f"закрывающих <script> должно быть 3, найдено {H.count('</script>')}")

# 2. баланс скобок в стилях
if css.count("{") != css.count("}"):
    problems.append(f"в CSS не сходятся скобки: {css.count('{')} против {css.count('}')}")

# 3. обломки от вставок (кавычки в начале строки стиля или разметки)
for name, chunk in (("CSS", css), ("разметке", body)):
    for i, line in enumerate(chunk.split("\n"), 1):
        st = line.strip()
        if st.startswith('"') or st.startswith("'''") or '"""' in st:
            problems.append(f"обломок вставки в {name}, строка {i}: {st[:60]}")

# 4. правила, без которых интерфейс ломается молча
critical = {
    ".hidden{display:none!important}": "разделы не будут скрываться",
    ".tabs{": "нижнее меню без оформления",
    ".tab{": "кнопки меню без оформления",
    ".chip{": "кнопки-фильтры без оформления",
}
for rule, why in critical.items():
    if rule not in css:
        problems.append(f"нет правила {rule} -- {why}")

# 5. все классы из разметки должны быть описаны
declared = set(re.findall(r"\.([a-zA-Z][\w-]*)", css))
used: set[str] = set()
for m in re.finditer(r"class=[\"']([^\"']+)[\"']", H):
    for c in m.group(1).split():
        if not c.startswith("${") and "$" not in c:
            used.add(c)
missing = sorted(c for c in used if c not in declared and len(c) > 2)
if missing:
    problems.append("классы без стилей: " + ", ".join(missing))

# 6. анимации, на которые ссылаются стили, должны существовать
for anim in set(re.findall(r"animation:\s*([a-zA-Z][\w-]*)", css)) - {"none", "inherit", "initial", "unset"}:
    if f"@keyframes {anim}" not in css:
        problems.append(f"нет описания анимации @keyframes {anim}")

# 7. каждой вкладке меню должен соответствовать раздел
groups = set(re.findall(r'data-g="([a-z]+)"', H))
if groups != {"home", "tools", "map", "profile"}:
    problems.append(f"неожиданный набор вкладок: {sorted(groups)}")

if problems:
    print("НАЙДЕНЫ ПРОБЛЕМЫ:")
    for p in problems:
        print("  !!", p)
    sys.exit(1)

print("интерфейс цел:")
print(f"  правил в CSS: {css.count('{')}")
print(f"  классов описано: {len(declared)}, использовано: {len(used)}")
print(f"  размер приложения: {len(H)} символов")
