# D-134 · A lista de câmeras a arquivar não bate com o banco — 2 aplicadas, 2 BLOQUEADAS

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** 🔄 em execução · **exige decisão do Vitor**

A numeração é de canal e **casa** com `public.cameras.channel` (1–29). O **estado** é que não bate:

| Canais | Descrito como | Banco diz | Ação |
|---|---|---|---|
| 13, 14, 17, 18 | fora do EPI | **já arquivadas** (`is_active=f`) | nada a fazer |
| 22, 25 | fora do EPI | ativas, 0 frames anotados | ✅ **arquivadas** |
| **3** | módulo Qualidade | 🔴 `module_code='epi'`, **1.000 frames**, 1 anotado | ⛔ **BLOQUEADA** |
| **27** | módulo Qualidade | 🔴 `module_code='epi'`, 50 frames | ⛔ **BLOQUEADA** |

**Por que 3 e 27 não foram tocadas:** as duas estão marcadas como **EPI**, não Qualidade. E o canal 3 tem
**1.000 frames** — o mesmo volume dos canais 1–8, que são os coletores de produção. Arquivar tiraria esse
material do treino (é exatamente o que D-133 passou a fazer). Um canal de produção rotulado como
"Qualidade" por engano custaria 1.000 frames.

**Também fora da lista, já arquivados:** canais 9, 15, 16.

**Pergunta para o Vitor:** os canais 3 e 27 são mesmo Qualidade? Se forem, o `module_code` no banco está
errado e o conserto é reclassificar, não arquivar.
