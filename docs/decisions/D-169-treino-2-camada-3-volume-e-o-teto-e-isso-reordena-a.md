# D-169 · TREINO 2 · Camada 3 — VOLUME é o teto, e isso reordena a prioridade

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **Data:** 2026-08-18

Nas 6 classes que os dois modelos conhecem, `test` de 179 imagens, thr 0,55:

| | tp | fn | recall |
|---|---|---|---|
| TREINO 1 | 17 | 204 | **7,7%** |
| TREINO 2 | 17 | 204 | **7,7%** |

`Botas` (34 instâncias) e `Uso incorreto de mascara` (16): **zero predições dos dois modelos**.

> 🔴 **A pergunta "rótulo ou volume" tem resposta COMPOSTA, com as duas metades provadas no MESMO
> experimento: o rótulo CORROMPIA (D-168) — e o volume LIMITA (aqui).**
> **12 épocas sobre ~400 imagens não produz detector.** A paridade em 12 foi correta para o controle,
> e é exatamente por isso que o controle não pode responder "volume".

**Decisão de prioridade:** o conserto do rótulo **já está entregue** — toda anotação nova nasce
certa. **A prioridade do projeto passa a ser DADO:** mineração estratificada + anotação sobre export
limpo. Treinar de novo antes de multiplicar o volume repete o mesmo teto. Ver issue #423 e o gate
proposto em #427 (D-166).
