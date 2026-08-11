# Корень проекта берём от самого файла, чтобы проверку можно было запустить
# просто как `python tests/checks/<файл>.py` из любой папки.
import pathlib as _pl, sys as _sys
_ROOT = str(_pl.Path(__file__).resolve().parents[2])
if len(_sys.argv) < 2:
    _sys.argv.append(_ROOT)
import ast, io, sys, pathlib

root = pathlib.Path(sys.argv[1])
bad = 0
for f in sorted(root.rglob("*.py")):
    if any(p in f.parts for p in ("__pycache__", ".venv")):
        continue
    rel = f.relative_to(root)
    try:
        ast.parse(io.open(f, encoding="utf-8").read(), filename=str(f))
        print("OK  ", rel)
    except SyntaxError as e:
        bad += 1
        print("FAIL", rel, "line", e.lineno, e.msg)
print("---", "problems:", bad)
sys.exit(1 if bad else 0)
