"""Integração: DOIS anotadores, o MESMO frame — Postgres REAL (#801).

Gêmeo de `test_verification_veredito_concorrente.py` (onda 1) para o Estúdio.
A corrida mora na transação de `save_batch` (SELECT ... FOR UPDATE + confere
versão + DELETE + INSERT) e no que o Postgres faz com duas transações
concorrentes na MESMA linha — nada disso um mock alcança.

O que este arquivo prova:

  1. O segundo save NÃO apaga as caixas do primeiro: recebe `ConflictError`
     (409) dizendo quem salvou e quando, e o banco continua com o trabalho do
     PRIMEIRO, `created_by` incluído.
  2. Sob concorrência de verdade — duas conexões com as transações
     SOBREPOSTAS À FORÇA (uma é pausada dentro da transação, depois de ler a
     versão) — EXATAMENTE UM grava, e o frame termina com as caixas de um só,
     nunca uma mistura nem uma duplicação. Largada por `Barrier` não serve:
     medido, passava igual com e sem a trava.
  3. Re-salvar o PRÓPRIO trabalho continua permitido (o anotador corrige o
     que ele mesmo desenhou; é também o que evita 409 contra si mesmo depois
     de aceitar uma proposta).
  4. Sem `versao_esperada` (chamada interna/Celery) o comportamento antigo
     segue valendo — a guarda é opt-in.

Mata (sem esta suíte os três sobrevivem a lint, tipo e testes unitários):
  · tirar a conferência de versão de `save_batch` → o caso 1 volta a
    devolver `1` e a caixa do primeiro anotador some (é o #801 medido no DEV);
  · tirar o `SELECT ... FOR UPDATE` da linha do frame → o caso 2 passa a ter
    DOIS vencedores (as duas transações leem a MESMA versão antes de
    qualquer escrita) — exatamente o cenário da segunda (07/09), em que os
    três anotadores começam pelo mesmo primeiro frame VAZIO da fila, onde
    não existe linha de anotação para travar;
  · trocar a guarda por "versão diferente = 409" puro → o caso 3 quebra e o
    anotador não consegue mais corrigir a própria caixa.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

import threading
import time
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
    VERSAO_VAZIA,
)


def _caixa(class_name: str, cx: float, cy: float) -> dict:
    return {"class_id": 0, "class_name": class_name, "module_code": "epi",
            "x_center": cx, "y_center": cy, "width": 0.1, "height": 0.1}


# Os dois payloads do #801: A desenha "Protetor auditivo" no canto de cima,
# B desenha "Sem protetor de ouvido" no canto de baixo. Geometrias distintas
# de propósito — se as duas sobrevivessem, o frame teria as duas caixas.
CAIXA_DE_ANA = [_caixa("Protetor auditivo", 0.2, 0.2)]
CAIXA_DE_BRUNO = [_caixa("Sem protetor de ouvido", 0.8, 0.8)]


@pytest.fixture
def cenario(pg_raw, pg_pool, tenant_id):
    """Um frame NVR sem anotação nenhuma + dois anotadores do mesmo tenant.

    Frame VAZIO de propósito: é o caso real da issue (os anotadores abrem o
    MESMO primeiro item da fila) e o único em que não há linha de
    `frame_annotations` para servir de âncora de trava.
    """
    ana, bruno = str(uuid4()), str(uuid4())
    frame = str(uuid4())
    with pg_raw.cursor() as cur:
        for uid, nome in ((ana, "Ana Prado"), (bruno, "Bruno Lima")):
            cur.execute(
                "INSERT INTO public.users "
                "  (id, email, password_hash, name, role, tenant_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (uid, f"conc-{uid[:8]}@test.dev", "x", nome, "operator", tenant_id),
            )
        chave = f"training-images/{tenant_id}/nvr/{frame}.jpg"
        cur.execute(
            "INSERT INTO public.training_frames "
            "  (id, video_id, frame_number, filename, source, r2_key, tenant_id) "
            "VALUES (%s, NULL, %s, %s, %s, %s, %s)",
            (frame, 0, chave, "nvr", chave, tenant_id),
        )
    yield {"ana": ana, "bruno": bruno, "frame": frame}
    with pg_raw.cursor() as cur:
        # training_frames antes dos tenants (FK não-cascata); frame_annotations
        # cai em cascata com o frame.
        cur.execute(
            "DELETE FROM public.training_frames WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute("DELETE FROM public.users WHERE tenant_id = %s", (tenant_id,))


def _caixas_no_banco(pg_raw, frame_id: str) -> list[dict]:
    with pg_raw.cursor() as cur:
        cur.execute(
            "SELECT class_name, created_by FROM frame_annotations "
            "WHERE frame_id = %s ORDER BY class_name",
            (frame_id,),
        )
        return [dict(linha) for linha in cur.fetchall()]


# ---------------------------------------------------------------------------
# 1. O segundo save não apaga o do primeiro
# ---------------------------------------------------------------------------

def test_segundo_save_recebe_conflito_e_nao_apaga_o_do_primeiro(
    pg_raw, pg_pool, cenario
):
    """A sequência EXATA medida no DEV em 05/09 (frame 2e9dcee9).

    ANTES da guarda os dois POSTs voltavam 200 {"saved":1} e o GET seguinte
    mostrava SÓ a caixa de Bruno — a de Ana evaporava sem aviso nenhum.
    """
    repo = AnnotationRepository(pg_pool)

    # Os dois abriram o frame VAZIO: a versão que ambos leram é a mesma.
    versao_lida_pelos_dois = repo.versao_do_frame(cenario["frame"])
    assert versao_lida_pelos_dois == VERSAO_VAZIA

    assert repo.save_batch(
        cenario["frame"], CAIXA_DE_ANA, user_id=cenario["ana"],
        versao_esperada=versao_lida_pelos_dois,
    ) == 1

    with pytest.raises(ConflictError) as excecao:
        repo.save_batch(
            cenario["frame"], CAIXA_DE_BRUNO, user_id=cenario["bruno"],
            versao_esperada=versao_lida_pelos_dois,
        )

    # Nominal e legível: NOME de quem salvou e quando — é o que Bruno lê na
    # tela. Nunca o UUID (id interno), nunca "409"/"conflict".
    assert excecao.value.status_code == 409
    assert "Ana Prado" in excecao.value.message
    assert cenario["ana"] not in excecao.value.message
    assert "agora há pouco" in excecao.value.message

    # E o banco: o trabalho de Ana intacto, nada do Bruno.
    caixas = _caixas_no_banco(pg_raw, cenario["frame"])
    assert [c["class_name"] for c in caixas] == ["Protetor auditivo"]
    assert str(caixas[0]["created_by"]) == cenario["ana"]


# ---------------------------------------------------------------------------
# 2. Concorrência real: duas threads, duas conexões, largada simultânea
# ---------------------------------------------------------------------------

def test_duas_transacoes_sobrepostas_no_mesmo_frame_apenas_uma_grava(
    pg_raw, pg_pool, cenario
):
    """A corrida de verdade, com sobreposição FORÇADA — não "com sorte".

    Uma `Barrier` não basta: as duas transações duram microssegundos e quase
    nunca se sobrepõem de fato. Medido: com `Barrier` este teste passava
    IGUAL com e sem a trava — mediria nada. Aqui Ana é pausada DENTRO da
    transação, logo depois de ler a versão, e Bruno roda a transação inteira
    nesse intervalo. A sobreposição é garantida, não sorteada.

    COM a trava: Bruno bloqueia no `SELECT ... FOR UPDATE` da linha do frame
    até Ana commitar, relê a versão (agora diferente) e leva 409 → 1 vencedor.
    SEM a trava: Bruno lê "vazio" (Ana ainda não commitou), passa pela
    conferência e grava; Ana acorda, apaga as caixas do Bruno no
    delete-then-insert e grava as dela → 2 vencedores, trabalho do Bruno
    perdido em silêncio. É o #801.
    """
    leu_a_versao = threading.Event()
    passou_pelo_gancho: list[str] = []

    class _CursorComPausa:
        """Delega tudo ao cursor real, mas avisa quando a versão foi lida."""

        def __init__(self, cur, ao_ler_versao):
            self._cur = cur
            self._ao_ler_versao = ao_ler_versao

        def execute(self, sql, params=None):
            resultado = self._cur.execute(sql, params)
            if sql.startswith("SELECT id, class_name"):
                self._ao_ler_versao()
            return resultado

        def __getattr__(self, nome):
            return getattr(self._cur, nome)

    class RepoComPausa(AnnotationRepository):
        def __init__(self, pool, ao_ler_versao):
            super().__init__(pool)
            self._ao_ler_versao = ao_ler_versao

        def _execute_in_transaction(self, fn):
            return super()._execute_in_transaction(
                lambda conn, cur: fn(conn, _CursorComPausa(cur, self._ao_ler_versao))
            )

    def ana_leu_e_espera():
        passou_pelo_gancho.append("ana")
        leu_a_versao.set()
        # Janela em que a transação de Ana está aberta, com a versão já lida
        # e a linha do frame travada. Tempo de sobra para Bruno chegar ao
        # `FOR UPDATE` (round-trip local ~1ms) e bloquear ali.
        time.sleep(0.5)

    repo = AnnotationRepository(pg_pool)
    versao_inicial = repo.versao_do_frame(cenario["frame"])
    resultado: dict[str, object] = {}

    def salvar(nome: str, user_id: str, caixas: list[dict], instancia) -> None:
        try:
            resultado[nome] = instancia.save_batch(
                cenario["frame"], caixas, user_id=user_id,
                versao_esperada=versao_inicial,
            )
        except ConflictError as exc:
            resultado[nome] = exc

    t_ana = threading.Thread(target=salvar, args=(
        "ana", cenario["ana"], CAIXA_DE_ANA,
        RepoComPausa(pg_pool, ana_leu_e_espera),
    ))
    t_ana.start()
    assert leu_a_versao.wait(timeout=10), "Ana não chegou a ler a versão"

    t_bruno = threading.Thread(target=salvar, args=(
        "bruno", cenario["bruno"], CAIXA_DE_BRUNO, repo,
    ))
    t_bruno.start()

    for t in (t_ana, t_bruno):
        t.join(timeout=30)
        assert not t.is_alive(), "thread travou — deadlock na transação do save"

    # O gancho existe? Teste que mede nada é pior que teste nenhum.
    assert passou_pelo_gancho == ["ana"], "a pausa não rodou — a corrida não foi forçada"

    vencedores = [k for k, v in resultado.items() if v == 1]
    perdedores = [k for k, v in resultado.items() if isinstance(v, ConflictError)]
    assert len(vencedores) == 1, f"esperado exatamente 1 vencedor, veio {resultado}"
    assert len(perdedores) == 1, f"esperado exatamente 1 conflito, veio {resultado}"

    # UMA caixa no banco, do vencedor — nem mistura, nem duplicação.
    caixas = _caixas_no_banco(pg_raw, cenario["frame"])
    assert len(caixas) == 1, f"frame terminou com {len(caixas)} caixas: {caixas}"
    assert str(caixas[0]["created_by"]) == cenario[vencedores[0]]


# ---------------------------------------------------------------------------
# 3. Corrigir o próprio trabalho continua valendo
# ---------------------------------------------------------------------------

def test_mesmo_anotador_reescreve_o_proprio_frame(pg_raw, pg_pool, cenario):
    """Inclui o caso em que a versão do cliente está velha (ex.: as caixas
    foram criadas por um aceite de proposta do próprio usuário, que gera
    linhas novas sem passar por `save_batch`)."""
    repo = AnnotationRepository(pg_pool)
    repo.save_batch(cenario["frame"], CAIXA_DE_ANA, user_id=cenario["ana"],
                    versao_esperada=VERSAO_VAZIA)

    assert repo.save_batch(
        cenario["frame"], CAIXA_DE_BRUNO, user_id=cenario["ana"],
        versao_esperada=VERSAO_VAZIA,  # de propósito: versão velha, dela mesma
    ) == 1

    caixas = _caixas_no_banco(pg_raw, cenario["frame"])
    assert [c["class_name"] for c in caixas] == ["Sem protetor de ouvido"]


# ---------------------------------------------------------------------------
# 4. Versão que bate / chamada interna sem versão
# ---------------------------------------------------------------------------

def test_versao_atualizada_deixa_salvar(pg_raw, pg_pool, cenario):
    """Bruno recarrega o frame (nova versão) e então salva: passa."""
    repo = AnnotationRepository(pg_pool)
    repo.save_batch(cenario["frame"], CAIXA_DE_ANA, user_id=cenario["ana"],
                    versao_esperada=VERSAO_VAZIA)

    depois_de_recarregar = repo.versao_do_frame(cenario["frame"])
    assert depois_de_recarregar != VERSAO_VAZIA

    assert repo.save_batch(
        cenario["frame"], CAIXA_DE_BRUNO, user_id=cenario["bruno"],
        versao_esperada=depois_de_recarregar,
    ) == 1
    caixas = _caixas_no_banco(pg_raw, cenario["frame"])
    assert str(caixas[0]["created_by"]) == cenario["bruno"]


def test_sem_versao_esperada_mantem_o_comportamento_antigo(pg_pool, cenario):
    repo = AnnotationRepository(pg_pool)
    repo.save_batch(cenario["frame"], CAIXA_DE_ANA, user_id=cenario["ana"])
    assert repo.save_batch(
        cenario["frame"], CAIXA_DE_BRUNO, user_id=cenario["bruno"]
    ) == 1
