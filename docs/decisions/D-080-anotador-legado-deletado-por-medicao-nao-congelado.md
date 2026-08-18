# D-080 · Anotador legado DELETADO por medição (não congelado)

**Seção:** Rodada 10/08 — anotação destravada de ponta a ponta (D-80..D-84) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**10/08 · Vitor (critério) + Claude (medição) · ✅**

Critério do Vitor: zero anotações de vídeo → deletar; uso real → congelar com prazo. A medição
no DEV fechou a questão: **0 frames com `video_id`, 0 anotações de vídeo, tabela `videos`
inexistente em `public`** — o modo vídeo nunca teve um dado. `AnnotationInterface.jsx`
(1.163 linhas, "congelado" desde D-71), o wrapper morto e o branch `video_id` da galeria saíram
no PR #334. Todo clique abre o **AnnotationStudio** novo (TSX, teclado-primeiro). Fim do risco
de dois anotadores para sempre.
