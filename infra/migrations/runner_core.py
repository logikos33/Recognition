"""
Núcleo único de aplicação de migrations — compartilhado por:
  - railway_start.py (produção, SERVICE_TYPE=api)
  - tests/harness/migrations/runner.py (harness/CI)

Fecha a PEND do README do harness (tests/harness/migrations/README.md):
"unificar o loop de apply do railway_start com o runner.py do harness para eliminar a
duplicação. Não fazer agora — risco de alterar comportamento de produção."
Este módulo faz exatamente essa unificação, mas SEM alterar o comportamento de produção:
o loop legado (`run_legacy`) é o mesmo código, parametrizado o suficiente para reproduzir
os dois comportamentos que já existiam em paralelo (ver docstring de `run_legacy`).

Dois modos, selecionados por env var MIGRATIONS_LEDGER_CUTOVER (lida por `run_migrations`,
o único ponto de entrada que os dois chamadores devem usar):

  * ausente / != "1"  (padrão — produção continua aqui hoje)
        Loop LEGADO: reexecuta todos os .sql a cada boot, sem tabela de controle,
        idempotência via heurística de string de erro ("already exists"/"duplicate"),
        NUNCA aborta o boot.

  * "1"
        Loop NOVO: ledger em public.migrations_ledger + pg_advisory_xact_lock +
        aplicação atômica por migration (BEGIN/lock/checa ledger/aplica/grava/COMMIT).
        Erro desconhecido (fora da lista de legado conhecido) => SystemExit(1), aborta
        o boot. Checksum divergente do que está no ledger => SystemExit(1) (migration
        editada — proibido por C-02 / forward-only).

CUTOVER: a flag é TRANSITIVA. O loop antigo só deixa de existir num follow-up depois do
backfill em produção (infra/migrations/backfill_schema_migrations.py) rodar de fato e um
humano confirmar — isso é o passo 3.5 do mutirão, gate humano. Não ligar a flag em
produção sem rodar o backfill antes: um banco já migrado pelo loop antigo, exposto ao
runner novo SEM backfill, tentaria reaplicar 50+ SQLs do zero.
"""

from __future__ import annotations

import glob
import hashlib
import logging
import os
import re
from dataclasses import dataclass, field

import psycopg2

DEFAULT_MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))

TENANT_SCHEMA_GLOBAL = "_global"

# Constante fixa e arbitrária do runner — usada em pg_advisory_xact_lock(). NUNCA gerar
# dinamicamente (ex.: hash() do Python não é determinístico entre processos) e NUNCA
# mudar entre deploys: instâncias concorrentes só se serializam corretamente se todas
# usarem a MESMA chave.
MIGRATION_ADVISORY_LOCK_KEY = 847_362_910_583

BASELINE_FILENAME = ".duplicate-prefix-baseline"

# Erros legados tolerados APENAS no arquivo que os origina. Mapeia basename -> marcadores.
# NUNCA usar marcador global — mascararia o bug que este mecanismo existe pra pegar.
#
# Cada entrada é uma migration que falha em banco virgem porque referencia um objeto que
# ainda não existe naquele ponto da sequência, mas o estado final está correto porque uma
# migration posterior corrige. Não corrigir as migrations — regra C-02 (forward-only).
#
# 038: FK para ip_cameras (renomeada na 013), corrigida pela 047.
# 039: FK para operations (não criada pq 038 falhou), criada pela 047/048.
# 011: DML usa quality_status antes de a coluna existir (criada por migration posterior).
# 021: DML usa pre_annotated_at antes de a coluna existir (criada por migration posterior).
KNOWN_LEGACY_ERRORS: dict[str, tuple[str, ...]] = {
    "038_operations.sql": ("ip_cameras",),
    "039_operation_results.sql": ('"operations" does not exist',),
    "011_active_learning.sql": ("quality_status",),
    "021_reset_empty_pre_annotations.sql": ("pre_annotated_at",),
}


def _default_logger() -> logging.Logger:
    return logging.getLogger("migrations")


def sql_files(migrations_dir: str = DEFAULT_MIGRATIONS_DIR) -> list[str]:
    return sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))


def is_idempotent_error(error_text: str) -> bool:
    lowered = error_text.lower()
    return "already exists" in lowered or "duplicate" in lowered


def is_known_legacy(basename: str, error_text: str, known_legacy_errors: dict[str, tuple[str, ...]] | None = None) -> bool:
    markers = (known_legacy_errors if known_legacy_errors is not None else KNOWN_LEGACY_ERRORS).get(basename, ())
    lowered = error_text.lower()
    return any(m.lower() in lowered for m in markers)


def drift_notices(notices: list[str]) -> list[str]:
    """Filtra NOTICEs do Postgres que indicam objeto pré-existente.

    "relation ... already exists, skipping" durante a PRIMEIRA aplicação de uma
    migration segundo o ledger significa que os objetos dela já estavam no banco
    — o sintoma clássico de migration aplicada na mão (psql -f) fora do runner,
    que deixa o ledger mentindo sobre o estado do ambiente (prática do ledger,
    REGISTRO_DE_DECISOES). Heurística best-effort: só cobre statements
    IF NOT EXISTS (que emitem NOTICE), e pode acusar re-assert defensivo de
    objeto antigo — por isso vira WARNING, nunca aborta.
    """
    return [
        n.strip()
        for n in notices
        if "already exists" in n.lower() and "skipping" in n.lower()
    ]


def version_of(basename: str) -> str:
    """Prefixo numérico do arquivo (ex.: '052_custom_roles.sql' -> '052')."""
    return basename.split("_", 1)[0]


def sha256_of_file(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ---------------------------------------------------------------------------
# Guarda de redeploy — issues #683 (P0) e #694 (risk:security)
# ---------------------------------------------------------------------------
#
# O loop LEGADO reexecuta TODO .sql a cada boot. Em produção (API-V3/production
# não tem MIGRATIONS_LEDGER_CUTOVER) isso transformava "uma vez" em "sempre":
#
#   049_counting_deepsort_rebuild.sql  DROP TABLE ... counting_sessions CASCADE
#       -> o histórico de contagem do cliente era apagado A CADA DEPLOY (o
#          CASCADE leva counting_events junto).
#   040_reset_superadmin_password.sql  UPDATE users SET password_hash = '<hash>'
#   027_superadmin_vitor.sql           ON CONFLICT ... DO UPDATE SET password_hash
#       -> a senha do superadmin voltava ao hash versionado no git a cada deploy,
#          desfazendo, sem log, qualquer troca feita pela tela.
#   046_deactivate_default_tenant.sql  DELETE FROM alerts / cameras
#
# (a 013 também tem DROP TABLE, mas está isenta — ver GUARDA_ISENTAS abaixo.)
#
# A guarda é a mesma ideia já aceita neste repo para o bootstrap de admin
# (railway_start._instalacao_virgem, D-166): a limpeza foi escrita para a
# instalação virgem, então SÓ na instalação virgem ela roda. Num banco que já
# tem tenant, migration que apaga dado ou reescreve credencial é PULADA — em
# ambos os loops (legado e ledger), porque o mesmo estrago acontece no ledger
# quando ele encontra um banco estabelecido sem backfill (o cenário exato do
# cutover que a docstring deste módulo avisa para não fazer).
#
# `established` é medido UMA VEZ, antes de aplicar qualquer migration: num banco
# virgem a 005/027 criam tenants no meio da passada, e reavaliar arquivo a
# arquivo faria a 049 ser pulada logo na primeira instalação — deixando
# counting_sessions com o schema errado da 015.
#
# Escopo deliberadamente estreito (só o que é IRREVERSÍVEL): apagar linha e
# reescrever senha. Backfill do tipo `UPDATE ... WHERE col IS NULL` não é
# pego aqui — essa classe é a da #682 e se resolve com migration corretiva.

_COMENTARIO_DE_LINHA = re.compile(r"--[^\n]*")
_COMENTARIO_DE_BLOCO = re.compile(r"/\*.*?\*/", re.S)

# 104 e 108 citam "DELETE/TRUNCATE" no CABEÇALHO, prometendo não fazer isso.
# Sem tirar comentário, a guarda pularia justo as duas migrations que seguem a
# regra — por isso o strip vem antes de qualquer casamento.


def strip_sql_comments(sql: str) -> str:
    return _COMENTARIO_DE_LINHA.sub(" ", _COMENTARIO_DE_BLOCO.sub(" ", sql))


_APAGA_DADO = re.compile(
    r"\b(?:DROP\s+TABLE|DROP\s+SCHEMA|DROP\s+DATABASE|DROP\s+MATERIALIZED\s+VIEW"
    r"|DROP\s+COLUMN|TRUNCATE|DELETE\s+FROM)\b",
    re.I,
)
# Definição de coluna ("password_hash VARCHAR(255)") não casa: exige o "=" da
# atribuição, que só aparece em UPDATE ... SET / ON CONFLICT DO UPDATE SET.
_REESCREVE_CREDENCIAL = re.compile(r"\bpassword_hash\s*=", re.I)


# Isenções — arquivo por arquivo, com o motivo escrito. NÃO é lista de "confio
# nesse": é lista de "medi e o comando não alcança linha de cliente".
#
# 013: o DROP TABLE só dispara quando `cameras` E `ip_cameras` existem, e num banco
#      estabelecido quem cria `ip_cameras` é a PRÓPRIA passada, 11 arquivos antes
#      (002 tem `CREATE TABLE IF NOT EXISTS ip_cameras`). A tabela que a 013 derruba
#      nasceu vazia segundos antes: o DROP não alcança dado nenhum, e o par 002+013
#      é um ciclo que se anula a cada boot desde sempre. Barrar a 013 NÃO salvaria
#      dado — só deixaria um `ip_cameras` fantasma vazio para trás, o que o diff de
#      schema do harness pegou (40 linhas novas na passada 2). Manter o ciclo como
#      está é a opção que não muda nada.
GUARDA_ISENTAS: dict[str, str] = {
    "013_consolidate_cameras.sql": (
        "derruba apenas o ip_cameras vazio que a 002 recria na mesma passada"
    ),
}


def destructive_reason(sql_text: str) -> str | None:
    """Motivo pelo qual reexecutar este SQL é perda de dado — ou None."""
    corpo = strip_sql_comments(sql_text)
    achado = _APAGA_DADO.search(corpo)
    if achado:
        return f"apaga dado ({' '.join(achado.group(0).split()).upper()})"
    if _REESCREVE_CREDENCIAL.search(corpo):
        return "reescreve credencial (atribuição a password_hash)"
    return None


def database_is_established(cur) -> bool:
    """True quando o banco já tem tenant — ou seja, já tem dado de gente.

    Banco sem a tabela `tenants` (schema anterior a ela) conta como virgem: não
    há dado de cliente que uma limpeza possa levar junto.
    """
    cur.execute(
        "SELECT EXISTS(SELECT FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='tenants')"
    )
    if not cur.fetchone()[0]:
        return False
    cur.execute("SELECT EXISTS(SELECT 1 FROM public.tenants)")
    return bool(cur.fetchone()[0])


def _guarda_pula(basename: str, sql_text: str, established: bool, log: logging.Logger) -> bool:
    if not established or basename in GUARDA_ISENTAS:
        return False
    motivo = destructive_reason(sql_text)
    if motivo is None:
        return False
    log.warning(
        "  %s ⛔ PULADA pela guarda de redeploy: %s, e este banco já tem tenant. "
        "Migration que apaga dado ou reescreve senha só roda em instalação virgem "
        "(issues #683/#694) — em banco estabelecido ela transforma uma limpeza "
        "única em perda de dado a cada deploy. Se esta migration é NOVA e precisa "
        "rodar, ela viola a regra forward-only do CLAUDE.md (sem DROP/DELETE/"
        "TRUNCATE): reescreva-a sem o comando destrutivo.",
        basename, motivo,
    )
    return True


# ---------------------------------------------------------------------------
# Loop LEGADO — item 3.2 (o que já existia, sem mudar comportamento observável)
# ---------------------------------------------------------------------------


def run_legacy(
    dsn: str,
    migrations_dir: str = DEFAULT_MIGRATIONS_DIR,
    log: logging.Logger | None = None,
    known_legacy_errors: dict[str, tuple[str, ...]] | None = None,
    pass_label: str = "",
) -> bool:
    """Loop legado: reexecuta todos os .sql, idempotência por heurística de erro.

    Parametrizado por `known_legacy_errors` para reproduzir os DOIS comportamentos que
    já existiam em paralelo antes desta unificação, sem mudar nenhum deles:

      - railway_start.py (produção) chama com known_legacy_errors={} (padrão do dict
        vazio abaixo) — reproduz exatamente o heurístico simples que já estava em
        produção (só "already exists"/"duplicate" são tolerados; qualquer outro erro
        vira um log ❌, mas o loop SEMPRE continua e SEMPRE retorna considerando
        apenas erros não-classificados como "fatais" para fins do valor de retorno,
        que a produção historicamente ignorava mesmo).
      - tests/harness/migrations/runner.py (CI) chama com known_legacy_errors=
        KNOWN_LEGACY_ERRORS — reproduz exatamente a distinção que o harness já fazia
        entre "idempotente", "legado conhecido" e "fatal real".

    Em NENHUM dos dois casos este loop aborta no meio (nunca faz sys.exit) — ele sempre
    tenta todos os arquivos, na ordem, e só reporta no final. Isso é intencional: é o
    comportamento de produção que existia antes deste módulo, e a troca para "aborta de
    verdade" só acontece no loop novo (`run_ledger`), atrás da flag.
    """
    log = log or _default_logger()
    known_legacy_errors = known_legacy_errors if known_legacy_errors is not None else {}
    label = f" ({pass_label})" if pass_label else ""
    log.info("=== Migrations%s ===", label)

    files = sql_files(migrations_dir)
    if not files:
        log.error("Nenhum arquivo .sql encontrado em %s", migrations_dir)
        return False
    log.info("  %d arquivo(s) em %s", len(files), migrations_dir)

    try:
        conn = psycopg2.connect(dsn)
    except Exception as exc:
        log.error("Migrations: %s", exc)
        return False

    cur = conn.cursor()
    fatal_errors: list[tuple[str, str]] = []
    # Medido UMA vez, antes de aplicar qualquer arquivo (ver bloco da guarda).
    established = database_is_established(cur)
    conn.rollback()
    if established:
        log.info("  banco já estabelecido (tem tenant) — guarda de redeploy ATIVA")

    for f in files:
        basename = os.path.basename(f)
        sql_text = open(f).read()
        if _guarda_pula(basename, sql_text, established, log):
            continue
        log.info("  %s...", basename)
        try:
            cur.execute(sql_text)
            conn.commit()
            log.info("  %s ✅", basename)
        except Exception as exc:
            conn.rollback()
            err_text = str(exc)
            if is_idempotent_error(err_text):
                log.info("  %s ⚠️  já existe (OK — redeploy normal)", basename)
            elif is_known_legacy(basename, err_text, known_legacy_errors):
                log.warning("  %s ⚠️  LEGADO CONHECIDO: %s", basename, err_text.strip())
            else:
                log.error("  %s ❌ %s", basename, err_text.strip())
                fatal_errors.append((basename, err_text))

    conn.close()

    if fatal_errors:
        log.error("=== %d erro(s) fatal(is) ===", len(fatal_errors))
        for name, err in fatal_errors:
            log.error("  ❌ %s: %s", name, err.strip())
        return False

    log.info("✅ Migrations OK")
    return True


# ---------------------------------------------------------------------------
# Loop NOVO — itens 3.3 (ledger) e 3.4 (transação atômica + advisory lock)
# ---------------------------------------------------------------------------


@dataclass
class LedgerRunSummary:
    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    tolerated: list[str] = field(default_factory=list)
    guarded: list[str] = field(default_factory=list)


_CREATE_LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS public.migrations_ledger (
    tenant_schema   VARCHAR(255) NOT NULL DEFAULT '_global',
    version         VARCHAR(10)  NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    checksum        VARCHAR(64)  NOT NULL,
    installed_rank  INTEGER,
    installed_on    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    success         BOOLEAN      NOT NULL DEFAULT TRUE,
    PRIMARY KEY (tenant_schema, version, filename)
);
"""
# Índice parcial mantido em sincronia com 107_migrations_ledger.sql (ver docstring de
# .duplicate-prefix-baseline). Bootstrap aqui existe para que migrations 001-106 (que
# rodam ANTES da 107 na ordem alfabética) já encontrem o ledger existindo.
_CREATE_LEDGER_INDEXES_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_migrations_ledger_tenant_version
    ON public.migrations_ledger (tenant_schema, version)
    WHERE version NOT IN ('052');
CREATE INDEX IF NOT EXISTS idx_migrations_ledger_installed_on
    ON public.migrations_ledger (installed_on);
"""


def _ensure_ledger_table(conn, log: logging.Logger) -> None:
    cur = conn.cursor()
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_ADVISORY_LOCK_KEY,))
    cur.execute(_CREATE_LEDGER_SQL)
    cur.execute(_CREATE_LEDGER_INDEXES_SQL)
    conn.commit()
    log.info("  ledger (public.migrations_ledger) OK")


def _load_baseline_duplicate_versions(migrations_dir: str) -> set[str]:
    path = os.path.join(migrations_dir, BASELINE_FILENAME)
    versions: set[str] = set()
    if os.path.isfile(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#"):
                versions.add(line)
    return versions


def _ledger_duplicate_versions(conn) -> set[str]:
    """Versões que já têm mais de um filename gravado no ledger (aceitas historicamente,
    mesmo que o arquivo .duplicate-prefix-baseline não liste — defesa extra)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT version FROM public.migrations_ledger "
            "GROUP BY tenant_schema, version HAVING COUNT(DISTINCT filename) > 1"
        )
        versions = {row[0] for row in cur.fetchall()}
    except Exception:
        versions = set()
    finally:
        conn.rollback()  # leitura; nada a commitar
    return versions


def _preflight_duplicate_prefix_check(conn, files: list[str], migrations_dir: str, log: logging.Logger) -> None:
    """Falha ANTES de aplicar qualquer migration se houver prefixo de versão duplicado
    fora da baseline histórica conhecida. Mata a classe de bug dos 6x052 se ela se repetir.
    """
    by_version: dict[str, list[str]] = {}
    for f in files:
        by_version.setdefault(version_of(os.path.basename(f)), []).append(os.path.basename(f))

    allowed = _load_baseline_duplicate_versions(migrations_dir) | _ledger_duplicate_versions(conn)
    offenders = {v: names for v, names in by_version.items() if len(names) > 1 and v not in allowed}

    if offenders:
        for v, names in sorted(offenders.items()):
            log.critical(
                "PREFIXO DE VERSAO DUPLICADO NAO AUTORIZADO: versao %s aparece em %d "
                "arquivo(s) (%s) e nao esta em %s/%s nem ja registrada no ledger com "
                "multiplos filenames. Abortando ANTES de aplicar qualquer migration.",
                v, len(names), ", ".join(sorted(names)), migrations_dir, BASELINE_FILENAME,
            )
        raise SystemExit(1)


def _record(conn, version: str, filename: str, checksum: str, success: bool) -> None:
    cur = conn.cursor()
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_ADVISORY_LOCK_KEY,))
    cur.execute(
        """
        INSERT INTO public.migrations_ledger
            (tenant_schema, version, filename, checksum, installed_rank, installed_on, success)
        VALUES (
            %(tenant_schema)s, %(version)s, %(filename)s, %(checksum)s,
            (SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM public.migrations_ledger
             WHERE tenant_schema = %(tenant_schema)s),
            NOW(), %(success)s
        )
        ON CONFLICT (tenant_schema, version, filename)
        DO UPDATE SET checksum = EXCLUDED.checksum,
                      success = EXCLUDED.success,
                      installed_on = EXCLUDED.installed_on
        """,
        {
            "tenant_schema": TENANT_SCHEMA_GLOBAL,
            "version": version,
            "filename": filename,
            "checksum": checksum,
            "success": success,
        },
    )
    conn.commit()


def _apply_one(conn, path: str, log: logging.Logger, ledger_established: bool = False) -> str:
    """Aplica uma migration em transação própria com advisory xact lock.

    *ledger_established*: True quando este boot já PULOU alguma migration por
    estar no ledger — distingue banco estabelecido (deploy normal) de banco
    virgem (harness pass 1), onde o bootstrap do ledger em _ensure_ledger_table
    gera "already exists" legítimo na 107 e o aviso de deriva seria ruído.

    BEGIN (implícito) -> pg_advisory_xact_lock -> checa ledger -> aplica -> grava -> COMMIT.
    Nunca pg_advisory_lock (sessão): o lock precisa morrer com a transação, senão uma
    conexão que pega o lock e devolve para o pool antes de outra sessão soltá-lo trava
    todo boot futuro.

    Retorna "applied" | "skipped" | "tolerated". Levanta SystemExit(1) em erro fatal real
    ou em checksum divergente (migration editada).
    """
    basename = os.path.basename(path)
    version = version_of(basename)
    checksum = sha256_of_file(path)
    sql_text = open(path).read()

    cur = conn.cursor()
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_ADVISORY_LOCK_KEY,))
    cur.execute(
        "SELECT checksum, success FROM public.migrations_ledger "
        "WHERE tenant_schema = %s AND version = %s AND filename = %s",
        (TENANT_SCHEMA_GLOBAL, version, basename),
    )
    row = cur.fetchone()

    if row is not None:
        stored_checksum, stored_success = row
        if stored_checksum != checksum:
            conn.rollback()
            log.critical(
                "MIGRATION EDITADA: %s (versao %s) tem checksum divergente do ledger "
                "(ledger=%s, arquivo atual=%s). Migrations sao forward-only — nunca edite "
                "uma ja aplicada; crie uma nova. Abortando o boot.",
                basename, version, stored_checksum, checksum,
            )
            raise SystemExit(1)
        if stored_success:
            conn.rollback()
            log.info("  %s ⏭️  já aplicada (ledger) — pulando", basename)
            return "skipped"
        # success=False: legado conhecido tolerado antes — tenta de novo agora
        # (pode ter virado no-op bem-sucedido, ver 038/039 no README do harness).

    del conn.notices[:]
    try:
        cur.execute(sql_text)
    except Exception as exc:
        conn.rollback()
        err_text = str(exc)
        if not is_known_legacy(basename, err_text):
            log.critical("FALHA FATAL na migration %s: %s", basename, err_text.strip())
            raise SystemExit(1)
        log.warning("  %s ⚠️  LEGADO CONHECIDO (tolerado): %s", basename, err_text.strip())
        _record(conn, version, basename, checksum, success=False)
        return "tolerated"

    if row is None and ledger_established:
        drifted = drift_notices(list(conn.notices))
        if drifted:
            log.warning(
                "  %s ⚠️  POSSÍVEL DERIVA DO LEDGER: primeira aplicação segundo o "
                "ledger, mas o banco já tinha %d objeto(s) dela (ex.: %s). Se essa "
                "migration foi aplicada na mão (psql -f) fora do runner, o ledger "
                "estava mentindo sobre o estado do ambiente — não aplique migration "
                "fora do runner; se for inevitável, grave a entrada no ledger junto "
                "(prática do ledger, REGISTRO_DE_DECISOES).",
                basename, len(drifted), drifted[0],
            )

    _record(conn, version, basename, checksum, success=True)
    log.info("  %s ✅ (ledger)", basename)
    return "applied"


def run_ledger(dsn: str, migrations_dir: str = DEFAULT_MIGRATIONS_DIR, log: logging.Logger | None = None) -> bool:
    """Loop novo: ledger + advisory xact lock + aplicação atômica por migration.

    Sem heurística de erro (idempotência vem do ledger). Erro real desconhecido ou
    checksum divergente -> SystemExit(1), aborta o boot.
    """
    log = log or _default_logger()
    log.info("=== Migrations (ledger) ===")

    files = sql_files(migrations_dir)
    if not files:
        log.error("Nenhum arquivo .sql encontrado em %s", migrations_dir)
        return False
    log.info("  %d arquivo(s) em %s", len(files), migrations_dir)

    conn = psycopg2.connect(dsn)
    try:
        _ensure_ledger_table(conn, log)
        _preflight_duplicate_prefix_check(conn, files, migrations_dir, log)

        cur = conn.cursor()
        established = database_is_established(cur)
        conn.rollback()
        if established:
            log.info("  banco já estabelecido (tem tenant) — guarda de redeploy ATIVA")

        summary = LedgerRunSummary()
        for path in files:
            basename = os.path.basename(path)
            # A guarda vale aqui também: um banco estabelecido cujo ledger ainda
            # está vazio (o cutover feito sem o backfill) faria o runner novo
            # reaplicar a 049 do zero — mesmo estrago, outro loop.
            if _guarda_pula(basename, open(path).read(), established, log):
                summary.guarded.append(basename)
                continue
            outcome = _apply_one(
                conn, path, log, ledger_established=bool(summary.skipped)
            )
            getattr(summary, outcome).append(basename)

        log.info(
            "✅ Migrations (ledger) OK — %d aplicada(s), %d pulada(s), %d tolerada(s), "
            "%d barrada(s) pela guarda",
            len(summary.applied), len(summary.skipped), len(summary.tolerated),
            len(summary.guarded),
        )
        return True
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Ponto de entrada único
# ---------------------------------------------------------------------------


def run_migrations(
    dsn: str,
    migrations_dir: str = DEFAULT_MIGRATIONS_DIR,
    log: logging.Logger | None = None,
    known_legacy_errors: dict[str, tuple[str, ...]] | None = None,
    pass_label: str = "",
) -> bool:
    """Ponto de entrada único, usado por railway_start.py e pelo harness.

    MIGRATIONS_LEDGER_CUTOVER=1 -> loop novo (ledger). Qualquer outro valor/ausente ->
    loop legado, byte-a-byte igual ao que já existia (ver `run_legacy`).
    """
    log = log or _default_logger()
    if os.environ.get("MIGRATIONS_LEDGER_CUTOVER") == "1":
        log.info("MIGRATIONS_LEDGER_CUTOVER=1 — runner novo (ledger + advisory lock)")
        return run_ledger(dsn, migrations_dir=migrations_dir, log=log)
    return run_legacy(
        dsn,
        migrations_dir=migrations_dir,
        log=log,
        known_legacy_errors=known_legacy_errors,
        pass_label=pass_label,
    )
