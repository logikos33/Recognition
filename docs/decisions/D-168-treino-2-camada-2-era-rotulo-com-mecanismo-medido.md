# D-168 · TREINO 2 · Camada 2 — era RÓTULO, com mecanismo medido (exploratória)

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **Data:** 2026-08-18 · ⚠️ **PÓS-HOC — não pré-registrada**

A varredura de limiar foi decidida **depois** de ver o resultado. Registrada como exploratória. O que
a distingue de análise pós-hoc comum: o **mecanismo está medido de ponta a ponta**, não inferido.

**1. As caixas migraram, e dá para contar:** o `test` do export v3 tinha **106 `mascara`**; o do v6
tem **54 `mascara` + 52 `Óculos`**. **Exatamente 52.** Mesmas 179 imagens nos dois (conferido:
conjunto de nomes idêntico).

**2. A confusão aparece e some:** matriz do TREINO 1 tem `Óculos → mascara`; a do TREINO 2, não.
O TREINO 1 aprendeu *"mascara = máscara OU óculos"*.

**3. Vence em 8 de 9 limiares** (mesmo gabarito, mesmo instrumento):

| thr | T1 | T2 | Δ |
|---|---|---|---|
| 0,70 | 0,4167 | 0,6250 | **+0,21** |
| 0,60 | 0,4762 | 0,6000 | **+0,12** |
| 0,55 | 0,4815 | 0,5000 | +0,02 |
| 0,50 | 0,4545 | 0,4483 | −0,01 |
| 0,40 | 0,2903 | 0,4211 | **+0,13** |
| 0,30 | 0,1939 | 0,3800 | **+0,19** |

Em **thr 0,30 os IC quase não se tocam** (T1 [0,13–0,28] × T2 [0,26–0,52]) com **`tp` idêntico (19)**.

**4. A assimetria do gabarito foi DISSOLVIDA por medição, não declarada.** O D-163 previa que o
gabarito endurecido tornaria a comparação ambígua e mandava não concluir "era volume" se caísse.
Rodar **os dois modelos no mesmo instrumento contra o mesmo gabarito** elimina o problema em vez de
o contornar: 0,4815 × 0,5000.

> 🔴 **O efeito do rótulo limpo NÃO é acertar mais — é errar 2,5–3,1× menos.**
> thr 0,30: fp 79 → 31 com `tp` idêntico · thr 0,10: fp 445 → 142.
