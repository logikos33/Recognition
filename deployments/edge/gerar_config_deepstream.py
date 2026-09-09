#!/usr/bin/env python3
"""Gera o config do DeepStream apontando para as câmeras REAIS da RVB.

⛔ RODA NO BOX, à mão, com o runbook `destravar_edge_rvb.md` ao lado. Não
   habilita serviço, não reinicia nada, não fala com o banco.

POR QUE ESTE SCRIPT EXISTE
--------------------------
Os configs que estão no box (`~/jetson-experiments/mm/app_mm_*.txt`) apontam
para `rtsp://127.0.0.1:8554/camN` — o gerador sintético do teste de carga. O
box pode rodar o melhor modelo do mundo sobre vídeo de mentira e ninguém
percebe: o teste de carga foi feito para medir GPU, não para ver a fábrica.

AS DUAS FONTES DA VERDADE JÁ ESTÃO NO BOX — este script só as junta
---------------------------------------------------------------------
  · `config_cache.json` (ADR-0058): camera_id (UUID) -> canal do gravador.
    Escrito pelo ConfigPoller a cada poll bem-sucedido de
    GET /api/v1/edge/config/poll. É a lista de câmeras da NUVEM, não um
    palpite local. NUNCA carrega segredo (por desenho da ADR).
  · `edge-sync-agent.env`: RECORDER_HOST/PORT/USERNAME/PASSWORD — a mesma
    credencial que o `edge-live-view` já usa com sucesso hoje.

⚠️ SENHA — as três regras
--------------------------
1. A senha NUNCA entra por argumento de linha de comando (apareceria em `ps`
   e no histórico do shell). Só é lida do arquivo .env, que já é 600.
2. A senha NUNCA é impressa: o resumo na tela mostra a URL redigida.
3. O config gerado CONTÉM a senha (o nvurisrcbin do DeepStream só aceita a
   URI pronta, não há substituição por env). Por isso o arquivo nasce 0600,
   fora do repo, em ~/.config/recognition/deepstream/. NÃO COMMITAR.

⚠️ LOCKOUT — leia antes de rodar
---------------------------------
As Intelbras da RVB TRAVAM por proteção anti-brute-force se apanharem
credencial errada em sequência (CLAUDE.md §Cloud→Edge). Por isso este script:
  · não aceita credencial nova — só reusa a que já está no .env e já
    funciona no live view;
  · aborta se RECORDER_PASSWORD estiver vazia (melhor não gerar nada do que
    gerar 29 fontes que vão bater com senha em branco);
  · tem `--cameras` para começar com UMA câmera, como manda o runbook.

⚠️ CADÊNCIA POR CÂMERA — por que NÃO é o `interval` do GIE
-----------------------------------------------------------
O front tem `fps_target` POR CÂMERA (ADR-0026) e ele já viaja no
`GET /api/v1/edge/config/poll`. Mas `[primary-gie] interval=N` é do GIE,
não da fonte: um único número não honra 18 alvos diferentes. Hoje todas as
18 da RVB estão em 5, então um interval global "daria certo" — e passaria a
mentir no dia em que uma câmera pedir 3 e outra 10.

O knob que existe POR FONTE é `drop-frame-interval` do `nvurisrcbin`
(`gst-inspect-1.0 nvurisrcbin`: "value of 5 means every 5th frame will be
given by decoder, rest all dropped"). Então:

    drop-frame-interval = round(fps_da_fonte / fps_target)   # por [sourceN]
    [primary-gie] interval = 0                               # infere o que chegar

Cada câmera entrega o SEU alvo e o GIE infere tudo que lhe entregam. Sai
exato por câmera, com um GIE só. Limites honestos:
  · a propriedade é inteira e vai só até 30 → o alvo real é
    fps_fonte/round(...), não o alvo pedido (5 de 30 = exato; 7 de 30 → 4,3);
  · dropar é PÓS-DECODE: economiza inferência e todo o resto do pipeline,
    NÃO economiza decode. Por isso o degrau de 18 câmeras se mede, não se
    extrapola — ver a tabela do runbook.

`--intervalo` continua existindo como escape hatch: se você passar, ele vai
pro GIE e o `drop-frame-interval` NÃO é emitido (comportamento antigo,
global). Sem ele, a cadência vem do banco, por câmera.

O MODELO É PARÂMETRO
--------------------
`--infer-config` aponta para o config do nvinfer (engine + labelfile +
parser). Quem vencer o duelo entra por aqui, sem tocar neste script.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CACHE_PADRAO = "~/.local/share/recognition/edge-sync/config_cache.json"
ENV_PADRAO = "~/.config/recognition/edge-sync-agent.env"
SAIDA_PADRAO = "~/.config/recognition/deepstream"

_LINHA_ENV = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")


def ler_env(caminho: Path) -> dict[str, str]:
    """KEY=VALUE do EnvironmentFile do systemd. Comentário e linha solta ignorados.

    Não usa `dotenv`: o formato do systemd é este subconjunto e o box não tem
    a lib. Aspas externas são removidas porque o systemd também as remove.
    """
    valores: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        m = _LINHA_ENV.match(linha.strip())
        if not m:
            continue
        valor = m.group(2).strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        valores[m.group(1)] = valor
    return valores


def url_rtsp(host: str, porta: str, usuario: str, senha: str, canal: int, subtype: int) -> str:
    """Dialeto Dahua/Intelbras — o MESMO de rtsp_timestamp_recorder_client.

    `quote(safe="")` porque senha de gravador costuma ter `@`/`/`, que sem
    escapar quebram o parsing da URI e o DeepStream tenta conectar num host
    inventado (e isso conta como tentativa falha no contador de lockout).
    """
    cred = f"{quote(usuario, safe='')}:{quote(senha, safe='')}@" if usuario else ""
    return (
        f"rtsp://{cred}{host}:{porta}/cam/realmonitor"
        f"?channel={canal}&subtype={subtype}"
    )


def redigir(url: str) -> str:
    """URL sem a senha, para log/tela. Espelha app/redact.py do agente."""
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url)


DROP_MAX = 30  # teto da propriedade drop-frame-interval do nvurisrcbin


def drop_por_fps(fps_fonte: float, fps_alvo: float) -> tuple[int, float]:
    """`drop-frame-interval` para atingir *fps_alvo* dada uma fonte de *fps_fonte*.

    Devolve (drop, fps_efetivo). `drop=1` = entrega tudo (nenhum frame
    descartado). O fps_efetivo é o que a câmera VAI entregar de verdade —
    devolvido junto porque a propriedade é inteira e quase nunca bate o alvo
    na mosca; quem chama loga o real, não o pedido.
    """
    if fps_alvo <= 0 or fps_alvo >= fps_fonte:
        return 1, fps_fonte
    drop = min(DROP_MAX, max(1, round(fps_fonte / fps_alvo)))
    return drop, fps_fonte / drop


def _autoteste() -> None:
    """Check mínimo da derivação — `python3 gerar_config_deepstream.py --autoteste`."""
    assert drop_por_fps(30, 5) == (6, 5.0)          # o caso da RVB: exato
    assert drop_por_fps(30, 3) == (10, 3.0)
    assert drop_por_fps(30, 30) == (1, 30.0)        # alvo == fonte -> não dropa
    assert drop_por_fps(30, 60) == (1, 30.0)        # alvo acima da fonte -> idem
    assert drop_por_fps(30, 0) == (1, 30.0)         # alvo ausente/zero -> idem
    d, ef = drop_por_fps(30, 7)                     # inteiro não bate o alvo
    assert (d, round(ef, 2)) == (4, 7.5), (d, ef)
    assert drop_por_fps(30, 0.1)[0] == DROP_MAX     # teto da propriedade
    print("autoteste OK")


def montar_config(
    fontes: list[tuple[int, str, str, int]],
    infer_config: str,
    kitti_dir: str,
    intervalo: int,
    mux_wh: tuple[int, int],
) -> str:
    """Config do `deepstream-app`. `fontes` = [(indice, camera_id, uri, drop)].

    Decisões, e por quê:
      · sink type=1 (fakesink): a saída ÚTIL é o dump KITTI, não vídeo. Um
        sink de tela exigiria DISPLAY e desperdiçaria GPU.
      · gie-kitti-output-dir: é o único jeito de tirar metadado do
        `deepstream-app` sem pyds (não instalado no box) e sem msgbroker (o
        adaptador Redis fala Streams/XADD, o relay do agente fala pub/sub).
      · tracker desligado: o dump do GIE não carrega track_id, então o
        tracker custaria GPU sem mudar nada na saída. Ligar só quando algo
        consumir track (ex.: contagem).
      · select-rtp-protocol=4 (TCP): a LAN do gravador perde UDP e o
        DeepStream não reconecta bem de stream truncado.
      · drop-frame-interval por fonte: é o único lugar do pipeline onde a
        cadência é POR CÂMERA. Só é emitido quando > 1 (drop=1 é o default
        do elemento e escrever isso só polui o config).
    """
    blocos = [
        "[application]",
        "enable-perf-measurement=1",
        "perf-measurement-interval-sec=5",
        f"gie-kitti-output-dir={kitti_dir}",
        "",
        "[tiled-display]",
        "enable=0",
        "",
    ]
    for indice, camera_id, uri, drop in fontes:
        blocos += [
            f"# {camera_id}",
            f"[source{indice}]",
            "enable=1",
            "type=4",
            f"uri={uri}",
            "gpu-id=0",
            "select-rtp-protocol=4",
            "latency=100",
            "rtsp-reconnect-interval-sec=10",
        ]
        if drop > 1:
            blocos.append(f"drop-frame-interval={drop}")
        blocos.append("")
    blocos += [
        "[sink0]",
        "enable=1",
        "type=1",
        "sync=0",
        "qos=0",
        "",
        "[osd]",
        "enable=0",
        "",
        "[streammux]",
        "gpu-id=0",
        f"batch-size={len(fontes)}",
        "batched-push-timeout=33000",
        f"width={mux_wh[0]}",
        f"height={mux_wh[1]}",
        "live-source=1",
        "",
        "[tracker]",
        "enable=0",
        "",
        "[primary-gie]",
        "enable=1",
        "gpu-id=0",
        f"interval={intervalo}",
        f"config-file={infer_config}",
        "",
    ]
    return "\n".join(blocos)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nome", default="epi", help="sufixo dos arquivos gerados (default: epi)")
    p.add_argument("--cache", default=CACHE_PADRAO, help="config_cache.json (camera->canal)")
    p.add_argument("--env", default=ENV_PADRAO, help=".env do edge-sync-agent (credencial do gravador)")
    p.add_argument("--saida", default=SAIDA_PADRAO, help="diretório de saída (nasce 0700)")
    p.add_argument("--infer-config", help="config do nvinfer (engine+labelfile+parser) — obrigatório fora do --autoteste")
    p.add_argument("--kitti-dir", default="/dev/shm/recognition-kitti",
                   help="dump do GIE. /dev/shm = RAM: disco cheio é intertravamento do device")
    p.add_argument("--cameras", default="",
                   help="csv de camera_id para incluir (vazio = todas do cache). COMECE COM UMA.")
    p.add_argument("--subtype", type=int, default=None,
                   help="0=principal 1=substream (default: RECORDER_STREAM_SUBTYPE do .env, ou 0)")
    p.add_argument("--intervalo", type=int, default=None,
                   help="ESCAPE HATCH: força interval do primary-gie (global, 1 a cada N+1 "
                        "frames) e NÃO emite drop-frame-interval. Sem isto, a cadência vem "
                        "do fps_target de cada câmera (default).")
    p.add_argument("--fps-fonte", type=float, default=30.0,
                   help="FPS real que o gravador entrega por stream (default 30). É o "
                        "denominador da conta do drop-frame-interval — se a fonte não for "
                        "30, o alvo sai errado.")
    p.add_argument("--fps-alvo", type=float, default=None,
                   help="força o MESMO fps_target para todas as câmeras, ignorando o banco. "
                        "Só para medição/degrau; em operação o valor vem do front.")
    p.add_argument("--autoteste", action="store_true", help="roda o check da derivação e sai")
    p.add_argument("--mux", default="1280x720", help="resolução do streammux (default 1280x720)")
    args = p.parse_args()

    if args.autoteste:
        _autoteste()
        return 0
    if not args.infer_config:
        logger.error("--infer-config é obrigatório")
        return 2

    cache_path = Path(os.path.expanduser(args.cache))
    env_path = Path(os.path.expanduser(args.env))
    for caminho in (cache_path, env_path):
        if not caminho.is_file():
            logger.error("arquivo obrigatório ausente: %s", caminho)
            return 2

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    channel_map: dict[str, int] = {str(k): int(v) for k, v in (cache.get("channel_map") or {}).items()}
    # fps_target_map: escrito pelo ConfigPoller no MESMO poll do channel_map.
    # Ausente = cache gravado por um agente anterior a esta mudança — não é
    # erro, cai no --fps-alvo/--intervalo. Tolerante como o collection_subtype_map.
    fps_map: dict[str, float] = {}
    for k, v in (cache.get("fps_target_map") or {}).items():
        try:
            fps_map[str(k)] = float(v)
        except (TypeError, ValueError):
            logger.warning("fps_target inválido no cache para %s: %r (ignorado)", k, v)
    if not channel_map:
        logger.error(
            "%s tem channel_map vazio — o ConfigPoller ainda não trouxe câmera "
            "nenhuma da nuvem. Sem isso não há como saber que canal é que câmera.",
            cache_path,
        )
        return 2

    env = ler_env(env_path)
    host = env.get("RECORDER_HOST", "")
    porta = env.get("RECORDER_PORT", "554")
    usuario = env.get("RECORDER_USERNAME", "")
    senha = env.get("RECORDER_PASSWORD", "")
    if not host or not senha:
        # Gerar com senha vazia produziria N tentativas falhas seguidas contra
        # o gravador — exatamente o gatilho do lockout anti-brute-force.
        logger.error(
            "RECORDER_HOST/RECORDER_PASSWORD ausentes em %s — abortando ANTES de "
            "gerar config que bateria no gravador com credencial vazia (lockout).",
            env_path,
        )
        return 2

    subtype = args.subtype if args.subtype is not None else int(env.get("RECORDER_STREAM_SUBTYPE", "0") or 0)
    escolhidas = [c.strip() for c in args.cameras.split(",") if c.strip()]
    if escolhidas:
        desconhecidas = [c for c in escolhidas if c not in channel_map]
        if desconhecidas:
            logger.error("camera_id fora do config_cache: %s", ", ".join(desconhecidas))
            return 2
        itens = [(c, channel_map[c]) for c in escolhidas]
    else:
        # Ordem por canal: torna o índice da fonte estável entre gerações, o
        # que importa porque é ele que o publicador usa para achar a câmera.
        itens = sorted(channel_map.items(), key=lambda kv: kv[1])

    # Cadência: --intervalo desliga a derivação (vai global no GIE, jeito antigo);
    # sem ele, cada fonte ganha o SEU drop-frame-interval e o GIE fica em 0.
    modo_global = args.intervalo is not None
    intervalo_gie = args.intervalo if modo_global else 0

    fontes: list[tuple[int, str, str, int]] = []
    cadencia: list[tuple[int, str, float | None, int, float]] = []
    for i, (camera_id, canal) in enumerate(itens):
        alvo = args.fps_alvo if args.fps_alvo is not None else fps_map.get(camera_id)
        if modo_global or alvo is None:
            drop, efetivo = 1, args.fps_fonte / (intervalo_gie + 1)
        else:
            drop, efetivo = drop_por_fps(args.fps_fonte, alvo)
        fontes.append((i, camera_id, url_rtsp(host, porta, usuario, senha, canal, subtype), drop))
        cadencia.append((i, camera_id, alvo, drop, efetivo))

    sem_alvo = [c for _, c, alvo, _, _ in cadencia if alvo is None]
    if sem_alvo and not modo_global:
        logger.warning(
            "%d câmera(s) sem fps_target no cache — vão inferir em TODOS os frames "
            "(%.1f FPS). Use --fps-alvo, ou atualize o edge-sync-agent para gravar "
            "fps_target_map no config_cache.json.",
            len(sem_alvo), args.fps_fonte,
        )

    saida = Path(os.path.expanduser(args.saida))
    saida.mkdir(parents=True, exist_ok=True)
    os.chmod(saida, 0o700)

    largura, altura = (int(x) for x in args.mux.lower().split("x"))
    conf_path = saida / f"app_{args.nome}.txt"
    conf_path.write_text(
        montar_config(fontes, args.infer_config, args.kitti_dir, intervalo_gie, (largura, altura)),
        encoding="utf-8",
    )
    os.chmod(conf_path, 0o600)  # contém a senha do gravador na URI

    # Mapa índice-da-fonte -> camera_id. Sem segredo: é o que o publicador lê
    # para saber em qual `det:{camera_id}` publicar o que o KITTI diz da
    # fonte N. Separado do config de propósito — este pode ser lido por
    # qualquer um, o outro não.
    fontes_path = saida / f"fontes_{args.nome}.json"
    fontes_path.write_text(
        json.dumps({str(i): camera_id for i, camera_id, _, _ in fontes}, indent=2),
        encoding="utf-8",
    )
    os.chmod(fontes_path, 0o644)

    logger.info("gerado %s (0600, %d fontes)", conf_path, len(fontes))
    logger.info("gerado %s", fontes_path)
    logger.info(
        "cadência: %s (fonte %.1f FPS, primary-gie interval=%d)",
        "--intervalo global (derivação DESLIGADA)" if modo_global else "por câmera, do fps_target",
        args.fps_fonte, intervalo_gie,
    )
    for (i, camera_id, uri, _), (_, _, alvo, drop, efetivo) in zip(fontes, cadencia):
        logger.info(
            "  source%-2d %s  alvo=%s drop=%d -> %.1f FPS  %s",
            i, camera_id, "-" if alvo is None else f"{alvo:g}", drop, efetivo, redigir(uri),
        )
    logger.info("carga de inferência total: %.1f FPS", sum(c[4] for c in cadencia))
    logger.warning(
        "NÃO COMMITAR %s (contém a senha do gravador). Confira o canal de UMA "
        "câmera antes de subir as %d — credencial errada em sequência trava a "
        "Intelbras por anti-brute-force.",
        conf_path, len(fontes),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
