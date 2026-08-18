# D-124 · Lote 1 bloqueado — o que o Vitor provisiona (com escopo mínimo)

**Seção:** Rodada 16/08 (tarde) — mineração DVR Lote 1: realidade do código e bloqueios · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-113→D-124** na consolidação dos PRs #385/#386/#388 (D-113 já em uso na develop).

**16/08 · Claude · 📄 análise**

**Medido.** Para o Lote 1 rodar e cair no **DEV** (não em prod), faltam, todos ato do Vitor: **(1) token de
device DEV com escopo `frames:write`** — o upload é `POST /api/v1/edge/frames` que exige device JWT
`frames:write` (`edge/routes.py:587`), e o box está enrolado em **produção**; **(2)** confirmar presença da
cred DVR no box (só presença, ⛔ nunca o valor); **(3)** `RECORDER_CLOUD_ID` + `channel_map` DEV; **(4)** conta
de teste DEV + `E2E_ANNOT_PASSWORD`; **(5)** R2 read-only bucket DEV; **(6)** DEV DB read-only (senha vazada,
rotacionar). Detalhe/revogação por item no doc §2. **Falta no código:** o miner não tem teto TOTAL de crops —
para "~50 e para" precisa moldar o plano ou somar um `max_total_crops` (mudança P).

**Veredito: ⛔ nada criado por mim.** Especificado; aguarda provisionamento.
