"""Nenhum deploy pode apagar dado, reescrever credencial nem desfazer configuração
— issues #683 / #694 / #743.

Prova ponta a ponta, contra Postgres de verdade: aplica `infra/migrations/*.sql`
DUAS vezes (como o boot da API faz a cada deploy), com dado de cliente semeado
ENTRE as duas passadas, e exige que o dado, a senha e a escolha de módulos do
admin sobrevivam à segunda.

Três pernas, porque o estrago tem três caminhos:

  A. legado -> legado   O que produção roda hoje (API-V3/production não tem
                        MIGRATIONS_LEDGER_CUTOVER). Antes da guarda: a 049
                        derruba counting_sessions com CASCADE e a 027/040
                        devolvem o password_hash ao hash versionado no git.
  B. ledger -> ledger   Não pode regredir: o ledger já protegia, e continua.
  C. legado -> ledger   O cutover feito SEM o backfill — o cenário que a
                        docstring do runner_core avisa para não fazer. O ledger
                        nasce vazio num banco cheio e reaplica a 049 do zero.

Sem a guarda, A e C perdem o histórico de contagem, a senha E a configuração de
módulos. Rodar com `git stash` da mudança em runner_core.py reproduz as falhas.

A terceira cara (#743) é a 023/034: a 034 devolve o módulo 'quality' a todo
tenant que não o tenha, e a 023 SOBRESCREVE a lista inteira dos tenants 'admin'
e 'rvb' pela versionada no git — desfazendo, a cada deploy, o que o admin
decidiu pela tela.

Cada perna usa um banco descartável próprio no MESMO servidor do harness
(HARNESS_DATABASE_URL) — nunca o banco do harness, que os outros testes leem.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

_RAIZ = Path(__file__).resolve().parents[3]
_RUNNER = _RAIZ / "tests" / "harness" / "migrations" / "runner.py"

# Hash que a 040 reimpõe (o do repositório). O sentinela precisa ser DIFERENTE
# dele — senão "sobreviveu" e "foi reescrito" ficariam indistinguíveis.
_HASH_DO_REPO = "$2b$12$2X2POe45QcgGVjZjBN39RuUpolTjPnYi/KATQG8O4UxD8v.fIES5."
_SENHA_TROCADA_PELO_VITOR = "$2b$12$ooooooooooooooooooooooTROCADAPELATELAoooooooooooooooo"

# A escolha que o admin faz pela tela para o tenant RVB: tira 'quality' (que a
# 034 devolve) e acrescenta 'analytics' (que a 023 não tem na lista do git).
# Precisa diferir das DUAS listas versionadas, senão "sobreviveu" e "foi
# reescrito" ficariam indistinguíveis.
_MODULOS_ESCOLHIDOS_PELO_ADMIN = ["epi", "counting", "basic", "analytics"]


def _dsn_base() -> str:
    dsn = os.environ.get("HARNESS_DATABASE_URL", "")
    if not dsn:
        pytest.skip("HARNESS_DATABASE_URL não definida — rode via run.sh ou CI.")
    return dsn


def _troca_banco(dsn: str, nome: str) -> str:
    return dsn.rsplit("/", 1)[0] + "/" + nome


def _cria_banco_descartavel(dsn_base: str) -> str:
    nome = "redeploy_" + uuid.uuid4().hex[:12]
    conn = psycopg2.connect(dsn_base)
    conn.autocommit = True
    conn.cursor().execute(f'CREATE DATABASE "{nome}"')
    conn.close()
    return nome


def _derruba_banco(dsn_base: str, nome: str) -> None:
    conn = psycopg2.connect(dsn_base)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (nome,)
    )
    cur.execute(f'DROP DATABASE IF EXISTS "{nome}"')  # banco de teste efêmero, não dado
    conn.close()


def _aplica(dsn: str, passada: int, ledger: bool, extra_env: dict | None = None) -> None:
    """Roda o runner exatamente como o boot da API roda (processo separado)."""
    env = dict(os.environ)
    env.pop("MIGRATIONS_LEDGER_CUTOVER", None)
    if ledger:
        env["MIGRATIONS_LEDGER_CUTOVER"] = "1"
    env.update(extra_env or {})
    r = subprocess.run(
        [sys.executable, str(_RUNNER), "--dsn", dsn, "--pass", str(passada)],
        env=env, capture_output=True, text=True, timeout=600,
    )
    assert r.returncode == 0, f"runner falhou (passada {passada}):\n{r.stdout[-4000:]}\n{r.stderr[-2000:]}"


def _semeia(dsn: str) -> dict:
    """Dado de cliente que um deploy jamais pode levar: contagem + senha trocada."""
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        "SELECT id, tenant_id FROM public.users WHERE email = 'vitor@logikos.com'"
    )
    dono = cur.fetchone()
    assert dono is not None, "a 027 deveria ter semeado vitor@logikos.com na passada 1"
    tenant_id, user_id = dono["tenant_id"], dono["id"]
    camera_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO public.cameras (id, tenant_id, user_id, name, host) "
        "VALUES (%s, %s, %s, %s, %s)",
        (camera_id, tenant_id, user_id, "camera-sentinela", "10.0.0.9"),
    )
    sessao_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO public.counting_sessions (id, tenant_id, camera_id, module_code) "
        "VALUES (%s, %s, %s, 'counting')",
        (sessao_id, tenant_id, camera_id),
    )
    cur.execute(
        "INSERT INTO public.counting_events (session_id, tenant_id, track_id, class_name) "
        "VALUES (%s, %s, 7, 'caixa')",
        (sessao_id, tenant_id),
    )

    # O Vitor troca a senha pela tela: o deploy seguinte não pode desfazer.
    cur.execute(
        "UPDATE public.users SET password_hash = %s WHERE email = 'vitor@logikos.com'",
        (_SENHA_TROCADA_PELO_VITOR,),
    )
    assert cur.rowcount == 1, "a 027 deveria ter semeado vitor@logikos.com na passada 1"

    # O admin desliga o módulo Qualidade do RVB pela tela — exatamente o SQL de
    # app/api/v1/admin/routes.py ("UPDATE tenants SET modules_enabled = %s::jsonb").
    cur.execute(
        "UPDATE public.tenants SET modules_enabled = %s::jsonb WHERE slug = 'rvb'",
        (json.dumps(_MODULOS_ESCOLHIDOS_PELO_ADMIN),),
    )
    assert cur.rowcount == 1, "a 023 deveria ter semeado o tenant 'rvb' na passada 1"

    conn.close()
    return {"sessao_id": sessao_id, "camera_id": camera_id}


def _confere(dsn: str, semente: dict) -> None:
    """Junta TODAS as violações antes de falhar — o estrago tem mais de uma cara."""
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    cur = conn.cursor()
    violacoes: list[str] = []

    cur.execute(
        "SELECT COUNT(*) AS n FROM public.counting_sessions WHERE id = %s",
        (semente["sessao_id"],),
    )
    if cur.fetchone()["n"] != 1:
        violacoes.append(
            "#683 SESSÃO DE CONTAGEM APAGADA: a 049 faz DROP TABLE "
            "public.counting_sessions CASCADE e o runner a reexecutou num banco "
            "que já tinha dado."
        )

    cur.execute(
        "SELECT COUNT(*) AS n FROM public.counting_events WHERE session_id = %s",
        (semente["sessao_id"],),
    )
    if cur.fetchone()["n"] != 1:
        violacoes.append(
            "#683 EVENTOS DE CONTAGEM APAGADOS: o CASCADE da 049 leva "
            "counting_events junto."
        )

    cur.execute("SELECT password_hash FROM public.users WHERE email = 'vitor@logikos.com'")
    hash_atual = cur.fetchone()["password_hash"]
    if hash_atual == _HASH_DO_REPO:
        violacoes.append(
            "#694 CREDENCIAL REESCRITA: a senha do superadmin voltou ao hash "
            "versionado no git (027/040 reexecutadas)."
        )
    elif hash_atual != _SENHA_TROCADA_PELO_VITOR:
        violacoes.append(f"#694 password_hash virou algo inesperado: {hash_atual!r}")

    cur.execute("SELECT modules_enabled FROM public.tenants WHERE slug = 'rvb'")
    linha = cur.fetchone()
    modulos = linha["modules_enabled"] if linha else None
    if modulos != _MODULOS_ESCOLHIDOS_PELO_ADMIN:
        violacoes.append(
            "#743 CONFIGURAÇÃO REESCRITA: o admin deixou modules_enabled do RVB em "
            f"{_MODULOS_ESCOLHIDOS_PELO_ADMIN} e o deploy devolveu {modulos} "
            "(023 sobrescreve a lista inteira; 034 recoloca 'quality')."
        )

    conn.close()
    assert not violacoes, "O redeploy destruiu estado do cliente:\n  - " + "\n  - ".join(violacoes)


@pytest.fixture
def banco(request):
    dsn_base = _dsn_base()
    nome = _cria_banco_descartavel(dsn_base)
    request.addfinalizer(lambda: _derruba_banco(dsn_base, nome))
    return _troca_banco(dsn_base, nome)


@pytest.mark.parametrize(
    "passada1_ledger, passada2_ledger, perna",
    [
        (False, False, "A: legado -> legado (o que produção roda hoje)"),
        (True, True, "B: ledger -> ledger (não pode regredir)"),
        (False, True, "C: legado -> ledger sem backfill (o cutover perigoso)"),
    ],
)
def test_redeploy_nao_apaga_dado_nem_reescreve_credencial(
    banco, passada1_ledger, passada2_ledger, perna
):
    _aplica(banco, 1, ledger=passada1_ledger)
    semente = _semeia(banco)
    _aplica(banco, 2, ledger=passada2_ledger)
    _confere(banco, semente)


# ---------------------------------------------------------------------------
# Locale do container não pode decidir se a API sobe
# ---------------------------------------------------------------------------

# 113 dos 125 .sql têm byte não-ASCII (comentário em português, ✅, →). Ler esses
# arquivos com o encoding do AMBIENTE em vez do encoding do ARQUIVO faz
# UnicodeDecodeError sob qualquer locale que não seja UTF-8 — e basta
# PYTHONCOERCECLOCALE=0 / LANG=C no serviço para chegar lá.
#
# Por que isso é um teste e não um detalhe: em railway_start.py a chamada
# `run_migrations()` (linha 665) NÃO está dentro de try/except. Um erro que sobe
# do runner mata o boot antes de `start_api()` — a API não sobe, nem degradada.
_LOCALE_HOSTIL = {
    "LC_ALL": "C",
    "LANG": "C",
    "PYTHONUTF8": "0",
    "PYTHONCOERCECLOCALE": "0",
}


@pytest.mark.parametrize("ledger", [False, True], ids=["legado", "ledger"])
def test_runner_le_migration_como_utf8_qualquer_que_seja_o_locale(banco, ledger):
    _aplica(banco, 1, ledger=ledger, extra_env=_LOCALE_HOSTIL)

    # exit 0 não basta: o loop legado engole erro por arquivo e segue. O que prova
    # é o banco ter ficado migrado de verdade.
    conn = psycopg2.connect(banco, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = 'public'"
    )
    tabelas = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM public.users WHERE email = 'vitor@logikos.com'")
    superadmin = cur.fetchone()["n"]
    conn.close()

    assert tabelas > 50, f"locale hostil deixou o banco pela metade: {tabelas} tabelas"
    assert superadmin == 1, "a 027 não rodou sob locale hostil"
