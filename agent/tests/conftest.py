"""Adiciona agent/ ao sys.path para importar src.* nos testes."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
