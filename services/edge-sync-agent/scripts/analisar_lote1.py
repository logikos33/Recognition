#!/usr/bin/env python3
"""Analisa o lote 1 e responde as 4 perguntas do critério de aceite.

Cruza os frames coletados com as janelas de horário das rodadas A/B/C
(anotadas na hora pelo operador) e produz, POR CLASSE:
    1. a partir de quantos px de cabeça os óculos ficam anotáveis
    2. idem para concha/abafador
    3. o cordão do plug aparece em alguma distância?
    4. % de frames úteis por classe (não global)

Uso:
    railway run --service Postgres -- python analisar_lote1.py \
        A=18:40-18:47  B=18:48-18:55  C=18:56-19:02

Sem as janelas ele ainda roda, mas não separa por rodada — e aí o lote vira
"50 fotos de gente", como o protocolo avisa.
"""
import os
import subprocess
import sys
from datetime import datetime

import boto3

OUT = "/tmp/lote1"
os.makedirs(OUT, exist_ok=True)
# Alvo por classe: hipóteses a confirmar. A "cabeça" é estimada como 1/7 da
# altura da pessoa — convenção antropométrica para corpo em pé; para agachado
# ela subestima, e isso é anotado no relatório em vez de corrigido às cegas.
HIPOTESES = {"oculos": 45, "concha": 45, "cordao": None}


def janelas_do_argv():
    js = {}
    for a in sys.argv[1:]:
        if "=" not in a:
            continue
        rodada, faixa = a.split("=", 1)
        ini, fim = faixa.split("-", 1)
        js[rodada.upper()] = (ini.strip(), fim.strip())
    return js


def rodada_de(hora_str, janelas):
    t = datetime.strptime(hora_str, "%H:%M:%S").time()
    for r, (i, f) in janelas.items():
        if (datetime.strptime(i, "%H:%M").time() <= t
                <= datetime.strptime(f, "%H:%M").time()):
            return r
    return "?"


SQL = """SELECT r2_key, width, height,
       to_char(captured_at AT TIME ZONE 'America/Sao_Paulo','HH24:MI:SS')
FROM public.training_frames
WHERE source='nvr' AND captured_at > now() - interval '6 hours'
ORDER BY captured_at;"""

linhas = subprocess.run(
    ["psql", os.environ["DATABASE_PUBLIC_URL"], "-At", "-F|", "-c", SQL],
    capture_output=True, text=True, check=True,
).stdout.strip().splitlines()

janelas = janelas_do_argv()
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                  aws_access_key_id=os.environ["R2_KEY"],
                  aws_secret_access_key=os.environ["R2_SECRET"],
                  region_name="auto")
bucket = os.environ.get("R2_BUCKET", "epi-monitor-dev")

por_rodada: dict[str, list] = {}
for i, ln in enumerate(linhas):
    key, w, h, hora = ln.split("|")
    r = rodada_de(hora, janelas) if janelas else "?"
    # a altura do RECORTE é ~1.16x a da pessoa (margem de 8% em cima e embaixo)
    pessoa_h = int(int(h) / 1.16)
    cabeca = pessoa_h // 7
    dest = f"{OUT}/{r}_{cabeca:03d}px_{i:03d}.jpg"
    try:
        s3.download_file(bucket, key, dest)
    except Exception as exc:
        print(f"  falhou {key[-12:]}: {str(exc)[:50]}")
        continue
    por_rodada.setdefault(r, []).append(
        {"arq": dest, "w": int(w), "h": int(h), "cabeca": cabeca, "hora": hora})

print(f"\n{sum(len(v) for v in por_rodada.values())} frames baixados em {OUT}\n")
print(f"{'rodada':>8} {'n':>4} {'cabeca min':>11} {'mediana':>8} {'max':>5} "
      f"{'>=35px':>7} {'>=45px':>7}")
for r in sorted(por_rodada):
    v = sorted(x["cabeca"] for x in por_rodada[r])
    u35 = sum(1 for c in v if c >= 35) * 100 // len(v)
    u45 = sum(1 for c in v if c >= 45) * 100 // len(v)
    print(f"{r:>8} {len(v):>4} {v[0]:>11} {v[len(v)//2]:>8} {v[-1]:>5} "
          f"{u35:>6}% {u45:>6}%")

print("\nOs arquivos estão nomeados <rodada>_<px_cabeca>_<n>.jpg — abra em ordem")
print("de px e marque onde CADA item deixa de ser legível. É esse o número que")
print("o lote 1 precisa produzir; o script mede o pixel, quem julga é humano.")
if not janelas:
    print("\n⚠️  Sem janelas A=/B=/C= no argv: não dá pra separar por condição")
    print("    de EPI. Passe os horários anotados durante a encenação.")
