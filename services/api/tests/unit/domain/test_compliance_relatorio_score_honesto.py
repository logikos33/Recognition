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

RAZAO_SEM_CAMERA = "sem_cameras_ativas"

TENANT = "11111111-1111-1111-1111-111111111111"
FIM = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
INICIO = FIM - timedelta(hours=2)
#: Câmeras ativas do módulo EPI da RVB no DEV — o denominador real do score.
CAMERAS_RVB = 17


class _RepoFake:
    """Repositório mínimo — só o que `_aggregate` chama.

    `total` = TODO alerta EPI da janela (violação E conformidade), que é o que
    `count_in_window` devolve. `horas_violacao` = horas-câmera COM VIOLAÇÃO de
    verdade, o numerador que a ADR-0065 já usava no Dashboard. Os dois são
    separados de propósito: é a distância entre eles que a issue #797 mede.
    """

    def __init__(self, total: int, horas_violacao: int = 0) -> None:
        self.total = total
        self.horas_violacao = horas_violacao
        self.janelas: list[tuple] = []
        self.janelas_violacao: list[tuple] = []

    def count_in_window(self, tenant_id, from_ts, to_ts, module_code=None, camera_ids=None):
        self.janelas.append((tenant_id, from_ts, to_ts, module_code))
        return self.total

    def count_since(self, tenant_id, module_code, since):
        """O caminho da develop, sem limite superior — mantido no dublê para
        que o vermelho destes testes venha da ASSERÇÃO e não de um AttributeError."""
        return self.total

    def camera_hours_with_violation(self, tenant_id, module_code, since, until=None):
        self.janelas_violacao.append((tenant_id, module_code, since, until))
        return self.horas_violacao

    def count_by_hour(self, tenant_id, start, end):
        return []

    def list_with_filters(self, **kwargs):
        return {"items": [{"camera_id": "cam-1"}] * self.total}


class _CamerasFake:
    def __init__(self, ativas: int) -> None:
        self.ativas = ativas

    def count_by_status(self, tenant_id, module_code, status):
        return self.ativas if status == "active" else 0


def _agregar(repo, cameras_ativas: int = CAMERAS_RVB, inicio=INICIO, fim=FIM):
    with patch(
        "app.domain.services.compliance_report_service._get_alert_repo",
        return_value=repo,
    ), patch(
        "app.domain.services.compliance_report_service._get_camera_repo",
        return_value=_CamerasFake(cameras_ativas),
    ):
        return ComplianceReportService()._aggregate(TENANT, "dia", inicio, fim)


def _score_do_dashboard(horas_violacao: int, cameras_ativas: int, horas: float) -> float:
    """A fórmula do cartão do Dashboard, escrita À MÃO aqui.

    Cópia deliberada de `module_service.get_stats` (não um import): se algum dia
    as duas fórmulas divergirem de novo, é ESTE teste que tem de ficar vermelho,
    e ele não pode ficar verde só porque leu a fórmula do lado errado.
    """
    horas_camera = cameras_ativas * horas
    return 100.0 * (1 - min(horas_violacao, horas_camera) / horas_camera)


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
        """O guard não pode engolir o caminho feliz.

        3 alertas na janela, 1 hora-câmera com violação, 17 câmeras ativas, 2 h:
        100 × (1 − 1/34) = 97,06.
        """
        resumo = _agregar(_RepoFake(total=3, horas_violacao=1))
        assert resumo["compliance_rate"] == 97.06
        assert resumo["compliance_reason"] is None

    def test_sem_camera_ativa_o_denominador_e_zero_e_o_score_nao_existe(self) -> None:
        """Zero câmera ativa = zero hora-câmera monitorada. Não é 100 %."""
        resumo = _agregar(_RepoFake(total=9, horas_violacao=2), cameras_ativas=0)
        assert resumo["compliance_rate"] is None
        assert resumo["compliance_reason"] == RAZAO_SEM_CAMERA

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


class TestTaxaDeConformidadeNaoCaiQuandoOEpiEUsado:
    """ISSUE #797 — a Taxa de Conformidade DESPENCAVA quando o EPI era USADO.

    A fórmula antiga era `100 − (TODOS os alertas ÷ horas) × 50`, e
    `count_in_window` não filtra tipo. Cada evento de **EPI EM USO** — o
    resultado bom, 3.881 dos 5.092 do acervo da RVB — abaixava a nota. Medido
    no DEV, janelas de 7 dias (168 h):

        04/08 → 11/08 · 3.801 alertas · proxy 22,6/h → PDF imprimia **0,0 %**
        25/08 → 01/09 ·    89 alertas · proxy 0,53/h → PDF imprimia  73,5 %
        29/08 → 05/09 ·   127 alertas · proxy 0,76/h → PDF imprimia  62,2 %

    Repare no absurdo do meio: 25/08 é "melhor" que 29/08 só porque chegaram
    MENOS eventos — não porque houve menos violação. E na semana de 04/08 o
    Dashboard, sobre os mesmos dados, mostrava **92 · Conforme** (#789). Dois
    números com o MESMO rótulo, ~90 pontos de distância, direções opostas — e o
    de 0,0 % é o que vira PDF de auditoria no R2.
    """

    SEMANA = 168.0

    def _semana(self, total: int, horas_violacao: int):
        fim = FIM
        inicio = fim - timedelta(hours=int(self.SEMANA))
        return _agregar(
            _RepoFake(total=total, horas_violacao=horas_violacao), inicio=inicio, fim=fim
        )

    def test_semana_de_3801_eventos_quase_todos_conformidade_nao_da_zero(self) -> None:
        """A semana real de 04/08: 3.801 alertas EPI, 31 horas-câmera com
        violação de verdade. A fórmula antiga imprimia 0,0 %."""
        resumo = self._semana(total=3801, horas_violacao=31)
        assert resumo["compliance_rate"] is not None
        assert resumo["compliance_rate"] > 90.0, (
            "a semana em que o EPI foi mais USADO ainda sai como a pior nota do "
            f"relatório: {resumo['compliance_rate']}"
        )

    def test_mais_conformidade_com_a_MESMA_violacao_nao_abaixa_a_nota(self) -> None:
        """O coração da inversão, isolado: MESMAS horas-câmera com violação,
        acervo 40× maior porque o EPI foi usado. A nota tem de ser IGUAL."""
        pouco = self._semana(total=95, horas_violacao=31)
        muito = self._semana(total=3801, horas_violacao=31)
        assert pouco["compliance_rate"] == muito["compliance_rate"], (
            "usar EPI mudou a Taxa de Conformidade — é exatamente a inversão "
            f"da #797: {pouco['compliance_rate']} vs {muito['compliance_rate']}"
        )

    def test_a_nota_piora_quando_a_VIOLACAO_aumenta_e_so_por_isso(self) -> None:
        menos = self._semana(total=500, horas_violacao=10)
        mais = self._semana(total=500, horas_violacao=200)
        assert mais["compliance_rate"] < menos["compliance_rate"]

    def test_relatorio_e_dashboard_usam_a_MESMA_formula(self) -> None:
        """Uma fonte de verdade. A janela pode diferir; a conta, não."""
        resumo = self._semana(total=3801, horas_violacao=31)
        esperado = _score_do_dashboard(31, CAMERAS_RVB, self.SEMANA)
        assert resumo["compliance_rate"] == round(esperado, 2), (
            "a tela de Relatórios voltou a ter fórmula própria — é o defeito "
            "que faz o PDF discordar do painel com o mesmo rótulo"
        )

    def test_a_janela_do_relatorio_e_FECHADA_dos_dois_lados(self) -> None:
        """Sem limite superior, o "mês anterior" contaria violação até AGORA —
        o mesmo defeito que `count_since` → `count_in_window` já corrigiu na
        contagem de eventos."""
        repo = _RepoFake(total=500, horas_violacao=7)
        inicio = FIM - timedelta(hours=168)
        _agregar(repo, inicio=inicio, fim=FIM)
        assert repo.janelas_violacao, "as horas de violação não passaram por janela nenhuma"
        _, modulo, de, ate = repo.janelas_violacao[0]
        assert (modulo, de, ate) == ("epi", inicio, FIM)

    def test_o_payload_publica_de_onde_a_taxa_veio(self) -> None:
        """Numerador e denominador saem no envelope: a tela pode mostrar a
        conta em vez de pedir confiança."""
        resumo = self._semana(total=500, horas_violacao=7)
        assert resumo["violation_hours"] == 7
        assert resumo["period_hours"] == self.SEMANA
        # A chave antiga continua sendo TODO evento do período — é o que
        # `Relatorios.tsx` imprime como "N eventos no período" e o que ela usa
        # para decidir se o período está vazio.
        assert resumo["total_violations"] == 500
