# D-025 · Log duplicado — consolidar em uma linha, sem perder campo

**Seção:** Câmeras e edge · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (achado em log) · 🔄**

Cada requisição gera duas linhas (`app.core.middleware` + `geventwebsocket.handler`), tudo em stderr.
Com 8 câmeras: ~1.440 linhas/min ≈ **2 milhões/dia**. Custa na Railway e inutiliza o log para
diagnóstico — que é onde os bugs têm sido achados.

↩ **Correção da própria decisão, no mesmo dia.** A primeira redação dizia "manter só o do middleware".
**Errado:** as duas linhas não são redundantes. O middleware tem `rid`; o gevent tem **bytes da resposta**
e **IP do cliente** — exatamente os números que sustentam a medição de egress (ADR-0059) e a investigação
de rate limit / sessão duplicada (D-24). Apagar a linha do gevent destruiria a evidência que estamos
usando para decidir arquitetura.

Decidido: **consolidar numa linha só** com `rid · método · rota · status · duração · bytes · IP`, e só
então silenciar o access log do gevent. Mais: INFO/DEBUG em **stdout**, WARNING+ em stderr — hoje o
Railway marca tudo como `[err]` e o filtro por severidade não serve para nada.

⚠️ Verificar cobertura antes de silenciar: nos 429 o middleware sai com `rid=-` e `(-0.000s)`, sinal de
que a requisição é barrada **antes** dele. Se a linha consolidada não cobrir esse caso, os 429 somem do
log — e são o que estamos investigando.
