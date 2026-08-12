"""Command poller: consumes edge_commands from the cloud and acks results.

Polls GET /api/v1/edge/commands/pending (device auth) and applies supported
command types:

  - update_camera_config → ConfigPoller.apply_camera_config (in-memory, no restart)
  - capture_snapshot → SnapshotExecutor.capture_and_upload (ONVIF/RTSP
    capture + multipart upload — see snapshot_executor.py). Processed
    SEQUENTIALLY within a poll batch (never concurrently — the gravador is a
    single device serving the whole site's recording, not just triage
    snapshots) with a short delay between successive captures
    (*snapshot_delay_s*) so a batch of 29 draft cameras never hammers it.
    Anti-lockout: once `snapshot_executor.circuit_open` trips (a 401/403 from
    the recorder), every remaining/future capture_snapshot command is failed
    immediately with reason="auth" WITHOUT even attempting the recorder
    again — see snapshot_executor.py's docstring.
  - run_propagation → launches training/propagate_seeded.py (the SAME executor
    the RunPod path embeds via heredoc, task "propagação no edge") as a
    transient systemd --user service, budgeted (MemoryMax/CPUQuota from the
    command payload, live view on the box must never starve).

Unknown command types are acked as failed with result={'reason': 'unsupported'}
so the queue never clogs. Every command is acked exactly once per poll cycle
via PATCH /api/v1/edge/commands/<command_id>.

Same pattern as ConfigPoller: injected http_client, run(stop_event) loop.
"""

import contextlib
import glob
import logging
import os
import subprocess  # noqa: S404 — systemd-run é o único jeito de orçar CPU/mem do executor
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL = 60.0  # 1 minute
_DEFAULT_SNAPSHOT_DELAY_S = 2.0
_CAPTURE_SNAPSHOT = "capture_snapshot"

_DEFAULT_PROPAGATION_PYTHON = os.path.expanduser("~/envs/propagation/bin/python")
_DEFAULT_PROPAGATION_RUN_DIR = os.path.expanduser("~/run")
_DEFAULT_MEM_MAX = "6G"
_DEFAULT_CPU_QUOTA = "400%"
_CUDA_LIB_PATH = "/usr/local/cuda/lib64"
_LAUNCH_TIMEOUT_S = 30.0

# payload key (services/api/.../tasks/propagation.py::_dispatch_edge_command)
# -> nome de env esperado por training/propagate_seeded.py.
_PROPAGATION_ENV_NAME_BY_KEY = {
    "manifest_url": "MANIFEST_URL",
    "callback_url": "CALLBACK_URL",
    "callback_token": "CALLBACK_TOKEN",
    "sam_weights_url": "SAM_WEIGHTS_URL",
    "sam_weights_sha256": "SAM_WEIGHTS_SHA256",
    "dinov2_weights_url": "DINOV2_WEIGHTS_URL",
    "dinov2_weights_sha256": "DINOV2_WEIGHTS_SHA256",
    "similarity_threshold": "SIMILARITY_THRESHOLD",
    "progress_every_n": "PROGRESS_EVERY_N",
    "max_results": "MAX_RESULTS",
}
_PROPAGATION_REQUIRED_KEYS = ("job_id", "manifest_url", "callback_url", "callback_token")


def default_propagation_executor_path() -> str:
    """training/propagate_seeded.py a partir do checkout do repo no box —
    services/edge-sync-agent/app/command_poller.py está 3 níveis abaixo da
    raiz do repo. Sobreponível via PROPAGATION_EXECUTOR_PATH (main.py) —
    este default só vale quando o box tem o MESMO layout de monorepo."""
    return str(Path(__file__).resolve().parents[3] / "training" / "propagate_seeded.py")


def _derive_ld_library_path(propagation_python: str) -> str:
    """LD_LIBRARY_PATH pra `import torch` achar `libcudss.so.0` — landmine
    registrada em docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.5 (shootout de
    Qualidade 2026-07-18, revalidada pelo agente do box na task de
    propagação-no-edge): a wheel torch 2.11 jp6/cu126 puxa
    `nvidia-cudss-cu12`, mas o `.so` instalado NÃO fica no loader path por
    padrão — sem esta variável, `import torch` morre com
    "libcudss.so.0: cannot open shared object" mesmo com o pacote presente
    no venv. Precisa estar setada ANTES do `import torch` do executor —
    por isso vai no MESMO arquivo de env injetado pelo systemd via
    `-p EnvironmentFile=` (ver `_run_propagation`).

    Descoberta via `glob` no venv real (robusto a qual python3.1x o venv
    de propagação de fato usa) — cai pro caminho documentado (`python3.10`,
    o mesmo do `train-venv` do shootout) se o venv ainda não existir no
    disco no instante em que o comando chega."""
    venv_root = os.path.dirname(os.path.dirname(os.path.expanduser(propagation_python)))
    candidates = sorted(glob.glob(
        os.path.join(venv_root, "lib", "python3.*", "site-packages", "nvidia", "cu12", "lib")
    ))
    nvidia_cu12_lib = candidates[0] if candidates else os.path.join(
        venv_root, "lib", "python3.10", "site-packages", "nvidia", "cu12", "lib",
    )
    return f"{nvidia_cu12_lib}:{_CUDA_LIB_PATH}"


class CommandPoller:
    """Periodically fetches pending edge commands and executes them."""

    def __init__(
        self,
        http_client: Any,
        cloud_url: str,
        token: str,
        config_poller: Any,
        poll_interval_s: float = _DEFAULT_INTERVAL,
        snapshot_executor: Any = None,
        snapshot_delay_s: float = _DEFAULT_SNAPSHOT_DELAY_S,
        sleep_fn: Any = time.sleep,
        propagation_python: Optional[str] = None,
        propagation_executor_path: Optional[str] = None,
        propagation_run_dir: Optional[str] = None,
    ) -> None:
        self._http = http_client
        base = cloud_url.rstrip("/")
        self._pending_url = f"{base}/api/v1/edge/commands/pending"
        self._ack_url_base = f"{base}/api/v1/edge/commands"
        self._token = token
        self._config_poller = config_poller
        self._interval = poll_interval_s
        self._snapshot_executor = snapshot_executor
        self._snapshot_delay_s = snapshot_delay_s
        self._sleep = sleep_fn
        self._propagation_python = propagation_python or _DEFAULT_PROPAGATION_PYTHON
        self._propagation_executor_path = (
            propagation_executor_path or default_propagation_executor_path()
        )
        self._propagation_run_dir = propagation_run_dir or _DEFAULT_PROPAGATION_RUN_DIR

    # ── internal ─────────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _poll_once(self) -> int:
        """Fetch and handle pending commands. Returns number handled."""
        try:
            resp = self._http.get(
                self._pending_url,
                headers=self._headers(),
                timeout=15.0,
            )
            if resp.status_code != 200:
                logger.warning("command_poll_failed status=%d", resp.status_code)
                return 0
            body = resp.json() or {}
            # API envelope: {"status": "success", "data": {"commands": [...]}}
            data = body.get("data") if isinstance(body.get("data"), dict) else body
            commands = data.get("commands") or []
        except Exception as exc:
            logger.warning("command_poll_error %s", exc)
            return 0

        handled = 0
        snapshots_seen = 0
        for cmd in commands:
            if cmd.get("command_type") == _CAPTURE_SNAPSHOT:
                breaker_open = (
                    self._snapshot_executor is not None and self._snapshot_executor.circuit_open
                )
                # Sequential, never a burst: sleep BETWEEN successive
                # captures in this batch (not before the first one, not
                # after the last command overall) — the recorder is shared
                # with actual site recording, not just triage snapshots.
                # Skipped once the breaker is open: no recorder call is
                # about to happen (fail-fast ack in _handle_capture_snapshot),
                # so there is nothing left to rate-limit.
                if snapshots_seen > 0 and not breaker_open:
                    self._sleep(self._snapshot_delay_s)
                snapshots_seen += 1
            self._handle(cmd)
            handled += 1
        return handled

    def _handle(self, cmd: dict) -> None:
        command_id = cmd.get("command_id")
        if not command_id:
            logger.warning("command_without_id ignored")
            return
        command_type = cmd.get("command_type")
        payload = cmd.get("payload") or {}

        if command_type == "update_camera_config":
            try:
                applied = self._config_poller.apply_camera_config(
                    payload.get("camera_id"),
                    payload.get("fps_target"),
                    payload.get("quality_preset"),
                    payload.get("collection_subtype"),
                )
                self._ack(command_id, "done", {"applied": bool(applied)})
            except Exception as exc:
                logger.warning("command_apply_error id=%s %s", command_id, exc)
                self._ack(command_id, "failed", {"reason": str(exc)})
        elif command_type == _CAPTURE_SNAPSHOT:
            self._handle_capture_snapshot(command_id, payload)
        elif command_type == "run_propagation":
            try:
                result = self._run_propagation(payload)
                self._ack(command_id, "done", result)
            except Exception as exc:
                # ⛔ str(exc) nunca inclui o conteúdo do payload (token) — as
                # exceções levantadas abaixo citam só nomes de campo/caminhos.
                logger.warning("command_apply_error id=%s %s", command_id, exc)
                self._ack(command_id, "failed", {"reason": str(exc)})
        else:
            # Unknown type: ack failed so the queue never clogs.
            logger.warning("command_unsupported type=%s id=%s", command_type, command_id)
            self._ack(command_id, "failed", {"reason": "unsupported"})

    def _handle_capture_snapshot(self, command_id: str, payload: dict) -> None:
        if self._snapshot_executor is None:
            logger.warning("command_capture_snapshot_no_executor id=%s", command_id)
            self._ack(command_id, "failed", {"reason": "unsupported"})
            return

        camera_id = payload.get("camera_id")
        if not camera_id:
            self._ack(command_id, "failed", {"reason": "invalid_payload"})
            return

        if self._snapshot_executor.circuit_open:
            # Breaker already tripped (this batch or an earlier poll cycle):
            # fail fast, never touch the recorder again until restart.
            logger.warning(
                "command_capture_snapshot_circuit_open id=%s reason=%s — pulando sem tentar",
                command_id, self._snapshot_executor.circuit_reason,
            )
            self._ack(
                command_id, "failed",
                {"reason": "auth", "detail": self._snapshot_executor.circuit_reason},
            )
            return

        result = self._snapshot_executor.capture_and_upload(camera_id, payload.get("channel"))
        if result.get("ok"):
            self._ack(command_id, "done", {"captured": True})
        else:
            self._ack(
                command_id, "failed",
                {"reason": result.get("reason", "capture_failed"), "detail": result.get("detail")},
            )

    def _run_propagation(self, payload: dict) -> dict:
        """Lança `training/propagate_seeded.py` — o MESMO executor do
        caminho RunPod (`services/api/.../tasks/propagation.py::
        _dispatch_edge_command` monta este payload) — como uma unit
        transiente `systemd-run --user --scope`, orçada (MemoryMax/
        CPUQuota do payload — live view do box nunca pode ser espremido).

        A CONCLUSÃO do job (completed/failed) chega por fora, via callback
        HTTP do próprio executor pro backend (`CALLBACK_URL`/
        `CALLBACK_TOKEN`) — esta função só confirma que a unit SUBIU; erro
        de lançamento (systemd-run falhou, payload incompleto) vira 'failed'
        aqui mesmo, sem nunca subir a unit.
        """
        missing = [k for k in _PROPAGATION_REQUIRED_KEYS if not payload.get(k)]
        if missing:
            raise ValueError(f"payload incompleto — faltando: {sorted(missing)}")
        job_id = str(payload["job_id"])

        run_dir = Path(self._propagation_run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        # WORK_DIR gravável pro executor — o default /root do executor é do
        # pod RunPod (container rodando como root); aqui é systemd --user.
        work_dir = run_dir / f"propagation-work-{job_id}"
        work_dir.mkdir(parents=True, exist_ok=True)
        env_path = run_dir / f"propagation-{job_id}.env"
        self._write_propagation_env_file(env_path, payload, work_dir)

        mem_max = payload.get("mem_max") or _DEFAULT_MEM_MAX
        cpu_quota = payload.get("cpu_quota") or _DEFAULT_CPU_QUOTA
        unit_name = f"propagation-{job_id[:8]}"

        # Unit transiente de SERVIÇO (não --scope): `-p EnvironmentFile=`
        # existe em [Service] e o systemd lê o arquivo LITERAL, linha a
        # linha, SEM interpretação de shell. A 1ª versão usava --scope +
        # wrapper `set -a; . env` — e URL presignada com `&` numa linha de
        # atribuição de shell manda o resto pra background e a variável SE
        # PERDE (bug real no box: executor subia com CALLBACK_URL mas sem
        # MANIFEST_URL). Serviço transiente também é detached: o
        # systemd-run retorna assim que a unit sobe, sem bloquear o poller
        # pela duração do job (--scope roda em foreground). LD_LIBRARY_PATH
        # (landmine libcudss, REGRAS_PLATAFORMA_JETSON.md §3.5) vai no
        # mesmo arquivo 0600 — token/paths nunca em argv/`ps`/log.
        # `--collect` recolhe a unit mesmo se falhar (senão o nome fica
        # preso e um re-disparo do MESMO job não sobe).
        argv = [
            "systemd-run", "--user", f"--unit={unit_name}", "--collect",
            "-p", f"MemoryMax={mem_max}", "-p", f"CPUQuota={cpu_quota}",
            "-p", f"EnvironmentFile={env_path}",
            "--", self._propagation_python, self._propagation_executor_path,
        ]
        try:
            subprocess.run(  # noqa: S603 — argv fixo + valores validados/quotados acima
                argv, check=True, capture_output=True, text=True, timeout=_LAUNCH_TIMEOUT_S,
            )
        except Exception:
            # Lançamento falhou — a unit nunca subiu, o arquivo de env
            # (com o callback_token) não precisa sobreviver no disco.
            with contextlib.suppress(OSError):
                os.remove(str(env_path))
            raise
        return {"launched": True, "unit": unit_name}

    def _write_propagation_env_file(
        self, env_path: Path, payload: dict, work_dir: Path
    ) -> None:
        """Escreve o arquivo de env 0600 — CALLBACK_TOKEN e demais valores
        do payload NUNCA em argv/log (só neste arquivo, lido pelo systemd
        via `EnvironmentFile=`). Valores LITERAIS, sem quoting de shell —
        o parser do systemd lê linha a linha e NÃO interpreta `&`/`?`/`$`
        (regressão do bug real da 1ª execução no Orin, 2026-08-11: com
        wrapper `source` bash, a URL presignada com `&` quebrava a linha e
        MANIFEST_URL se perdia). Modo 0600 aplicado ANTES de qualquer
        conteúdo (`os.open` com o modo já na criação — nunca uma janela em
        que o arquivo existe legível por outros usuários do box)."""
        lines = []
        for key, env_name in _PROPAGATION_ENV_NAME_BY_KEY.items():
            value = payload.get(key)
            if value is None or value == "":
                continue
            lines.append(f"{env_name}={value}")
        lines.append(f"WORK_DIR={work_dir}")
        lines.append(f"LD_LIBRARY_PATH={_derive_ld_library_path(self._propagation_python)}")
        content = "\n".join(lines) + "\n"

        fd = os.open(str(env_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(content)
        except Exception:
            with contextlib.suppress(OSError):
                os.remove(str(env_path))
            raise
        os.chmod(str(env_path), 0o600)  # defesa em profundidade (ex.: umask do processo)

    def _ack(self, command_id: str, status: str, result: Optional[dict]) -> None:
        try:
            resp = self._http.patch(
                f"{self._ack_url_base}/{command_id}",
                json={"status": status, "result": result},
                headers=self._headers(),
                timeout=15.0,
            )
            if resp.status_code != 200:
                logger.warning(
                    "command_ack_failed id=%s status=%d", command_id, resp.status_code
                )
        except Exception as exc:
            logger.warning("command_ack_error id=%s %s", command_id, exc)

    # ── main loop ────────────────────────────────────────────────────────────

    def run(self, stop_event: threading.Event) -> None:
        """Poll commands continuously until *stop_event* is set."""
        while not stop_event.is_set():
            self._poll_once()
            stop_event.wait(timeout=self._interval)
