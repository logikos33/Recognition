# D-083 · Teto conhecido do anotador: `<img>` + overlay de div — registrado, não resolvido

**Seção:** Rodada 10/08 — anotação destravada de ponta a ponta (D-80..D-84) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**10/08 · Claude · 📌 para a onda das 500**

A arquitetura atual (imagem em `<img>`, caixas como divs absolutos) está **certa**: mata o CORS
como bloqueio e serve bem até dezenas de caixas. O teto: com **zoom alto + muitas caixas por
frame**, overlay de div degrada (reflow por caixa, imprecisão subpixel na borda). Sinal de
troca: arrasto de caixa perceptivelmente lento com >30–50 caixas/frame ou zoom >4×. Rota quando
chegar lá: camada `<canvas>` **só para o render das caixas** (imagem continua `<img>` — o CORS
não volta). Não mudar antes do sinal.
