# Runbook — Lote 1 do minerador de DVR (canal 10, RVB / módulo EPI)

Passo a passo para o Vitor rodar o lote 1 de verdade. A corrente foi validada
ponta a ponta nesta sessão (ver D-112): o DVR **puxa playback real** (canal 1 e
10, ~3,4 MB por janela de 6 s). ⛔ Roda **só do Orin** (pandora), nunca da nuvem.

> **Estado corrigido (era D-107, estava errado):** os canais **NÃO** estão só no
> "canal 1". A fonte autoritativa (`resolve_channel_map`, cloud_config, ADR-0058)
> tem **28 canais mapeados**, incluindo o 10. O D-107 leu o `RECORDER_CHANNEL_MAP`
> do `.env` (stale). **Não é preciso mapear canal nenhum.**

---

## Pré-requisitos

| Item | Estado | Ação |
|---|---|---|
| Recorder configurado (host/creds/canais) | ✅ no box (`edge-sync-agent.env` + cloud_config) | nenhuma |
| Identidade do device (RS256) | ✅ | nenhuma |
| `yolox_nano.onnx` | ✅ `~/recognition/models/` | nenhuma |
| Disco (reserva 8 GB) | ✅ 56 GB livres | nenhuma |
| ffmpeg | ⚠️ em `~/.local/bin`, **fora do PATH de login** | `export PATH=$HOME/.local/bin:$PATH` (ver passo 3) |
| `replay_miner.py` + `mine_lote1.py` no box | ❌ só na PR #384 | **merge #384 → OTA** (passo 2) |
| Conta de teste + R2 (pro walkthrough, ⛔ não pro lote 1) | ❌ | provisionar depois (ver "Pendências do Vitor") |

---

## Passo 1 — mapear canais (NÃO é necessário)

Os 28 canais já estão no cloud_config. ⛔ Pular. *(Se um dia faltar um canal:
registrar a câmera-canal no DEV via `scripts/ops/import_nvr_channels_rvb.py` —
ato do Vitor, nunca do agente.)*

**Como saber que está ok:** o próprio `mine_lote1.py` recusa com mensagem clara
se o canal alvo não estiver mapeado.

## Passo 2 — mergear a #384 → OTA leva o minerador ao box

```bash
# no seu checkout de merge (gate humano):
gh pr merge 384 --merge          # ⛔ merge commit, NUNCA squash
# o OTA do edge (edge-sync-agent) puxa a nova release; confirmar:
ssh pandora@100.93.126.76 'ls ~/recognition/current/app/collector/replay_miner.py'
```

**O que esperar:** `replay_miner.py` presente em `~/recognition/current/...`.
**Como saber que deu certo:** o arquivo existe (hoje NÃO existe no box).
⚠️ `mine_lote1.py` vive em `scripts/ops/` — confirme que o OTA leva `scripts/`;
se não levar, copie o arquivo à mão pro box (é standalone).

## Passo 3 — rodar o lote 1 no pandora

```bash
ssh pandora@100.93.126.76
cd ~/recognition/current
export PATH=$HOME/.local/bin:$PATH        # 🔴 ffmpeg vive aqui — sem isso, 0 crops
set -a && . ~/.config/recognition/edge-sync-agent.env && set +a   # carrega RECORDER_*/EDGE_*
# inspeção primeiro (NÃO sobe — salva local pra você olhar a qualidade):
CONFIRM_MINE=1 LOTE1_SAVE_DIR=/tmp/lote1insp .venv/bin/python \
  ~/recognition/current/scripts/ops/mine_lote1.py
# quando a qualidade estiver ok, subir de verdade (sem LOTE1_SAVE_DIR):
CONFIRM_MINE=1 .venv/bin/python ~/recognition/current/scripts/ops/mine_lote1.py
```

**Env úteis:** `LOTE1_CHANNEL` (=10), `LOTE1_DAY_OFFSET` (=1 dia atrás — use um
**dia útil** com operação), `LOTE1_SHIFT` (=tarde), `LOTE1_BLUR_MIN` (ver aviso),
`LOTE1_SAVE_DIR` (inspeção local, não sobe).

**O que esperar:** um relatório com recortes mantidos, janelas, frames, disco,
tempo, impacto no gravador. **Sem `CONFIRM_MINE=1` ele recusa e explica.**
**Como saber que deu certo:** `janelas puxadas > 0` e tempo > 0 (o DVR respondeu).

## Passo 4 — onde olhar o resultado

- **Inspeção local:** os `.jpg` em `LOTE1_SAVE_DIR`. Olhe tamanho e nitidez.
- **Upload real:** os frames entram na fila de anotação do DEV (`source='nvr'`),
  visíveis na aba **Classificar** (PR #384) filtrando por câmera. *(Precisa da
  conta de teste + R2 — ver pendências.)*

---

## 🔴 Antes de confiar no yield — dois bloqueios reais (D-112)

O lote 1 desta sessão puxou 144 frames e manteve **1 recorte**. A causa NÃO é o
DVR (funciona), são dois defeitos de pipeline:

1. **Limiar de blur 3000 rejeita ~100% dos recortes reais** (variância medida
   ~150 — o limiar foi calibrado só em fixture sintético). Baixe com
   `LOTE1_BLUR_MIN` para experimentar, mas recalibre de verdade sobre recortes
   **humano-aprovados**, não no chute.
2. **O detector nano falso-positiva em estrutura fixa** — um poste do canal 10
   virou "pessoa" em 23/23 amostras. Baixar o blur admitiria mais poste, não
   pessoa. O fix é no detector (subir confiança / filtrar aspecto), não no blur.

⚠️ **Canal 10 (convivência) estava quase vazio** na Sex tarde — como fonte de
AUSÊNCIA rende pouco sozinho. A ausência real vem do **veredito completo por
recorte em TODO canal de produção** (aba Classificar) — mas só depois de
corrigir (1) e (2), senão o yield real é ~0.

**Ordem recomendada:** corrigir (1)+(2) → lote 1 de **turno inteiro** num canal
de produção → classificar no humano → medir a taxa de não-conformidade real →
só então decidir volume e se precisa de mais câmeras.
