# D-065 · Régua validada + metodologia (a medição dos 679 aguarda credenciais)

**Seção:** Rodada 5 — Triagem dos 679 frames RVB (05/08 · Claude) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**05/08 · Claude**

`scripts/triage/measure_person_heights.py` (Apache-2.0, local): YOLOX-s COCO,
**BGR 0-255**, mede a altura em px de cada pessoa e classifica o frame pela
pessoa mais alta (≥140 anotável / 80–140 duvidoso / <80 descartar), conta frames
sem pessoa à parte.

**Validada contra a triagem humana nos 3 recortes** (`Documento RVB/
resolucao-frames-rvb/`):
- `B_closeup` (humano: anotável) → pessoa **323 px = 92% da altura** → **anotável** ✔
- `A_substream` pessoa ao fundo (humano: não anotável) → **sem pessoa** a conf
  0.25; **58 px (<80)** a conf 0.10 ✔
- `A_zoom_x4` (humano: "vira mancha") → **sem pessoa** em qualquer conf (o zoom
  digital não recupera pessoa detectável — é a malha) ✔

**Metodologia:** rodar a régua a **`--conf 0.10`** no lote real — separa "pessoa
pequena demais" (entra em <80) de "sem pessoa" (a conf 0.25 o distante some e
seria contado errado como negativo). Não alucina (o zoom-blur segue sem pessoa a
0.05).

**Bloqueio (ação do Vitor / rodar no box):** os 679 **não estão locais** — vivem
no R2 (`training-images/{RVB}/nvr/{recorder}/*.jpg`) + DEV Postgres. A medição
do lote inteiro precisa de credenciais R2/DB e roda **local ou no Orin** (frames
não saem para terceiro). Comando pronto em `scripts/triage/README.md`.
