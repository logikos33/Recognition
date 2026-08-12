"""Ring buffer local de métricas — SQLite com downsample e retenção.

Retenção sem perder nada (requisito do /monitoring):

    resolução  | janela
    10s (fina) | últimas 2h
    1 min      | 48h
    5 min      | 30 dias

O downsample é automático (10s→1m→5m, agregação em `aggregate_records`) e a
retenção apaga o que passou da janela de cada resolução. Volume total ≈ 12k
linhas — o teto de tamanho (`max_db_mb`) e a guarda de disco (`min_free_gb`)
existem como cinto de segurança, não como regime: a reserva intocável de disco
é intertravamento do device por design (ADR-0033/0045) e o ring buffer NUNCA
pode ser o processo que a consome.

Concorrência: o coletor (`python -m app.monitoring`) é o ÚNICO escritor; o
edge-sync-agent lê em modo read-only (URI `mode=ro`) para responder aos
comandos `monitoring.*`. WAL permite leitura concorrente sem lock de escrita.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# resolução → (passo em segundos, retenção em segundos)
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "10s": (10, 2 * 3600),
    "1m": (60, 48 * 3600),
    "5m": (300, 30 * 86400),
}
_EVENTS_RETENTION_S = 30 * 86400
_DEFAULT_MAX_DB_MB = 64
_DEFAULT_MIN_FREE_GB = 8.0
# janela pedida → resolução servida (2h cabe na fina; acima, downsampled)
WINDOW_TO_RESOLUTION: dict[str, tuple[int, str]] = {
    "2h": (2 * 3600, "10s"),
    "24h": (24 * 3600, "1m"),
    "7d": (7 * 86400, "5m"),
    "30d": (30 * 86400, "5m"),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    res  TEXT NOT NULL,
    ts   INTEGER NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (res, ts)
);
CREATE TABLE IF NOT EXISTS events (
    ts     INTEGER NOT NULL,
    kind   TEXT NOT NULL,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def aggregate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega N amostras numa só (downsample 10s→1m→5m).

    Semântica por tipo de folha:
      - número  → média (gauge);
      - bool    → média de 0/1 = FRAÇÃO da janela em que era True (ex.:
                  `throttle.active: 0.3` = 30% da janela com throttle — mais
                  honesto que OR, que apagaria a duração);
      - chave terminada em `_total` → último valor (contador monotônico);
      - string  → último valor;
      - lista de números → média elemento a elemento (ex.: cpu_cores_pct);
      - dict    → recursão.

    Amostras com campos ausentes não zeram a média — cada folha agrega só
    sobre as amostras em que apareceu (regra de honestidade da telemetria:
    nunca inventar métrica).
    """
    if not records:
        return {}
    if len(records) == 1:
        return records[0]

    keys: list[str] = []
    seen: set[str] = set()
    for rec in records:
        for key in rec:
            if key not in seen:
                seen.add(key)
                keys.append(key)

    out: dict[str, Any] = {}
    for key in keys:
        values = [rec[key] for rec in records if key in rec and rec[key] is not None]
        if not values:
            out[key] = None
            continue
        out[key] = _aggregate_leaf(key, values)
    return out


def _aggregate_leaf(key: str, values: list[Any]) -> Any:
    first = values[-1]
    if key.endswith("_total"):
        return first  # contador monotônico: o último valor é o estado
    if isinstance(first, dict):
        dicts = [v for v in values if isinstance(v, dict)]
        return aggregate_records(dicts)
    if isinstance(first, bool):
        bools = [v for v in values if isinstance(v, bool)]
        return round(sum(1 for v in bools if v) / len(bools), 3)
    if isinstance(first, (int, float)):
        nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if not nums:
            return first
        return round(sum(nums) / len(nums), 3)
    if isinstance(first, list):
        lists = [v for v in values if isinstance(v, list)]
        return _aggregate_number_lists(lists)
    return first  # string/qualquer outro: último valor


def _aggregate_number_lists(lists: list[list[Any]]) -> list[Any]:
    """Média elemento a elemento; se os comprimentos divergem (ex.: core
    ligou/desligou no meio da janela), devolve a última lista como está."""
    if not lists:
        return []
    length = len(lists[-1])
    if any(len(lst) != length for lst in lists):
        return lists[-1]
    out = []
    for i in range(length):
        col = [lst[i] for lst in lists if isinstance(lst[i], (int, float))]
        out.append(round(sum(col) / len(col), 2) if col else lists[-1][i])
    return out


class MetricsStore:
    """Escritor do ring buffer (usado só pelo coletor). Thread-safe."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_db_mb: int = _DEFAULT_MAX_DB_MB,
        min_free_gb: float = _DEFAULT_MIN_FREE_GB,
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max_db_bytes = max_db_mb * 1024 * 1024
        self._min_free_bytes = int(min_free_gb * 1024**3)
        self._lock = threading.Lock()
        self._disk_guard_active = False
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── escrita ──────────────────────────────────────────────────────────────

    def insert_sample(self, ts: int, record: dict[str, Any]) -> bool:
        """Grava uma amostra fina (10s). Devolve False se a guarda de disco
        está ativa (disco perto da reserva — parar de escrever é o coletor
        respeitando o intertravamento, nunca o causando)."""
        if self._disk_guard_active:
            return False
        data = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO samples (res, ts, data) VALUES ('10s', ?, ?)",
                (ts, data),
            )
            self._conn.commit()
        return True

    def insert_event(self, ts: int, kind: str, detail: str = "") -> None:
        """Eventos discretos (throttle_start/end, oom_kill, power_mode_change,
        service_restart…). Sempre gravados — são raros e é exatamente o que
        não pode se perder."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, kind, detail) VALUES (?, ?, ?)",
                (ts, kind, detail),
            )
            self._conn.commit()

    # ── downsample + retenção ────────────────────────────────────────────────

    def maintain(self, now: int) -> None:
        """Um passo de manutenção: rollup 10s→1m→5m, retenção, teto de
        tamanho e guarda de disco. Chamado ~1x/min pelo coletor; idempotente."""
        with self._lock:
            self._rollup("10s", "1m", now)
            self._rollup("1m", "5m", now)
            self._prune(now)
            self._conn.commit()
        self._check_disk_guard()

    def _rollup(self, src: str, dst: str, now: int) -> None:
        step, _ = RESOLUTIONS[dst]
        cursor_key = f"rollup_upto_{dst}"
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (cursor_key,)
        ).fetchone()
        # Primeiro rollup: começa no bucket mais antigo disponível na origem.
        if row is None:
            oldest = self._conn.execute(
                "SELECT MIN(ts) FROM samples WHERE res = ?", (src,)
            ).fetchone()[0]
            if oldest is None:
                return
            upto = (oldest // step) * step
        else:
            upto = int(row[0])

        current_bucket = (now // step) * step  # bucket em andamento: não fecha
        while upto < current_bucket:
            bucket_end = upto + step
            rows = self._conn.execute(
                "SELECT data FROM samples WHERE res = ? AND ts >= ? AND ts < ? ORDER BY ts",
                (src, upto, bucket_end),
            ).fetchall()
            if rows:
                records = []
                for (data,) in rows:
                    try:
                        records.append(json.loads(data))
                    except json.JSONDecodeError:
                        continue
                if records:
                    merged = aggregate_records(records)
                    merged["ts"] = upto
                    merged["agg_n"] = len(records)
                    self._conn.execute(
                        "INSERT OR REPLACE INTO samples (res, ts, data) VALUES (?, ?, ?)",
                        (dst, upto, json.dumps(merged, ensure_ascii=False, separators=(",", ":"))),
                    )
            upto = bucket_end
            self._conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (cursor_key, str(upto)),
            )

    def _prune(self, now: int) -> None:
        for res, (_, retention) in RESOLUTIONS.items():
            self._conn.execute(
                "DELETE FROM samples WHERE res = ? AND ts < ?", (res, now - retention)
            )
        self._conn.execute("DELETE FROM events WHERE ts < ?", (now - _EVENTS_RETENTION_S,))
        # Teto de tamanho: nunca deveria disparar com esse volume; se disparar,
        # sacrifica o histórico mais antigo da resolução mais grossa primeiro.
        try:
            size = self._path.stat().st_size
        except OSError:
            return
        if size > self._max_db_bytes:
            logger.warning(
                "metrics_store_acima_do_teto size_mb=%.1f — apagando histórico antigo",
                size / 1024 / 1024,
            )
            for res in ("5m", "1m", "10s"):
                self._conn.execute(
                    "DELETE FROM samples WHERE res = ? AND ts IN ("
                    "  SELECT ts FROM samples WHERE res = ? ORDER BY ts LIMIT 1000)",
                    (res, res),
                )
            self._conn.execute("PRAGMA incremental_vacuum")

    def _check_disk_guard(self) -> None:
        try:
            free = shutil.disk_usage(self._path.parent).free
        except OSError:
            return
        active = free < self._min_free_bytes
        if active and not self._disk_guard_active:
            logger.error(
                "metrics_store_guarda_de_disco ATIVA free_gb=%.1f min_gb=%.1f — "
                "coleta de amostras SUSPENSA (reserva intocável, ADR-0033/0045)",
                free / 1024**3,
                self._min_free_bytes / 1024**3,
            )
        elif not active and self._disk_guard_active:
            logger.info("metrics_store_guarda_de_disco liberada")
        self._disk_guard_active = active

    @property
    def disk_guard_active(self) -> bool:
        return self._disk_guard_active

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class MetricsReader:
    """Leitor read-only do ring buffer — usado pelo edge-sync-agent para
    responder aos comandos `monitoring.*`. Abre e fecha por consulta (o
    processo leitor não segura handle entre polls)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        # mode=ro: o leitor jamais escreve — nem por acidente.
        return sqlite3.connect(f"file:{self._path}?mode=ro", uri=True, timeout=5.0)

    def available(self) -> bool:
        return self._path.exists()

    def query(
        self, window: str, *, max_points: int = 360, now: int | None = None
    ) -> dict[str, Any]:
        """Janela de amostras + eventos, já afinada para `max_points`.

        `window` ∈ WINDOW_TO_RESOLUTION. Levanta ValueError para janela
        desconhecida (o chamador transforma em ack failed)."""
        if window not in WINDOW_TO_RESOLUTION:
            raise ValueError(
                f"janela inválida: {window!r} (esperado {sorted(WINDOW_TO_RESOLUTION)})"
            )
        window_s, res = WINDOW_TO_RESOLUTION[window]
        max_points = max(10, min(int(max_points), 1000))
        now = int(now if now is not None else time.time())
        since = now - window_s
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, data FROM samples WHERE res = ? AND ts >= ? ORDER BY ts",
                (res, since),
            ).fetchall()
            event_rows = conn.execute(
                "SELECT ts, kind, detail FROM events WHERE ts >= ? ORDER BY ts",
                (since,),
            ).fetchall()

        stride = max(1, -(-len(rows) // max_points))  # ceil
        samples = []
        for i, (ts, data) in enumerate(rows):
            if i % stride != 0 and i != len(rows) - 1:
                continue  # afina, mas preserva sempre a última amostra
            try:
                rec = json.loads(data)
            except json.JSONDecodeError:
                continue
            rec["ts"] = ts
            samples.append(rec)

        events = [
            {"ts": ts, "kind": kind, "detail": detail or ""}
            for ts, kind, detail in event_rows
        ]
        return {
            "resolution": res,
            "window": window,
            "samples": samples,
            "events": events,
            "thinned_stride": stride,
        }

    def latest(self) -> dict[str, Any] | None:
        """Última amostra fina — o payload do refresh live de ~10s."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ts, data FROM samples WHERE res = '10s' ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        try:
            rec = json.loads(row[1])
        except json.JSONDecodeError:
            return None
        rec["ts"] = row[0]
        return rec

    def status(self, *, now: int | None = None) -> dict[str, Any]:
        """Metadados de saúde do próprio coletor — para a página nunca mostrar
        dado velho com cara de novo."""
        now = int(now if now is not None else time.time())
        if not self.available():
            return {"alive": False, "status": "down", "last_sample_ts": None}
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT MAX(ts) FROM samples WHERE res = '10s'"
                ).fetchone()
            last_ts = row[0] if row else None
            size = self._path.stat().st_size
        except (sqlite3.Error, OSError) as exc:
            logger.warning("metrics_reader_status_falhou %s", exc)
            return {"alive": False, "status": "down", "last_sample_ts": None}
        if last_ts is None:
            return {"alive": False, "status": "down", "last_sample_ts": None, "db_size_bytes": size}
        age = now - last_ts
        status = "ok" if age <= 30 else ("stale" if age <= 300 else "down")
        return {
            "alive": age <= 300,
            "status": status,
            "last_sample_ts": last_ts,
            "last_sample_age_s": age,
            "db_size_bytes": size,
        }
