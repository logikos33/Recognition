"""conftest.py — adiciona venv/site-packages ao sys.path para testes locais.

Necessário quando pytest é invocado com Python diferente do venv do projeto.
O driver usa _eval_env() que resolve isso em CI; aqui fazemos o equivalente.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_VENV_SITE = _ROOT / "venv" / "lib"

# Adiciona o primeiro subdiretório de lib/ (ex: python3.14/site-packages)
for _py in _VENV_SITE.iterdir():
    _sp = _py / "site-packages"
    if _sp.is_dir() and str(_sp) not in sys.path:
        sys.path.insert(0, str(_sp))
        break
