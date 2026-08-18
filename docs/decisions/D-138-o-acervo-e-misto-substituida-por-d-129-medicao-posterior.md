# D-138 · O acervo é MISTO  ↩ SUBSTITUÍDA por D-129 (medição posterior: 615 frames inteiros, não 1.254)

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Mantida por ser append-only. **O número desta entrada está errado** — ver D-129, que mediu
> 0,7% de contaminação e dano ZERO. Registrada aqui só para o erro ficar rastreável.

#### Texto original — nem "frames inteiros", nem "recortes de pessoa"

**Status:** ✅ vigente · **↩ corrige** a afirmação da rodada anterior (frames inteiros) **e** a correção do
briefing desta rodada (recortes desde sempre). **As duas estavam erradas.**

| Tipo | Frames RVB | Anotados | Dimensões |
|---|---|---|---|
| **Recorte de pessoa** (`width` < 640) | **8.413 (87%)** | 350 | 33×36 a 639×907 |
| **Frame inteiro** (`width` ≥ 640) | **1.254 (13%)** | 60 | 640×154 a 1437×934 |

Estão na **mesma tabela `public.training_frames`, sem nenhuma coluna que os distinga.**

**Causa:** o coletor do edge só recorta se o detector de pessoa estiver configurado E pronto; em 3 pontos
`_payload_para_upload` cai para o frame inteiro (`collector_loop.py:171-213`, `person_detector.py:340`).

**Consequência viva:** a aba Classificar (mergeada hoje pela #384) carrega a fila com
`GET /training/images?is_annotated=false&curation_status=active` — **sem filtro de tipo**
(`CropClassifier.tsx:243-256`). Cerca de **13% das perguntas "esta pessoa está de máscara?" são feitas
sobre uma cena inteira com várias pessoas** — pergunta que não tem resposta.

**A decisão:** marcar o tipo na ingestão (migration forward-only, coluna nova + backfill por `width`/`height`)
e filtrar a fila da aba Classificar. Sem isso, todo veredito por recorte carrega 13% de ruído estrutural.
