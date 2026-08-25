"""Backup do PostgreSQL para o R2 — com DRILL, não só com dump.

═══ POR QUE ISTO EXISTE ═══

Auditado em 2026-08-25: a spec de 20/08 pedia `pg_dump` → R2 2×/dia com drill.
Nada disso existia. O que havia no R2 era UM objeto:

    backups/postgres/pre-patch-2026-08-20.sql.gz   10,0 MB   2026-08-20 12:55

Um dump manual avulso, do mesmo dia da spec. Zero `pg_dump` no código de
aplicação, zero SERVICE_TYPE de backup, e `postgresql` nem estava no `nixPkgs`
— o binário não existia na imagem.

═══ DUMP SEM DRILL É UM ARQUIVO, NÃO UM BACKUP ═══

Um `.sql.gz` no bucket prova que ALGO subiu. Não prova que dá para restaurar.
Um dump truncado, um dump de um banco vazio e um dump bom são todos objetos de
tamanho plausível. Por isso toda execução aqui termina com um DRILL: relê o
objeto DO R2 (não o arquivo local), descomprime e confere marcadores estruturais
— senão o que se está monitorando é o upload, não o backup.

═══ SILÊNCIO É O MODO DE FALHA QUE IMPORTA ═══

Backup que para de rodar não avisa: só deixa de aparecer arquivo novo, e
ninguém olha bucket. Por isso o par desta tarefa é
`GET /health/backup` (api/v1/health), que devolve a IDADE do backup mais novo e
falha quando ela passa do limite. A tarefa produz; o endpoint denuncia a
ausência.

═══ SEGREDO NUNCA EM ARGV ═══

`pg_dump` aceita a URI inteira como argumento, e aí a senha aparece em `ps` e
em qualquer log de processo. Aqui a URL é partida e a senha vai por `PGPASSWORD`
no environment do subprocesso — nunca na linha de comando.
"""
from __future__ import annotations

import gzip
import logging
import os
import shutil
import subprocess  # noqa: S404 — pg_dump, argv fixo, sem shell
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlparse

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

#: Prefixo dos backups automáticos. Separado do `backups/postgres/` solto para
#: não confundir dump manual de emergência com a série do serviço.
PREFIXO_BACKUP = "backups/postgres/auto"

#: Idade máxima aceitável do backup mais novo. Com 2×/dia, 26h dá folga para um
#: atraso de agendamento sem virar alarme falso.
IDADE_MAXIMA_H = 26

#: Abaixo disto o dump é pequeno demais para ser este banco (225 MB cru,
#: ~10 MB comprimido em ago/2026). Não é uma medida de qualidade — é o piso que
#: separa "dump vazio" de "dump".
TAMANHO_MINIMO_BYTES = 512 * 1024

#: Marcadores que um dump íntegro deste banco tem de conter. Tabelas centrais e
#: o rodapé que o pg_dump só escreve quando termina.
MARCADORES = (b"CREATE TABLE public.alerts", b"CREATE TABLE public.cameras")
RODAPE = b"PostgreSQL database dump complete"


def _ambiente_pg(url: str) -> tuple[list[str], dict[str, str]]:
    """Parte a URL em argv (sem senha) + env (com senha).

    A senha JAMAIS entra em argv: `pg_dump 'postgres://user:senha@host/db'`
    deixa a credencial visível em `ps aux` e em qualquer coletor de processo.
    """
    p = urlparse(url)
    if not p.hostname or not p.path:
        raise ValueError("DATABASE_URL sem host ou database")

    args = [
        "--host", p.hostname,
        "--port", str(p.port or 5432),
        "--username", unquote(p.username or "postgres"),
        "--dbname", p.path.lstrip("/"),
    ]
    env = dict(os.environ)
    if p.password:
        env["PGPASSWORD"] = unquote(p.password)
    # Railway exige TLS; sem isto o pg_dump tenta sem e o servidor recusa.
    env.setdefault("PGSSLMODE", "require")
    return args, env


def _versao_pg_dump() -> str | None:
    exe = shutil.which("pg_dump")
    if not exe:
        return None
    try:
        saida = subprocess.run(  # noqa: S603 — argv fixo, sem shell
            [exe, "--version"], capture_output=True, text=True, timeout=30, check=True
        )
        return saida.stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def _drill(bruto: bytes) -> dict:
    """Confere se o que voltou do R2 é um dump restaurável deste banco.

    Não é um restore de verdade (isso exigiria um Postgres descartável, e é o
    passo seguinte). É o que dá para afirmar com honestidade a cada execução:
    o objeto descomprime, tem as tabelas centrais e tem o rodapé que o
    `pg_dump` só escreve depois de terminar. Um dump truncado por timeout ou
    disco cheio falha exatamente aqui.
    """
    achados = {
        "descomprimiu": False,
        "tamanho_descomprimido": 0,
        "marcadores": [],
        "tem_rodape": False,
    }
    texto = gzip.decompress(bruto)
    achados["descomprimiu"] = True
    achados["tamanho_descomprimido"] = len(texto)
    achados["marcadores"] = [m.decode() for m in MARCADORES if m in texto]
    achados["tem_rodape"] = RODAPE in texto
    achados["ok"] = (
        achados["tem_rodape"]
        and len(achados["marcadores"]) == len(MARCADORES)
        and achados["tamanho_descomprimido"] > TAMANHO_MINIMO_BYTES
    )
    return achados


def _storage():
    from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

    # Backup é do banco INTEIRO, não de um tenant. Storage sem tenant = bucket raiz.
    return get_storage(None)


@celery.task(name="tasks.backup.backup_database", bind=True, max_retries=2)
def backup_database(self, prefixo: str | None = None) -> dict:  # noqa: ANN001
    """pg_dump → gzip → R2, e só devolve sucesso se o DRILL passar.

    Devolve dict com `status`, a chave gravada e o resultado do drill. NUNCA
    devolve sucesso por ter feito upload: se o drill reprovar, o resultado é
    'drill_falhou' e a chave fica lá para inspeção manual — apagar a evidência
    de um backup ruim seria o pior desfecho possível.
    """
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        logger.error("backup_sem_database_url")
        return {"status": "erro", "motivo": "DATABASE_URL ausente"}

    exe = shutil.which("pg_dump")
    if not exe:
        # Não é falha silenciosa: sem o binário não há backup nenhum, e quem
        # olhar o log precisa saber que é a IMAGEM que está faltando peça.
        logger.error(
            "backup_sem_pg_dump: binário não encontrado no PATH — falta "
            "'postgresql' no nixPkgs (nixpacks.toml)"
        )
        return {"status": "erro", "motivo": "pg_dump ausente na imagem"}

    agora = datetime.now(timezone.utc)
    chave = f"{prefixo or PREFIXO_BACKUP}/{agora.strftime('%Y-%m-%dT%H%M%SZ')}.sql.gz"
    args, env = _ambiente_pg(url)

    with tempfile.TemporaryDirectory() as tmp:
        bruto = os.path.join(tmp, "dump.sql")
        try:
            subprocess.run(  # noqa: S603 — argv montado aqui, sem shell, sem input do usuário
                [exe, *args, "--no-owner", "--no-privileges", "--file", bruto],
                env=env, capture_output=True, text=True, timeout=1800, check=True,
            )
        except subprocess.CalledProcessError as exc:
            # stderr do pg_dump não contém a senha (ela foi por env), mas
            # truncamos por precaução — mensagem de erro não é lugar de URL.
            logger.error("backup_pg_dump_falhou: %s", (exc.stderr or "")[:400])
            return {"status": "erro", "motivo": "pg_dump falhou"}
        except subprocess.TimeoutExpired:
            logger.error("backup_pg_dump_timeout")
            return {"status": "erro", "motivo": "pg_dump estourou o tempo"}

        comprimido = bruto + ".gz"
        with open(bruto, "rb") as origem, gzip.open(comprimido, "wb", compresslevel=6) as destino:
            shutil.copyfileobj(origem, destino)
        tamanho = os.path.getsize(comprimido)

        if tamanho < TAMANHO_MINIMO_BYTES:
            logger.error("backup_pequeno_demais: %d bytes — não subindo", tamanho)
            return {"status": "erro", "motivo": f"dump com {tamanho} bytes"}

        armazenamento = _storage()
        armazenamento.upload_file(chave, comprimido)

    # DRILL: relê DO R2, não o arquivo local. O que interessa é se o que ficou
    # gravado presta, não se o que saiu do pg_dump prestava.
    try:
        conferencia = _drill(armazenamento.download_bytes(chave))
    except Exception as exc:  # noqa: BLE001
        logger.error("backup_drill_erro: chave=%s err=%s", chave, exc)
        return {"status": "drill_falhou", "chave": chave, "erro": str(exc)[:200]}

    if not conferencia.get("ok"):
        logger.error("backup_drill_reprovou: chave=%s achados=%s", chave, conferencia)
        return {"status": "drill_falhou", "chave": chave, "drill": conferencia}

    logger.info(
        "backup_ok: chave=%s comprimido=%.1fMB descomprimido=%.1fMB pg_dump=%s",
        chave, tamanho / 1e6, conferencia["tamanho_descomprimido"] / 1e6,
        _versao_pg_dump(),
    )
    return {
        "status": "ok",
        "chave": chave,
        "bytes": tamanho,
        "drill": conferencia,
        "pg_dump": _versao_pg_dump(),
    }


def idade_do_backup_mais_novo(prefixo: str | None = None) -> dict:
    """Idade do backup mais novo, para `GET /health/backup`.

    Fail closed: erro de storage → `saudavel: False`. "Não consegui verificar"
    não pode ler igual a "está tudo bem" — é a mesma regra que a varredura
    desta rodada aplicou em toda parte.
    """
    try:
        chaves = _storage().list_keys(f"{prefixo or PREFIXO_BACKUP}/")
    except Exception as exc:  # noqa: BLE001
        logger.error("backup_health_storage_falhou: %s", exc)
        return {
            "saudavel": False,
            "motivo": "não foi possível listar o storage",
            "erro": str(exc)[:200],
        }

    if not chaves:
        return {"saudavel": False, "motivo": "nenhum backup automático encontrado", "total": 0}

    # A chave carrega o instante: .../2026-08-25T081500Z.sql.gz
    def quando(k: str) -> datetime | None:
        base = k.rsplit("/", 1)[-1].replace(".sql.gz", "")
        try:
            return datetime.strptime(base, "%Y-%m-%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    datas = sorted(d for d in (quando(k) for k in chaves) if d is not None)
    if not datas:
        return {
            "saudavel": False,
            "motivo": "backups sem instante legível no nome",
            "total": len(chaves),
        }

    mais_novo = datas[-1]
    idade = datetime.now(timezone.utc) - mais_novo
    return {
        "saudavel": idade < timedelta(hours=IDADE_MAXIMA_H),
        "mais_novo": mais_novo.isoformat(),
        "idade_horas": round(idade.total_seconds() / 3600, 1),
        "idade_maxima_horas": IDADE_MAXIMA_H,
        "total": len(chaves),
    }
