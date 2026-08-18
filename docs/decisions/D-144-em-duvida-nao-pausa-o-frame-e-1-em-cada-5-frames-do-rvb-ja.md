# D-144 · "Em dúvida" não pausa o frame — e 1 em cada 5 frames do RVB já está excluído

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

`curation_status='duvida'` **não remove o frame do export** — só `'excluida'` remove.
`versioning_v2.py:80-83` admite em comentário: *"duvida CONTINUA entrando — ainda não há decisão humana"*.
São **36 frames** entrando no treino sem decisão, e a tela mostra só um chip, sem avisar disso.

**Segundo achado, do mesmo lugar:** o acervo se moveu **durante a auditoria**.
Início da rodada: `active 9.225 / excluida 406`. Fim: `active 7.605 / excluida 2.026` —
**~1.620 frames excluídos em 2026-08-17 22:16.**
**21% do acervo RVB está fora da curadoria** — e nada na tela mostra essa proporção.

**A decisão:** (a) tornar o texto de "em dúvida" honesto sobre o que ele faz e não faz;
(b) mostrar a proporção excluído/ativo na aba Imagens, porque 21% de descarte é um sinal
sobre a qualidade da coleta que hoje ninguém vê.
