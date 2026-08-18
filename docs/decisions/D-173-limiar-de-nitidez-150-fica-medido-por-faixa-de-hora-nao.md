# D-173 · Limiar de nitidez 150 fica — MEDIDO por faixa de hora, não ajustado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **Data:** 2026-08-18

O limiar foi calibrado (D-anterior) sobre n=224 recortes **sem estratificar por hora**. O risco não
medido: um limiar que rejeita quase tudo à noite faz o plano noturno render zero **em silêncio**.

Medido com a **função de produção** (`replay_miner.blur_variance`, Laplaciano 3×3 em PIL puro) sobre
**834 recortes** do acervo, amostrados até 40 por hora, limiar **intocado**:

| faixa do plano | n | mediana | rejeitados @150 |
|---|---|---|---|
| 05–16 (cheia) | 480 | 683 | **3,8%** |
| 17–19 (leve) | 120 | 477 | **9,2%** |
| 20–23 (cheia) | 160 | 708 | **6,9%** |
| 00–04 (fora) | 74 | 627 | 4,1% |
| **total** | **834** | — | **5,2%** |

> ✅ **Nenhuma faixa colapsa. O medo de "à noite rejeita tudo" está DESCARTADO** — 20–23h rejeita 6,9%,
> praticamente o mesmo que o dia.

Pior hora: **17h e 21h, 15%** (6 de 40 — amostra pequena, não é sinal forte). O **crepúsculo (17–19h)
é a faixa mais difícil**: menor mediana (477) e maior rejeição — coerente com luz de transição, e
mais uma razão para ela ser "leve mas nunca zero" no plano.

**Decisão: `_DEFAULT_BLUR_VARIANCE_MIN = 150.0` fica como está.** A medição confirmou a calibração
anterior (mediana 683 aqui × 693 lá) com amostra 3,7× maior e agora estratificada.

⚠️ **Limite honesto da medida:** foi feita sobre o acervo do **coletor ao vivo**, não sobre recorte
de **replay** do DVR, que passa por substream e pode ter qualidade diferente. Re-medir na primeira
mineração real.
