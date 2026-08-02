"""
Recognition — Local Filesystem Storage (fallback when R2 not configured).

Implements StorageStrategy using local filesystem.
Files stored under storage/ directory.
"""
import logging
import os
import shutil
import time
from typing import NoReturn

from app.core.exceptions import StorageError
from app.infrastructure.storage.base import StorageStrategy

logger = logging.getLogger(__name__)

# EX_CONFIG (sysexits.h) — separa "processo recusou subir por config errada"
# de "processo crashou" nos logs do Railway.
STORAGE_CONFIG_EXIT_CODE = 78

# Tentativas + backoff do preflight de conectividade R2 (item 3, mutirão 2.1).
_PREFLIGHT_ATTEMPTS = 3
_PREFLIGHT_BACKOFF_SECONDS = 1.0


class LocalStorage(StorageStrategy):
    """Filesystem-based storage for development and R2 fallback."""

    def __init__(self, base_dir: str = "storage") -> None:
        self._base_dir = os.path.realpath(os.path.abspath(base_dir))
        os.makedirs(self._base_dir, exist_ok=True)
        logger.info("local_storage_initialized: base_dir=%s", self._base_dir)

    def _full_path(self, key: str) -> str:
        """Resolve key to full filesystem path. Prevents traversal."""
        full = os.path.realpath(os.path.join(self._base_dir, key))
        if not full.startswith(self._base_dir + os.sep) and full != self._base_dir:
            raise StorageError("Path traversal detected")
        return full

    def generate_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", ttl: int = 900
    ) -> str:
        """Local storage: returns the API upload endpoint path."""
        return f"/api/storage/upload/{key}"

    def generate_presigned_download_url(
        self, key: str, ttl: int = 3600, response_content_type: str | None = None
    ) -> str:
        """Local storage: returns the API download endpoint path."""
        return f"/api/storage/download/{key}"

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        """Write bytes to local file."""
        path = self._full_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        logger.debug("local_upload: key=%s, size=%d", key, len(data))

    def download_bytes(self, key: str) -> bytes:
        """Read bytes from local file."""
        path = self._full_path(key)
        if not os.path.exists(path):
            raise StorageError(f"File not found: {key}")
        with open(path, "rb") as f:
            return f.read()

    def upload_file(self, key: str, local_path: str) -> None:
        """Copy local file to storage."""
        dest = self._full_path(key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(local_path, dest)
        logger.debug("local_upload_file: key=%s", key)

    def delete(self, key: str) -> None:
        """Delete file from storage."""
        path = self._full_path(key)
        if os.path.exists(path):
            os.remove(path)

    def exists(self, key: str) -> bool:
        """Check if file exists."""
        return os.path.exists(self._full_path(key))

    def list_keys(self, prefix: str) -> list[str]:
        """List files with prefix."""
        base = self._full_path(prefix)
        if not os.path.isdir(base):
            parent = os.path.dirname(base)
            if not os.path.isdir(parent):
                return []
            base_prefix = os.path.basename(base)
            return [
                os.path.join(prefix, f)
                for f in os.listdir(parent)
                if f.startswith(base_prefix)
            ]
        result = []
        for root, dirs, files in os.walk(base):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, self._base_dir)
                result.append(rel)
        return result

    def copy_object(self, src_key: str, dest_key: str) -> None:
        """Copy object within local storage using filesystem copy."""
        src = self._full_path(src_key)
        dest = self._full_path(dest_key)
        if not os.path.exists(src):
            raise StorageError(f"Copy failed: source not found: {src_key}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
        logger.debug("local_copy: src=%s, dest=%s", src_key, dest_key)


def _is_production() -> bool:
    """Produção Railway = RAILWAY_ENVIRONMENT_NAME == 'production'.

    Railway nomeia o ambiente de dev "Desenvolvimento" (não "development"),
    então qualquer outro valor (incluindo ausente — fora do Railway) NÃO é
    produção. Não confundir com `RAILWAY_ENVIRONMENT` (variável legada, sem
    uso hoje neste módulo).
    """
    return os.environ.get("RAILWAY_ENVIRONMENT_NAME") == "production"


def get_storage(tenant_id: str | None = None) -> StorageStrategy:
    """Factory: R2Storage se configurado; LocalStorage só com opt-in explícito.

    Credenciais via `resolve_r2_credentials` (integration store do tenant >
    env de plataforma — mesmo padrão do Vast.ai em `resolve_vast_api_key`).
    Sem `tenant_id`, a resolução pula direto pro env de plataforma, que é o
    comportamento histórico desta factory.

    SEM FALLBACK SILENCIOSO (auditoria da cadeia frame→R2→anotação): antes,
    qualquer credencial faltando degradava pra LocalStorage sem um ruído
    sequer — o que num container Railway significa gravar em disco EFÊMERO.
    O endpoint devolvia 201, o edge achava que tinha funcionado, e as imagens
    sumiam no próximo deploy.

    Mutirão 2.1 (D-03) inverteu o default: modo efêmero deixou de ser "o que
    sobra quando falta credencial" e virou opt-in explícito.

      - as 3 credenciais presentes                         -> R2Storage;
      - config PARCIAL (1-2 de 3)                          -> erro, sempre;
      - nenhuma presente, sem ALLOW_EPHEMERAL_STORAGE=1     -> erro, sempre
        (antes só errava dentro do Railway — agora erra em qualquer lugar,
        inclusive dev local, a menos que o opt-in seja explícito);
      - nenhuma presente, ALLOW_EPHEMERAL_STORAGE=1 em produção -> erro
        (efêmero é PROIBIDO em produção, não importa o opt-in);
      - nenhuma presente, ALLOW_EPHEMERAL_STORAGE=1 fora de produção
        -> LocalStorage + `logger.warning` estruturado (degraded_config=true).

    Todos os erros aqui são `StorageError` (uma Exception normal) — não
    `SystemExit`. Esta função roda em 11+ call sites de request/task (ex.:
    `GET /api/v1/storage/health`), a maioria com `except Exception` esperando
    exatamente isso. Quem precisa matar o PROCESSO (não a request) por
    configuração inválida é `ensure_storage_ready()`, chamada 1x no boot.

    `bucket` fica fora dessa conta de propósito: tem default não-vazio
    (`epi-monitor`, ver integration_service.resolve_r2_credentials), então
    nunca ajudaria a distinguir "configurado" de "não configurado".
    """
    from app.domain.services.integration_service import resolve_r2_credentials

    creds = resolve_r2_credentials(tenant_id)
    required = {
        "R2_ENDPOINT": creds["endpoint"],
        "R2_KEY": creds["access_key"],
        "R2_SECRET": creds["secret_key"],
    }
    present = [name for name, value in required.items() if value]
    missing = [name for name, value in required.items() if not value]

    if not missing:
        from app.infrastructure.storage.r2_storage import R2Storage

        return R2Storage(
            endpoint=creds["endpoint"],
            bucket=creds["bucket"],
            access_key=creds["access_key"],
            secret_key=creds["secret_key"],
        )

    if present:
        raise StorageError(
            "Storage R2 configurado pela METADE — presentes: "
            f"{', '.join(sorted(present))}; faltando: {', '.join(sorted(missing))}. "
            "Recusando cair em LocalStorage: num deploy isso gravaria em disco "
            "efêmero e as imagens sumiriam no próximo restart. "
            "Configure as 3 ou nenhuma."
        )

    # Nenhuma credencial presente. Modo efêmero exige ALLOW_EPHEMERAL_STORAGE=1
    # explícito — deixar de configurar R2 não basta mais pra "escolher" disco
    # efêmero (default invertido, decisão D-03 do mutirão 2.1).
    if os.environ.get("ALLOW_EPHEMERAL_STORAGE") != "1":
        raise StorageError(
            "Storage R2 não configurado — faltando: "
            f"{', '.join(sorted(missing))}. Sem R2, uploads seriam gravados em "
            "disco EFÊMERO e perdidos no próximo redeploy/restart. Configure "
            "R2_ENDPOINT, R2_KEY e R2_SECRET, ou defina "
            "ALLOW_EPHEMERAL_STORAGE=1 explicitamente (proibido em produção)."
        )

    if _is_production():
        raise StorageError(
            "ALLOW_EPHEMERAL_STORAGE=1 detectado com RAILWAY_ENVIRONMENT_NAME="
            "'production'. Storage efêmero é PROIBIDO em produção — configure "
            "R2_ENDPOINT, R2_KEY e R2_SECRET."
        )

    base = os.environ.get("STORAGE_DIR", "storage")
    logger.warning(
        "storage_ephemeral_allowed: degraded_config=true — "
        "ALLOW_EPHEMERAL_STORAGE=1 ativo, sem credenciais R2, gravando em "
        "disco EFÊMERO (%r). Uploads serão perdidos no próximo deploy/restart. "
        "Aceitável só fora de produção.",
        base,
    )
    return LocalStorage(base)


def _exit_config(message: str) -> NoReturn:
    """Mata o PROCESSO com EX_CONFIG (78) — só chamado no boot (nunca em
    request/task). Loga a mensagem completa (nomes de env, nunca valores)
    antes de sair, pra aparecer no log do Railway como causa raiz."""
    logger.critical(message)
    raise SystemExit(STORAGE_CONFIG_EXIT_CODE)


def ensure_storage_ready() -> StorageStrategy | None:
    """Preflight de storage — chamado 1x no BOOT do processo (API e Celery
    worker), nunca em request/task.

    Reusa `get_storage()` como único ponto de verdade da decisão de config
    (R2 completo / parcial-erro / efêmero opt-in / efêmero proibido em
    produção) e converte qualquer `StorageError` daí em `SystemExit(78)` —
    aqui, matar o processo inteiro é seguro e desejado: é boot, não request.

    Se resolveu R2Storage, ainda falta confirmar que a credencial é válida e
    o bucket existe de fato (`get_storage()` só olha se a env está setada,
    não se ela FUNCIONA) — isso é o preflight real: `head_bucket` com
    timeout curto e `_PREFLIGHT_ATTEMPTS` tentativas com backoff. Falhou nas
    N tentativas (credencial expirada, bucket errado, endpoint fora do ar)
    -> mesma morte com SystemExit(78).

    Retorna a instância de storage resolvida (LocalStorage/R2Storage) só
    para facilitar teste/asserção — o boot em si não precisa do retorno.
    """
    try:
        storage = get_storage()
    except StorageError as exc:
        _exit_config(str(exc))

    from app.infrastructure.storage.r2_storage import R2Storage

    if not isinstance(storage, R2Storage):
        return storage  # LocalStorage — efêmero explicitamente permitido

    last_error: Exception | None = None
    for attempt in range(1, _PREFLIGHT_ATTEMPTS + 1):
        try:
            storage.check_connectivity()
            logger.info(
                "storage_preflight_ok: attempt=%d/%d", attempt, _PREFLIGHT_ATTEMPTS
            )
            return storage
        except StorageError as exc:
            last_error = exc
            logger.warning(
                "storage_preflight_attempt_failed: attempt=%d/%d, error=%s",
                attempt, _PREFLIGHT_ATTEMPTS, exc,
            )
            if attempt < _PREFLIGHT_ATTEMPTS:
                time.sleep(_PREFLIGHT_BACKOFF_SECONDS * attempt)

    _exit_config(
        "Preflight de conectividade R2 (head_bucket) falhou após "
        f"{_PREFLIGHT_ATTEMPTS} tentativas: {last_error}. Credencial pode "
        "estar expirada, ou o bucket configurado não existe. Verifique "
        "R2_ENDPOINT, R2_KEY, R2_SECRET e o bucket."
    )
    return None  # pragma: no cover — _exit_config sempre levanta SystemExit
