# D-129 · O acervo misto era 0,7%, não 13% — e o dano era ZERO

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **↩ corrige D-121** (que dizia 8.413 recortes vs 1.254 frames inteiros)

O número anterior saiu de um limiar errado (`width >= 640`), que classificou **recorte grande**
(818×581, 1437×698 — pessoa perto da câmera) como frame inteiro.

**Discriminador correto:** frame inteiro tem a resolução do stream, então a MESMA dimensão se repete
muitas vezes; recorte tem o tamanho da caixa da pessoa, logo dimensão praticamente única.

| | Antes (errado) | Medido |
|---|---|---|
| Frames inteiros no RVB | 1.254 | **615** (todos `704x480`, a única dimensão repetida) |
| Fila da aba Classificar | ~13% contaminada | **0,7%** — 51 de 7.222 |
| **Classificações caídas em frame inteiro** | a apurar | **ZERO** |

**Conserto aplicado:** parâmetro `only_crops` em `GET /training/images`, aplicado pela aba Classificar
(`FrameRepository.list_images_filtered`). Auto-detecta resolução de câmera nova sem deploy.
**Teto conhecido:** se o coletor passar a emitir recorte de tamanho fixo, ele seria excluído por engano —
aí vira coluna `frame_kind` gravada na ingestão.

**Não houve dano a reverter.** Nada foi marcado para revisão porque não havia o que marcar.
