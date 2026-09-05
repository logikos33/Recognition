"""O relatório de compliance para de afirmar 100 % quando não apurou nada.

Irmã do `test_modules_stats_score_honesto.py`: o Dashboard e a tela de
Relatórios mostram o MESMO score de conformidade por caminhos diferentes
(`GET /api/modules/epi/stats` e `GET /api/reports/compliance`). O guard do
Dashboard não alcança este, que tinha o defeito na forma mais cara:

  · `except Exception: compliance_rate = 100.0` — a agregação cair devolvia o
    relatório PERFEITO. Foi exatamente esse `except` que engoliu o TypeError
    do PR #75 por semanas (ver `tests/integration/test_compliance_report_aggregation.py`);
  · zero alerta na janela também virava 100 — e `count_since`/`count_in_window`
    contam TODO alerta EPI (violação E conformidade), então zero significa que
    NADA chegou: ausência de medição, não conformidade.

E este score não fica só na tela: `generate()` imprime num PDF que sobe para o
R2 sob `tenant/<id>/reports/…` e é gerado todo dia pelo job de compliance. Um
"Taxa de Conformidade: 100,0%" arquivado por causa de um banco fora do ar é
prova de auditoria fabricada.

Aqui só o `_aggregate` (e a linha do PDF) — o resto de `generate` (R2,
reportlab) tem cobertura própria em `tests/unit/api/test_compliance_reports.py`.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.domain.services.compliance_report_service import ComplianceReportService

# Literais de propósito, NÃO importados do módulo sob teste: importar as
# constantes faria o vermelho vir de um ImportError — prova falsa, que passa
# a impressão de cobrir a asserção sem nunca exercitá-la. Assim o teste falha
# na linha que interessa, com a develop no lugar.
RAZAO_SEM_SINAL = "sem_sinal_no_periodo"
RAZAO_NAO_APURADA = "nao_foi_possivel_apurar"

TENANT = "11111111-1111-1111-1111-111111111111"
FIM = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
INICIO = FIM - timedelta(hours=2)


class _RepoFake:
    """Repositório mínimo — só o que `_aggregate` chama."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.janelas: list[tuple] = []

    def count_in_window(self, tenant_id, from_ts, to_ts, module_code=None, camera_ids=None):
        self.janelas.append((tenant_id, from_ts, to_ts, module_code))
        return self.total

    def count_since(self, tenant_id, module_code, since):
        """O caminho da develop, sem limite superior — mantido no dublê para
        que o vermelho destes testes venha da ASSERÇÃO e não de um AttributeError."""
        return self.total

    def count_by_hour(self, tenant_id, start, end):
        return []

    def list_with_filters(self, **kwargs):
        return {"items": [{"camera_id": "cam-1"}] * self.total}


def _agregar(repo):
    with patch(
        "app.domain.services.compliance_report_service._get_alert_repo",
        return_value=repo,
    ):
        return ComplianceReportService()._aggregate(TENANT, "dia", INICIO, FIM)


class TestScoreDoRelatorioSobreOVazio:
    def test_sem_alerta_nenhum_na_janela_o_score_vira_null(self) -> None:
        """Zero evento = zero hora observada. Não é 100 %."""
        resumo = _agregar(_RepoFake(total=0))
        assert resumo["compliance_rate"] is None, (
            "zero alerta no período virou nota máxima de conformidade — é "
            "ausência de medição, não conformidade"
        )
        assert resumo["compliance_reason"] == RAZAO_SEM_SINAL
        assert resumo["total_violations"] == 0

    def test_agregacao_que_falha_nao_vira_relatorio_perfeito(self) -> None:
        """Banco caindo devolvia 100 %. Agora devolve `None` + razão."""

        class _RepoQuebrado:
            def count_in_window(self, *a, **k):
                raise RuntimeError("connection pool exhausted")

        resumo = _agregar(_RepoQuebrado())
        assert resumo["compliance_rate"] is None, (
            "consulta que falhou devolveu 100 % de conformidade — o relatório "
            "mentia exatamente quando menos sabia"
        )
        assert resumo["compliance_reason"] == RAZAO_NAO_APURADA

    def test_com_alerta_na_janela_o_score_e_calculado_normalmente(self) -> None:
        """O guard não pode engolir o caminho feliz: 3 alertas em 2 h → 25 %."""
        resumo = _agregar(_RepoFake(total=3))
        assert resumo["compliance_rate"] == 25.0
        assert resumo["compliance_reason"] is None

    def test_o_periodo_fechado_para_de_contar_evento_de_fora_da_janela(self) -> None:
        """`count_since` ignorava `end`: "mês anterior" somava até HOJE."""
        repo = _RepoFake(total=3)
        _agregar(repo)
        assert repo.janelas, "a contagem não passou por uma janela com fim"
        _, de, ate, modulo = repo.janelas[0]
        assert (de, ate, modulo) == (INICIO, FIM, "epi")


class TestPdfNaoImprimeScoreQueNaoExiste:
    """O PDF vai para o cliente e fica arquivado no R2 — o job diário gera um
    por dia. Nunca pode imprimir "100,0%" para um score que não existe.

    Sem tocar em reportlab de propósito: outros testes da suíte substituem
    `reportlab` em `sys.modules`, e um teste que só passa sozinho não é teste.
    """

    def test_score_nulo_por_falha_sai_como_travessao_com_a_razao(self) -> None:
        from app.domain.services.compliance_report_service import valor_conformidade

        valor = valor_conformidade(
            {"compliance_rate": None, "compliance_reason": RAZAO_NAO_APURADA}
        )
        assert "100" not in valor, f"o PDF arquivou uma conformidade inventada: {valor!r}"
        assert valor.startswith("—")
        assert "não foi possível apurar" in valor

    def test_score_nulo_por_periodo_vazio_diz_que_nao_havia_o_que_apurar(self) -> None:
        from app.domain.services.compliance_report_service import valor_conformidade

        valor = valor_conformidade(
            {"compliance_rate": None, "compliance_reason": RAZAO_SEM_SINAL}
        )
        assert valor.startswith("—")
        assert "sem evento no período" in valor

    def test_score_apurado_continua_saindo_como_porcentagem(self) -> None:
        from app.domain.services.compliance_report_service import valor_conformidade

        assert valor_conformidade({"compliance_rate": 82.4, "compliance_reason": None}) == "82.4%"
