"""Colheita PONTUAL de FRAME CHEIO do gravador — driver do ReplayMiner novo.

Roda de uma cópia isolada do código (~/colheita-full-0902), com estado
isolado via XDG_STATE_HOME: NÃO toca a marca-d'água nem os contadores de
campanha da produção. Os serviços do box seguem intocados.

Só orquestra: quem decide gate de pessoa, blur, dedup, reserva de disco e
anti-lockout é o próprio ReplayMiner (full_frame=True).

PRIORIDADE=<canais> promove canais a FULL só DENTRO deste processo. Existe
porque a tabela de política (decisão Vitor 15/08) deixa canal não listado em
REDUCED, com teto de 1 frame por janela — e foi isso que rendeu 17 (ch7 Entrada
Preparação) e 8 (ch21 Entrada Expedição 02) na colheita de 02/09, justamente as
entradas que o dono pediu. A alternativa seria 4x mais janelas contra o gravador
para o mesmo número de frames, e mais requisição no DVR é o que NÃO se quer
(D-160/anti-lockout). A tabela compartilhada segue byte a byte como está; quem
sobe é este driver pontual.

Uso:
    CANAIS=1,4 DIAS=2026-09-01 python colheita_full.py
    CANAIS=1,4,7,8,11,21 DIAS=2026-09-01,2026-09-02 DEDUP=2 python colheita_full.py
    CANAIS=2,7,21 PRIORIDADE=2,7,21 PULL_MIN=10 DIAS=2026-09-02 python colheita_full.py
"""
import json
import os
import sys
from datetime import date
from datetime import time as dtime

BASE = os.path.expanduser("~/colheita-full-0902")
os.chdir(BASE)
sys.path.insert(0, BASE)

# Estado ISOLADO: state_path_for() lê XDG_STATE_HOME. Sem isto o piloto
# avançaria a marca-d'água da produção e abriria buraco permanente no
# dataset dela (o FIFO do DVR come o que ficou para trás).
os.environ["XDG_STATE_HOME"] = os.path.join(BASE, "state")

# .env do systemd (KEY=valor cru, não é shell: valores têm espaço e parêntese).
for linha in open(os.path.expanduser("~/.config/recognition/edge-sync-agent.env")):
    linha = linha.strip()
    if linha and not linha.startswith("#") and "=" in linha:
        k, _, v = linha.partition("=")
        os.environ.setdefault(k, v)

from app.logging_setup import install_redacted_logging  # noqa: E402

install_redacted_logging()
import logging  # noqa: E402

logging.getLogger("httpx").setLevel(logging.WARNING)

from app.auth.token_manager import build_token_manager_from_env  # noqa: E402
from app.collector import replay_miner as rm  # noqa: E402
from app.collector.person_detector import build_person_detector_from_env  # noqa: E402
from app.collector.replay_miner import (  # noqa: E402
    ReplayMiner,
    ShiftWindow,
    _resumo_do_ciclo,
    run_mining,
)
from app.recorder_factory import build_recorder_client_from_env  # noqa: E402


def promove_prioritarios(canais):
    """Canal prioritário vira FULL neste processo. build_sampling_plan resolve
    policy_for_channel pelo módulo a cada task, então trocar o atributo basta —
    e some quando o processo morre."""
    original = rm.policy_for_channel

    def _com_prioridade(channel):
        if channel in canais:
            return rm.ChannelRule(
                rm.ChannelPolicy.FULL,
                "prioridade do dono 02/09 (colheita pontual) — sobrepõe REDUCED",
                priority=100,
            )
        return original(channel)

    rm.policy_for_channel = _com_prioridade


def canais_do_config():
    """channel -> camera_id, da MESMA fonte que a produção usa (config da nuvem)."""
    caminho = os.environ.get(
        "EDGE_CONFIG_CACHE_PATH",
        os.path.expanduser("~/.local/share/recognition/edge-sync/config_cache.json"),
    )
    with open(caminho) as f:
        cfg = json.load(f)

    def acha(o):
        if isinstance(o, dict):
            if "channel_map" in o:
                return o["channel_map"]
            for v in o.values():
                r = acha(v)
                if r:
                    return r
        return None

    mapa = acha(cfg) or json.loads(os.environ.get("RECORDER_CHANNEL_MAP", "{}"))
    return {int(ch): cid for cid, ch in mapa.items()}


def main():
    todos = canais_do_config()
    pedidos = [int(c) for c in os.environ["CANAIS"].split(",")]
    faltando = [c for c in pedidos if c not in todos]
    if faltando:
        raise SystemExit(f"canais fora do mapa do gravador: {faltando}")
    camera_by_channel = {c: todos[c] for c in pedidos}

    prio = {int(c) for c in os.environ.get("PRIORIDADE", "").split(",") if c.strip()}
    if prio:
        promove_prioritarios(prio)

    dias = [date.fromisoformat(d) for d in os.environ["DIAS"].split(",")]
    dedup = os.environ.get("DEDUP")
    # Turno estreito por padrão: piloto tem de ser pequeno e medido antes de
    # escalar. SHIFTS_RVB inteiro é a campanha, não o piloto.
    turno = ShiftWindow(
        os.environ.get("TURNO_NOME", "piloto"),
        dtime.fromisoformat(os.environ.get("TURNO_INI", "07:00")),
        dtime.fromisoformat(os.environ.get("TURNO_FIM", "17:00")),
    )

    miner = ReplayMiner(
        recorder=build_recorder_client_from_env(),
        api_base_url=os.environ["EDGE_API_URL"],
        recorder_id=os.environ["RECORDER_CLOUD_ID"],
        token_source=build_token_manager_from_env(),
        person_detector=build_person_detector_from_env(os.environ),
        module_code=os.environ.get("COLLECTOR_MODULE_CODE", "epi"),
        full_frame=True,
        dedup_hamming=int(dedup) if dedup else None,
        pull_interval_min=float(os.environ.get("PULL_MIN", "20")),
    )
    print(
        f"COLHEITA FRAME CHEIO canais={pedidos} dias={[d.isoformat() for d in dias]} "
        f"turno={turno.label} {turno.start}..{turno.end} "
        f"pull_min={os.environ.get('PULL_MIN', '20')} "
        f"dedup_hamming={dedup or '0 (default do modo)'} "
        f"prioridade={sorted(prio) or 'nenhuma (tabela intacta)'}",
        flush=True,
    )
    for c in pedidos:
        r = rm.policy_for_channel(c)
        print(f"  canal {c}: {r.policy.value} teto_campanha={r.campaign_max_crops} "
              f"teto_janela={r.per_window_cap}", flush=True)
    stats = run_mining(miner, camera_by_channel, days=dias, shifts=(turno,))
    print(_resumo_do_ciclo(stats))
    print(f"BYTES_SUBIDOS={stats.bytes_uploaded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
