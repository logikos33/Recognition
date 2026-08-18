# D-082 · O percurso e2e pegou o que 276 testes verdes não pegaram: useToast instável → 429 em cascata

**Seção:** Rodada 10/08 — anotação destravada de ponta a ponta (D-80..D-84) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**10/08 · Claude · ✅ (PR #335)**

Suíte inteira verde + tsc limpo, e mesmo assim a tela caía no 2º frame do percurso real:
`useToast()` devolvia **objeto novo a cada render**; em array de dependência de
useCallback/useEffect, o fetch de classes redisparava em loop na velocidade da latência, o
bucket do flask-limiter esgotava e o **429 derrubava classes + save + load de caixas juntos**.
Fix sistêmico: `useMemo` no retorno do hook (estabiliza estúdio, galeria e página de classes de
uma vez) + estado de erro com retry no painel. **Regras que ficam:** hook utilitário devolve
identidade estável; **tela nova só entrega roteiro depois do percurso e2e andado** — é a 3ª vez
que o caminho real acha o que a suíte não achou.
