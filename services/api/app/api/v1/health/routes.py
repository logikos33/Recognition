"""Health check endpoints (Railway healthcheck + admin metrics)."""
import hashlib
import logging
import os
import re
import time

from flask import Blueprint, jsonify

from app.api.v1.health.readiness import STALE_AFTER_SECONDS, cache as _readiness_cache
from app.core.auth import jwt_required_custom

health_bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)

# Marca de boot do PROCESSO (não do request) — usada só por /livez.
_PROCESS_STARTED_AT = time.monotonic()

# ---------------------------------------------------------------------------
# Proveniência: o que me DISSERAM  ×  o que eu SOU
# ---------------------------------------------------------------------------
#
# Por que existe: não havia como perguntar à API que código ela está rodando,
# e isso mordeu duas vezes em uma semana — um `railway up` sobrescreveu um
# deploy por git e ninguém conseguiu provar o que estava no ar sem adivinhar.
#
# ⚠️ A PRIMEIRA VERSÃO DISTO SE AUTO-ENGANAVA. Ela lia um SHA de env var e o
# devolvia como se fosse fato. Env var e código servido são coisas
# INDEPENDENTES: o CI grava `GIT_COMMIT_SHA` ANTES de subir, então basta o
# upload falhar, subir outra árvore, ou alguém dar um `railway up` do laptop
# (que não toca a variável) para o `/livez` afirmar, com confiança, um SHA que
# não está rodando. Trocar "não sei" (`unknown`) por "acho que sei" DESLIGOU o
# único sinal honesto que existia. Ver o runbook SINAIS_DEGRADACAO.md.
#
# O conserto: além do SHA declarado, devolver um digest derivado do PRÓPRIO
# CÓDIGO EM DISCO. Ninguém escreve esse valor — ele é o que o processo é.

#: SHA que ALGUÉM declarou. Não é prova de nada por si só.
_COMMIT_SHA = (
    os.environ.get("RAILWAY_GIT_COMMIT_SHA")
    or os.environ.get("GIT_COMMIT_SHA")
    or ""
).strip() or "unknown"

#: QUEM declarou — e isso muda o peso da declaração.
#:
#: `RAILWAY_GIT_COMMIT_SHA` é injetado pela plataforma num deploy por git:
#: descreve o artefato, ninguém digita. `GIT_COMMIT_SHA` é variável que uma
#: pessoa ou um workflow escreveu, e ela SOBREVIVE a um deploy que subiu outra
#: coisa — é declaração, não proveniência. `None` = ninguém declarou.
_COMMIT_SOURCE = (
    "RAILWAY_GIT_COMMIT_SHA"
    if (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "").strip()
    else "GIT_COMMIT_SHA"
    if (os.environ.get("GIT_COMMIT_SHA") or "").strip()
    else None
)

#: Raiz do pacote servido: .../app/api/v1/health/routes.py → .../app
_PACOTE_SERVIDO = os.path.dirname(  # app
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


def _digest_da_arvore_servida(raiz: str) -> str | None:
    """Impressão digital do código Python que ESTE processo tem em disco.

    Usa o hash de blob do git (`sha1("blob <n>\0" + conteúdo)`) por arquivo,
    para que qualquer pessoa recomponha o valor esperado a partir do
    repositório SEM checkout e SEM rede:

        git ls-tree -r <sha> -- services/api/app   # → mesmos hashes

    É isso que separa prova de declaração: o SHA da env var é o que alguém
    disse; este digest é o que o processo é. Se os dois discordam, quem mente
    é a env var.

    `None` quando não deu para calcular — nunca levanta: este código roda no
    import do blueprint do `/livez`, e um `/livez` que não sobe vira loop de
    restart no Railway.

    ponytail: cobre só `app/**/*.py` — não pega dependências instaladas,
    migrations nem o frontend. Estenda a varredura se algum desses virar a
    pergunta.
    """
    try:
        entradas = []
        for pasta, _subpastas, arquivos in os.walk(raiz):
            for nome in arquivos:
                if not nome.endswith(".py"):
                    continue
                caminho = os.path.join(pasta, nome)
                with open(caminho, "rb") as fh:
                    dados = fh.read()
                # sha1 aqui NÃO é escolha de segurança: é o formato do git,
                # que é justamente o que torna o valor conferível de fora.
                blob = hashlib.sha1(  # noqa: S324
                    b"blob %d\0" % len(dados) + dados, usedforsecurity=False
                ).hexdigest()
                relativo = os.path.relpath(caminho, raiz).replace(os.sep, "/")
                entradas.append(f"{blob} {relativo}")
        if not entradas:
            return None
        # Ordenação explícita pela linha inteira: `os.walk` e `git ls-tree` não
        # entregam na mesma ordem, e sem isto os dois lados nunca casariam.
        corpo = "\n".join(sorted(entradas))
        return hashlib.sha256(corpo.encode()).hexdigest()[:16]
    except Exception as exc:  # pragma: no cover - defensivo, nunca derruba /livez
        logger.warning("tree_digest_falhou: %s", exc)
        return None


#: Resolvido UMA vez no import (~340 arquivos): o `/livez` é probe de liveness
#: e não pode pagar I/O por request.
_TREE_DIGEST = _digest_da_arvore_servida(_PACOTE_SERVIDO)


@health_bp.route("/health")
@health_bp.route("/api/v1/health")
def health_check() -> tuple:
    """
    ---
    tags:
      - health
    summary: Health check do sistema
    description: Verifica conectividade com PostgreSQL e Redis
    responses:
      200:
        description: Sistema saudável
        schema:
          properties:
            status: {type: string, example: healthy}
            checks:
              type: object
              properties:
                database: {type: boolean}
                redis: {type: boolean}
      503:
        description: Sistema degradado
    """
    checks: dict[str, bool] = {
        "database": _check_database(),
        "redis": _check_redis(),
    }
    all_healthy = all(checks.values())
    status_code = 200 if checks["database"] else 503

    return (
        jsonify(
            {
                "status": "healthy" if all_healthy else "degraded",
                "checks": checks,
            }
        ),
        status_code,
    )


@health_bp.route("/livez")
def liveness_check() -> tuple:
    """
    ---
    tags:
      - health
    summary: Liveness — o processo está de pé?
    description: |
      NUNCA toca DB/Redis/R2. Só confirma que o processo Python responde a
      HTTP. Serve para "reiniciar se travou" — não para "promover deploy":
      isso é o /readyz. Sempre 200 enquanto o processo estiver vivo.

      Proveniência, em dois campos que NÃO são a mesma coisa:

      - `commit` + `commit_source`: o SHA que ALGUÉM DECLAROU, e quem
        declarou. `RAILWAY_GIT_COMMIT_SHA` vem da plataforma num deploy por
        git (descreve o artefato); `GIT_COMMIT_SHA` é variável escrita por
        um workflow ou por uma pessoa e SOBREVIVE a um deploy que subiu
        outra coisa. `unknown` = ninguém declarou.
      - `tree_digest`: o que este processo DE FATO tem em disco — digest dos
        hashes de blob git de `app/**/*.py`. Ninguém escreve esse valor.
        Confira de fora, sem checkout:
        `git ls-tree -r <sha> -- services/api/app`.

      ⚠️ `commit` sozinho NÃO é prova: a variável e o código servido são
      independentes. Prova é `tree_digest` casar com o da árvore esperada.

      Sem autenticação de propósito — SHA de commit não é segredo, e a
      pergunta "o que está no ar?" precisa ser respondível mesmo com o banco
      fora.

      E `running_jobs`: quantos jobs de treino estão em voo (queued|running),
      LIDO DO CACHE do refresher de readiness — este handler continua sem
      tocar o banco. Serve à regra de convivência entre sessões: merge na
      develop redeploya API e worker, e o deploy do worker mata o vigia de um
      pod em voo. A regra vira `curl /livez` → `running_jobs == 0` → merge.

      ⚠️ `null` significa NÃO SEI (sem ciclo do refresher, snapshot velho, ou
      banco fora) — nunca "zero". A regra é `== 0`, então `null` BLOQUEIA.
      Contagem não é dado sensível: é um inteiro, sem id, tenant ou nome.
    responses:
      200:
        description: Processo vivo
    """
    uptime = time.monotonic() - _PROCESS_STARTED_AT
    return jsonify({
        "status": "alive",
        "uptime_seconds": round(uptime, 1),
        "commit": _COMMIT_SHA,
        "commit_source": _COMMIT_SOURCE,
        "tree_digest": _TREE_DIGEST,
        "running_jobs": _readiness_cache.peek_running_jobs(),
    }), 200


@health_bp.route("/readyz")
def readiness_check() -> tuple:
    """
    ---
    tags:
      - health
    summary: Readiness — dependências + invariantes de config (única barreira de promoção)
    description: |
      Railway só chama isto NA PROMOÇÃO do deploy. O handler NUNCA toca
      dependência diretamente — só lê o cache mantido por um refresher de
      fundo (ver readiness.py). Invariantes determinísticos (worker_class,
      storage_backend) reprovam duro na primeira leitura ruim. Dependências
      transitórias (DB, Redis) só reprovam após falhas consecutivas do
      refresher (backoff). Cache com mais de 30s (refresher morto) = 503
      com stale=true, mesmo que o último conteúdo dissesse "tudo bem"
      (fail closed — nunca serve um "ready" congelado).
    responses:
      200:
        description: Pronto para receber tráfego
      503:
        description: Não pronto (invariante quebrado, dependência down, ou cache stale)
    """
    state = _readiness_cache.get_state()
    age = time.monotonic() - state.checked_at

    if age > STALE_AFTER_SECONDS:
        logger.error(
            "readyz_stale: cache com %.1fs (refresher parece morto) — fail closed", age
        )
        return (
            jsonify(
                {
                    "status": "not_ready",
                    "ready": False,
                    "stale": True,
                    "age_seconds": round(age, 1),
                    "invariants": state.invariants,
                    "dependencies": state.dependencies,
                }
            ),
            503,
        )

    return (
        jsonify(
            {
                "status": "ready" if state.ready else "not_ready",
                "ready": state.ready,
                "stale": False,
                "age_seconds": round(age, 1),
                "invariants": state.invariants,
                "dependencies": state.dependencies,
            }
        ),
        200 if state.ready else 503,
    )


@health_bp.route("/status")
def status_check() -> tuple:
    """
    ---
    tags:
      - health
    summary: Diagnóstico rico — NUNCA consumido por automação que reinicia
    description: |
      Agrega o que /health já mostra + detalhe por dependência (latência,
      última checagem via cache de /readyz). Uso humano/observabilidade —
      não é chamado pelo healthcheck do Railway nem por nada que promove ou
      reinicia deploy. Pode fazer I/O direto (sem cache) porque não está no
      caminho de promoção.
    responses:
      200:
        description: Snapshot de diagnóstico
    """
    db_start = time.perf_counter()
    db_ok = _check_database()
    db_latency_ms = round((time.perf_counter() - db_start) * 1000, 1)

    redis_start = time.perf_counter()
    redis_ok = _check_redis()
    redis_latency_ms = round((time.perf_counter() - redis_start) * 1000, 1)

    readiness_state = _readiness_cache.get_state()
    readiness_age = time.monotonic() - readiness_state.checked_at

    return (
        jsonify(
            {
                "status": "healthy" if db_ok and redis_ok else "degraded",
                "checks": {
                    "database": {"ok": db_ok, "latency_ms": db_latency_ms},
                    "redis": {"ok": redis_ok, "latency_ms": redis_latency_ms},
                },
                "readiness_cache": {
                    "ready": readiness_state.ready,
                    "age_seconds": round(readiness_age, 1),
                    "stale": readiness_age > STALE_AFTER_SECONDS,
                    "invariants": readiness_state.invariants,
                    "dependencies": readiness_state.dependencies,
                },
            }
        ),
        200,
    )


def _contar_jobs_em_voo() -> int | None:
    """Quantos jobs de treino estão em voo (queued|running). None = não deu para saber.

    Existe para a regra de convivência entre sessões: merge na develop redeploya
    API e worker, e o deploy do worker MATA o vigia de um pod em voo. A pergunta
    "há pod em voo?" precisava ser feita a um humano ou a outra sessão, e ficou
    três vezes sem resposta numa rodada só.

    ⚠️ `None` NUNCA vira 0. Uma sessão consultou o banco errado e leu "zero pods"
    porque a tabela estava vazia, não porque não havia pod — foi assim que a
    pergunta ficou pendente. Aqui, não-saber é explícito, e a regra é
    `running_jobs == 0` (não `!= 1`), então `null` BLOQUEIA o merge.

    Chamado só pelo refresher de fundo. ⛔ Nunca do handler HTTP.
    """
    try:
        from app.constants import TrainingStatus
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return None
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM public.training_jobs WHERE status = ANY(%s)",
                ([TrainingStatus.QUEUED.value, TrainingStatus.RUNNING.value],),
            )
            linha = cur.fetchone()
        if linha is None:
            return None
        # RealDictCursor devolve dict; cursor comum devolve tupla.
        return int(linha["count"] if isinstance(linha, dict) else linha[0])
    except Exception:
        logger.warning("health_check: contagem de jobs em voo indisponível")
        return None


def _check_database() -> bool:
    try:
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return False
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
        return True
    except Exception:
        logger.warning("health_check: database unavailable")
        return False


def _check_redis() -> bool:
    try:
        import os

        import redis

        url = os.environ.get("REDIS_URL", "")
        if not url:
            return False
        client = redis.from_url(url, socket_timeout=3)
        client.ping()
        return True
    except Exception:
        logger.warning("health_check: redis unavailable")
        return False


@health_bp.route("/api/v1/health/metrics")
@jwt_required_custom
def health_metrics(**kwargs: object) -> tuple:
    """
    ---
    tags:
      - health
    summary: Métricas de saúde para o footer global (requer autenticação)
    responses:
      200:
        description: Métricas coletadas
    """
    from app.core.auth import get_tenant_schema

    schema = get_tenant_schema()

    db_ok = _check_database()
    redis_ok = _check_redis()
    cameras_active = _count_active_cameras(schema)

    return jsonify({
        "database": db_ok,
        "redis": redis_ok,
        "cameras_active": cameras_active,
    }), 200


_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _count_active_cameras(schema: str) -> int:
    if not _SCHEMA_RE.match(schema):
        logger.warning("health_metrics: invalid schema identifier '%s'", schema)
        return 0
    try:
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return 0
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (schema,))
            cur.execute("SELECT COUNT(*) AS count FROM cameras WHERE status = 'active'")
            row = cur.fetchone()
            return int(row["count"]) if row else 0
    except Exception as exc:
        logger.warning(
            "health_metrics: could not count active cameras (%s: %s)",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        return 0


@health_bp.route("/health/backup")
@health_bp.route("/api/v1/health/backup")
def backup_health() -> tuple:
    """Idade do backup mais novo do banco. 503 quando passa do limite.

    Este endpoint é a metade que FALTAVA do backup. Um `pg_dump` agendado que
    morre não avisa: só deixa de aparecer arquivo novo no bucket, e ninguém
    olha bucket. Foi assim que a spec de 20/08 ficou cinco dias sem ninguém
    perceber que nada rodava.

    Sem autenticação de propósito: é sonda de infraestrutura, e o corpo não
    revela conteúdo — só instante, idade e contagem.

    Fail closed: erro ao listar o storage devolve 503, nunca 200. "Não
    consegui verificar" não pode ler igual a "está tudo bem".
    """
    from app.infrastructure.queue.tasks.backup import (  # noqa: PLC0415
        idade_do_backup_mais_novo,
    )

    try:
        estado = idade_do_backup_mais_novo()
    except Exception as exc:  # noqa: BLE001
        logger.error("backup_health_erro: %s", exc, exc_info=True)
        return jsonify({"saudavel": False, "motivo": "erro ao verificar"}), 503

    return jsonify(estado), (200 if estado.get("saudavel") else 503)
