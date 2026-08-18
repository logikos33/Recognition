# D-028 · Log de acesso consolidado

**Seção:** Contrato e jurídico · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · ✅ vigente · conclui D-25**

Duas linhas por requisição (middleware + `geventwebsocket.handler`), tudo em stderr, ~2M linhas/dia com 8
câmeras. Consolidado (PR #290) em **uma linha no middleware** com os 7 campos (`rid·método·rota·status·
duração·bytes·IP`), access log do gevent silenciado (só o INFO; erros de protocolo preservados), e
severidade por stream (INFO→stdout, WARNING+→stderr). Os 429 seguem visíveis (o handler de 429 preenche
rid/tempo). Confirmado no ar: uma linha, IP real do cliente via primeiro hop do X-Forwarded-For.
