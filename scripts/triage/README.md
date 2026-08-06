# Triagem de frames — régua de altura-de-pessoa (Apache-2.0, LOCAL)

Instrumento para triar frames de coleta **antes de anotar**: nem anotar tudo,
nem descartar tudo. Mede a altura em pixels de cada pessoa com um detector COCO
de prateleira (**YOLOX-s, Apache-2.0 / Megvii**) e classifica cada frame pela
pessoa mais alta.

> **Isto NÃO é treino em dado de terceiro.** O detector é só uma **régua**. O
> modelo do produto continua treinado só com anotação humana dos frames da RVB.
> **ZERO ultralytics/AGPL** (ADR-0043). Roda **local ou no Orin** — frames com
> pessoas identificáveis **não saem para nuvem de terceiro**.

## As 3 faixas

| Altura da pessoa | Capacete resultante | Veredito |
|---|---|---|
| **≥ 140 px** | ~20 px | anotável |
| 80–140 px | ~12–20 px | duvidoso — Vitor decide |
| **< 80 px** | < 12 px | descartar para anotação |

(Regra: capacete ≈ 1/7 da altura da pessoa; detecção degrada muito abaixo de
~32 px de lado = limiar "small" do COCO.) Frames **sem nenhuma pessoa** são
contados à parte — possível negativo, não jogar fora.

## Rodar

```bash
# 1. baixar o modelo Apache-2.0 (uma vez)
curl -L -o yolox_s.onnx \
  https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx

# 2. deps (onnxruntime + opencv já estão em requirements/inference.txt)
pip install onnxruntime opencv-python-headless numpy

# 3. medir um diretório de frames
python scripts/triage/measure_person_heights.py \
    --model yolox_s.onnx --frames-dir <dir_dos_frames> \
    --conf 0.10 --out triagem.json --debug
```

`--conf 0.10` no lote real: separa **"pessoa pequena demais"** (entra em `<80`)
de **"sem pessoa"** (a 0.25 o distante some e seria contado errado como
negativo). Não alucina — o zoom-blur segue sem pessoa a 0.05. Ver D-65.

Saída (`triagem.json`): contagem por faixa, `no_person_frames`, stats de altura
**por câmera**, `annotatable_frames` / `doubtful_frames` (lista pronta para o
Vitor anotar) e o detalhe por frame.

## Validação (nos 3 recortes de `Documento RVB/resolucao-frames-rvb/`)

A régua bate com a triagem humana:

| recorte | humano | régua (conf 0.10) |
|---|---|---|
| `B_closeup` | anotável | pessoa **323 px = 92% da altura** → **anotável** ✔ |
| `A_substream` (pessoa ao fundo) | não anotável | **58 px (<80)** → **descartar** ✔ |
| `A_zoom_x4` ("vira mancha") | não anotável | **sem pessoa** (o zoom digital não recupera — é a malha) ✔ |

## Os 679 frames da RVB — bloqueio de acesso

⚠️ Os 679 frames **não estão em disco** — vivem no **R2**
(`training-images/{RVB}/nvr/{recorder}/*.jpg`) + **DEV Postgres** (`training_frames`,
`camera_id NULL`, `source='nvr'`). Rodar a régua no lote inteiro exige **baixar
de R2 para um diretório local** (credenciais R2/DB — ação do Vitor) e **rodar
local ou no box** (os frames não podem ir para terceiro). Só os 3 recortes de
validação estão versionados.

## Corte por câmera — limitação de dados (D-64)

O corte **por câmera** é o resultado mais valioso ("quais posições servem,
fisicamente, para EPI?"), mas **não é recuperável do banco**: os frames NVR têm
`camera_id NULL`, **não há coluna `channel`** e o filename é `uuid4`. O
`--camera-map cam.csv` (`frame_stem,camera`) permite injetar o mapeamento **se e
quando** ele existir. Ação de fundo: persistir `camera_id`/`channel` na coleta
NVR (`nvr_extraction`) — sem isso, "por câmera" só dá para **aproximar** por
resolução (615 × 704×480 substream vs ~64 de fonte maior) ou cluster de
`captured_at`.

## Limitação registrada (D-62)

🔴 Se a triagem sobrar só frames de perto, **o primeiro modelo funciona só de
perto**. Não invalida a volta 1 (ela prova que a corrente conecta), mas **não é
produto pronto** — é um modelo de curta distância. Ver `docs/REGISTRO_DE_DECISOES.md`.

## Nota de preprocessamento (D-66 / D-73)

Esta régua usa **BGR 0-255** (o que o YOLOX stock espera). O `_preprocess` de
`app/domain/detectors/onnx_yolox.py` normalizava **RGB/255** e **zerava** as
detecções do modelo COCO stock — confirmado e corrigido no caminho servido
(ver D-73 em `docs/REGISTRO_DE_DECISOES.md`: nenhum modelo do registry
dependia do RGB/255, fix direto para BGR 0-255).
