"""Тесты берут SymPy из runtime/, то есть ровно ту версию, что работает в браузере."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
try:
    import sympy  # noqa: F401
except ImportError:
    for name in ("mpmath", "sympy"):
        sys.path.insert(0, str(ROOT / "runtime" / f"{name}.zip"))
