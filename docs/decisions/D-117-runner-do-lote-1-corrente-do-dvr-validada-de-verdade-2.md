# D-117 · Runner do lote 1 + corrente do DVR validada de verdade + 2 bloqueios de yield (corrige D-107)

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-112→D-117** na consolidação do merge #384 (D-112 já em uso na develop).

**Entregue.** `scripts/ops/mine_lote1.py` (runner pronto pro Vitor): lê `RECORDER_*`/`EDGE_*` do env (nunca
argv), valida ANTES de puxar (`CONFIRM_MINE=1`? ffmpeg no PATH? canal mapeado? disco? identidade? DVR
responde?) com mensagem legível do que falta, monta plano mínimo (1 canal, 1 dia, 1 turno ≈ 50 recortes),
anti-lockout herdado do `mine()` (401/403 encerra o run, sem retry), modo inspeção (`LOTE1_SAVE_DIR`, salva
local sem subir). `ruff` limpo. Validado no box (recusa sem `CONFIRM_MINE`; roda com). Runbook em
`docs/runbooks/RUNBOOK_LOTE1_DVR.md`.

🔴 **Correções ao D-107 (estado antigo estava errado — C-04):**
- **Canal 10 (e 28 canais) JÁ estão mapeados** via `resolve_channel_map`/cloud_config (ADR-0058). O D-107
  leu o `RECORDER_CHANNEL_MAP` do `.env` (stale, só canal 1) em vez da fonte autoritativa. **"Bloqueio nº1"
  era falso.**
- **A corrente do DVR FUNCIONA de ponta a ponta:** `RtspTimestampRecorderClient` puxou playback real do
  iNVD 3032 (canal 1 e 10, ~3,4 MB por janela de 6 s). ADR-0034 era "mock-only"; agora é validado em
  hardware real.
- O único motivo de "0 crops" no 1º teste foi **ffmpeg fora do PATH** (vive em `~/.local/bin`, que os
  serviços systemd põem no PATH mas o shell de login não). O runner agora valida ffmpeg antes de puxar.

🔴 **Dois bloqueios reais de yield (o valor de "começar pequeno"):**
1. **Limiar de blur 3000 rejeita ~100% dos recortes reais.** Medido em campo: variância dos recortes reais
   = **141–259 (p50 155)**, contra o limiar 3000 → **0/23 passam**. O limiar foi calibrado só em fixture
   sintético (o próprio código avisa). Exposto via `LOTE1_BLUR_MIN`; recalibrar sobre recortes
   humano-aprovados, não no chute.
2. **O detector YOLOX-nano falso-positiva em estrutura fixa** — um poste do canal 10 virou "pessoa" em
   **23/23** amostras (recortes de ~128×168 de um poste preto no concreto). Baixar o blur admitiria mais
   poste, não pessoa. O fix é no detector (subir confiança / filtrar aspecto), não no blur.

**Recount da ausência (bloco 4 — a conta antiga só via o canal 10).** A pergunta certa é a **taxa de
não-conformidade por tipo de EPI, por canal aprovado** — e para isso **não há dado**: exige veredito humano
por recorte (aba Classificar), que ainda não rodou. **Resposta honesta: "não sei" — o lote 1 humano-
classificado é quem responde.** Direção qualitativa: com o veredito completo por recorte, AUSÊNCIA vem de
TODO canal, e produção (~6000 recortes) domina o canal 10 (~209) — **mas só depois de corrigir (1) e (2)**,
senão o yield real é ~0. Amostra desta sessão: canal 10 (convivência) na Sex tarde estava quase vazio
(poste + cena vazia); canal 8 (produção) deu 0 pessoas em 36 frames (amostra de 6 s é ruidosa demais para
medir yield).

**Precisa mapear mais áreas de convivência, ou a produção resolve?** **Nem uma coisa nem outra ainda** —
primeiro corrigir os 2 bloqueios mecânicos. Direção: **produção resolve, NÃO mapear mais convivência** (o
canal 10 mostrou-se vazio), mas confirmar com um lote 1 de **turno inteiro** num canal de produção, humano-
classificado, depois dos fixes.

**Segurança.** Nada foi subido à nuvem (modo inspeção); recortes reais de trabalhadores apagados do box e
local ao fim; nenhuma credencial/host/URL/connection-string impressa (o `stderr` do ffmpeg é redigido e o
runner só imprime categoria de erro, nunca a mensagem crua).

<!-- Consolidação dos PRs #385/#386/#388 (D-107..115,119 renumerados uma vez -> D-118..127; D-116/117/118 do #386 omitidas por obsolescência) + entrada da rodada. -->
