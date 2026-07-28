"""`python -m app.ota` — one-shot OTA check, invoked by a systemd --user
timer (edge-sync-agent-updater.service/.timer, see deploy/).

Deliberately NOT a long-running loop threaded into `run_daemon()` — see
`updater.py`'s docstring for why the checker must live outside the daemon's
own cgroup.

Env:
  OTA_SOURCE_REPO        (obrigatório) clone git usado como fonte pra `git
                          worktree add` (git fetch roda aqui, nunca aqui
                          o HEAD é alterado).
  OTA_RELEASES_ROOT       dir com um subdir por release (padrão:
                          ~/recognition/releases).
  OTA_CURRENT_SYMLINK     symlink que o unit do daemon usa como
                          WorkingDirectory (padrão: ~/recognition/current).
  OTA_UNIT_NAME           unit systemd --user do daemon (padrão:
                          edge-sync-agent).
  OTA_HEARTBEAT_SENTINEL  path tocado pelo heartbeat.py a cada envio bem
                          sucedido — prova de vida pós-restart (padrão:
                          ~/.local/state/recognition/heartbeat.ok).
  OTA_CHANNEL             canal de release (padrão: dev).
  OTA_KEEP_LAST           releases a manter no disco (padrão: 3).
  DEVICE_ID, EDGE_API_URL, EDGE_DEVICE_KEY_PATH — mesma identidade do
                          daemon (PR-A); a chave já deve existir (o
                          updater não enrola, só lê a identidade).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import httpx

from ..auth.token_manager import TokenManagerError, build_token_manager_from_env
from . import client, updater

logger = logging.getLogger(__name__)

_DEFAULT_RELEASES_ROOT = str(Path.home() / "recognition" / "releases")
_DEFAULT_CURRENT_SYMLINK = str(Path.home() / "recognition" / "current")
_DEFAULT_UNIT_NAME = "edge-sync-agent"
_DEFAULT_SENTINEL = str(Path.home() / ".local" / "state" / "recognition" / "heartbeat.ok")
_DEFAULT_CHANNEL = "dev"
_DEFAULT_KEEP_LAST = 3


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    source_repo = os.environ.get("OTA_SOURCE_REPO", "")
    if not source_repo:
        logger.error("OTA_SOURCE_REPO é obrigatório")
        return 2

    releases_root = os.environ.get("OTA_RELEASES_ROOT", _DEFAULT_RELEASES_ROOT)
    current_symlink = os.environ.get("OTA_CURRENT_SYMLINK", _DEFAULT_CURRENT_SYMLINK)
    unit_name = os.environ.get("OTA_UNIT_NAME", _DEFAULT_UNIT_NAME)
    sentinel_path = os.environ.get("OTA_HEARTBEAT_SENTINEL", _DEFAULT_SENTINEL)
    channel = os.environ.get("OTA_CHANNEL", _DEFAULT_CHANNEL)
    keep_last = int(os.environ.get("OTA_KEEP_LAST", str(_DEFAULT_KEEP_LAST)))
    cloud_url = os.environ.get("EDGE_API_URL", "")

    try:
        token_manager = build_token_manager_from_env()
    except TokenManagerError as exc:
        logger.error("ota_no_identity %s — device precisa estar enrolado antes do OTA", exc)
        return 2
    if not token_manager.has_valid_identity():
        logger.error("ota_no_identity: device ainda não enrolado — nada a fazer")
        return 2

    http_client = httpx.Client()

    def _fetch_target_ref() -> str:
        return client.fetch_target_ref(http_client, cloud_url, token_manager, channel=channel)

    try:
        result = updater.run_once(
            source_repo=source_repo,
            releases_root=releases_root,
            current_symlink=current_symlink,
            unit_name=unit_name,
            sentinel_path=sentinel_path,
            fetch_target_ref=_fetch_target_ref,
            keep_last=keep_last,
        )
    except client.TargetFetchError as exc:
        logger.warning("ota_target_fetch_failed %s — tenta de novo no próximo tick do timer", exc)
        return 1

    logger.info(
        "ota_run_once action=%s ref=%s rolled_back=%s healthy=%s",
        result.action, result.ref, result.rolled_back, result.healthy,
    )
    return 0 if result.healthy else 1


if __name__ == "__main__":
    sys.exit(main())
