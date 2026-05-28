"""
Recognition — Fueling Mock Service.

Gera dados determinísticos de demonstração para o módulo de controle de carregamento.
Usado apenas quando user_role == 'superadmin' (modo demo para apresentações).
Clientes comuns recebem dados reais do banco ou estado vazio.

Semente baseada na data atual → números estáveis durante o dia, mudam no seguinte.
Status das baias muda a cada 5 min baseado no epoch (comportamento natural).
"""
import random
import time
from datetime import date, timedelta
from typing import Any

# ── Dados fictícios estáveis ───────────────────────────────────────────────────

_BAY_NAMES = ["Baia 01", "Baia 02", "Baia 03", "Baia 04", "Baia 05", "Baia 06"]
_OPERATORS = ["Carlos Silva", "Ana Souza", "Pedro Alves", "Fernanda Lima", "João Costa", "Maria Ramos"]  # noqa: E501
_PLATES = ["ABC-1234", "DEF-5678", "GHI-9012", "JKL-3456", "MNO-7890", "PQR-2468"]
_NC_CAUSES = [
    {"name": "Item Danificado",       "value": 38},
    {"name": "Falha de Equipamento",  "value": 27},
    {"name": "Desvio de Procedimento","value": 22},
    {"name": "Outros",                "value": 13},
]
_BAY_STATUSES = ["active", "idle", "maintenance"]


def _day_seed() -> int:
    """Semente diária: inteiro derivado da data (ex: 20260504)."""
    return int(date.today().isoformat().replace("-", ""))


def _slot_seed() -> int:
    """Semente por slot de 5 minutos: muda a cada 300 segundos."""
    return int(time.time()) // 300


def generate_dashboard(period: str = "today") -> dict[str, Any]:
    """
    Gera KPIs + séries para o dashboard de carga e descarga.

    Args:
        period: 'today' | 'week' | 'month' — janela de tempo.

    Returns:
        Dict com kpis, top_baias_produtivas, top_baias_perda,
        series_operacoes_diarias, series_tempo_por_baia, pizza_causas_perda.
    """
    rng = random.Random(_day_seed())  # noqa: S311

    # Multiplicadores por período
    multiplier = {"today": 1, "week": 7, "month": 30}.get(period, 1)
    days = {"today": 1, "week": 7, "month": 30}.get(period, 1)

    total_carregado = rng.randint(120, 180) * multiplier
    total_itens = rng.randint(800, 1_400) * multiplier
    itens_nc = rng.randint(8, 25) * multiplier
    taxa_nc = round((itens_nc / total_itens) * 100, 2) if total_itens else 0
    tempo_medio = round(rng.uniform(22, 38), 1)
    eventos_nc = rng.randint(3, 12) * multiplier
    taxa_ocupacao = round(rng.uniform(62, 91), 1)

    # Top baias produtivas (itens decrescente)
    bay_itens = sorted(
        [{"baia": n, "itens": rng.randint(80, 200) * multiplier}
         for n in _BAY_NAMES],
        key=lambda x: x["itens"], reverse=True,
    )
    top_baias_produtivas = bay_itens[:3]

    # Top baias com maior não-conformidade
    bay_losses = sorted(
        [{"baia": n, "perda": rng.randint(2, 15) * multiplier} for n in _BAY_NAMES],
        key=lambda x: x["perda"], reverse=True,
    )
    top_baias_perda = bay_losses[:3]

    # Série operações diárias (últimos `days` dias)
    today = date.today()
    series_operacoes = []
    for i in range(days):
        day = today - timedelta(days=days - 1 - i)
        ops = rng.randint(100, 300)
        series_operacoes.append({"dia": day.strftime("%d/%m"), "operacoes": ops})

    # Série tempo médio por baia
    series_tempo = [
        {"baia": n, "tempo": round(rng.uniform(18, 45), 1)}
        for n in _BAY_NAMES
    ]

    return {
        "kpis": {
            "total_carregado": total_carregado,
            "tempo_medio_minutos": tempo_medio,
            "total_itens_movimentados": total_itens,
            "itens_nao_conformes": itens_nc,
            "taxa_nao_conformidade": taxa_nc,
            "eventos_nao_conformidade": eventos_nc,
            "taxa_ocupacao_percent": taxa_ocupacao,
        },
        "top_baias_produtivas": top_baias_produtivas,
        "top_baias_perda": top_baias_perda,
        "series_operacoes_diarias": series_operacoes,
        "series_tempo_por_baia": series_tempo,
        "pizza_causas_perda": _NC_CAUSES,
    }


def generate_bays() -> list[dict[str, Any]]:
    """
    Gera lista das 6 baias com status dinâmico (muda a cada 5 min).

    Returns:
        Lista de dicts com id, nome, status, operador, placa, total_itens, progresso.
    """
    slot_rng = random.Random(_slot_seed())  # noqa: S311
    day_rng = random.Random(_day_seed())   # noqa: S311

    bays = []
    for i, name in enumerate(_BAY_NAMES):
        status = slot_rng.choice(_BAY_STATUSES)
        operator = day_rng.choice(_OPERATORS) if status == "active" else None
        plate = day_rng.choice(_PLATES) if status == "active" else None
        total_itens = day_rng.randint(20, 120) if status == "active" else 0
        progress = round(day_rng.uniform(10, 95)) if status == "active" else 0

        bays.append({
            "id": i + 1,
            "nome": name,
            "status": status,
            "operador": operator,
            "placa": plate,
            "total_itens": total_itens,
            "progresso": progress,
        })

    return bays


def get_bay(bay_id: int) -> dict[str, Any] | None:
    """Retorna uma baia específica pelo id (1-based). None se não existir."""
    bays = generate_bays()
    matches = [b for b in bays if b["id"] == bay_id]
    return matches[0] if matches else None
