# D-150 · Sondagem × coleta: 1.000 dos 9.667 frames do RVB são amostra rala, e nenhum foi anotado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · ⛔ nada mutado

| | Canais | Frames | Anotados | Janela de captura |
|---|---|---|---|---|
| **Coleta real** | 1–8 | **8.667** (89,7%) | 410 | 3,6 a 10,9 dias |
| **Sondagem** | 10–29 (20 canais) | **1.000** (10,3%) | **0** | 45 min a 4,8 dias |

**Não são quadros do mesmo instante** — as janelas vão de 45 min (canal 28) a 4,8 dias (canal 19).
São amostra rala no tempo, não duplicata. **Não contaminaram nenhum treino** (zero anotados).

**Canal 27 NÃO arquivado** (decisão do Vitor): 50 frames em ~7.600 é ruído, arquivar não ganha nada e
perde opção. **Canal 3 NÃO arquivado** — é Qualidade mas serve para anotar EPI, e o `module_code='epi'`
está coerente com o uso; ⛔ não "corrigir" para Qualidade.
