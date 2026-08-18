# D-063 · Câmera com obstrução física (tela metálica) — resolução NÃO conserta

**Seção:** Rodada 5 — Triagem dos 679 frames RVB (05/08 · Claude) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**05/08 · Claude**

A cena "A" (substream, pessoa ao fundo) tem uma **tela metálica entre a câmera e
a pessoa**. No zoom, o que aparece é a **malha**. **4K não resolveria** — é
**posicionamento de câmera**, não resolução. Confirmado com a régua: o detector
COCO não acha pessoa nesse frame a conf 0.25 e só acha um vulto de **58 px** a
conf 0.10 (< 80 → descartar).

**Regra de projeto de instalação:** se a área de interesse de uma câmera fica
**atrás de obstrução**, **comprar resolução não faz o modelo detectar ali**. Tem
que reposicionar. Registrar por câmera quando o inventário por posição existir
([[D-64]]).
