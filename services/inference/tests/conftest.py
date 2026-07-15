"""Torna o pacote `inference` importável rodando pytest da raiz do repo.

O CI roda `pytest services/inference/tests/` a partir da raiz — este
conftest insere services/inference/ no sys.path (padrão análogo ao das
suítes de pre-annotation-service e training/vast).
"""
import sys
from pathlib import Path

_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ROOT))
