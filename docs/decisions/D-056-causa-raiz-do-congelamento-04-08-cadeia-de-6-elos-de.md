# D-056 · Causa raiz do congelamento 04/08: cadeia de 6 elos de expiração de token, PROVADA

**Seção:** Rodada 4 — a caça ao congelamento (04/08, noite) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (verificação adversarial elo a elo) · ✅ vigente · PRs #306 #307 #308**

Log do incidente: `serve_hls: token de playback inválido` ×8 câmeras no MESMO segundo (22:46:03, repete
:04) → `GET /login` ×10. Quarta rodada no mesmo sintoma; desta vez a cadeia inteira foi confirmada por
verificação adversarial (cada elo com `file:line`, tentando REFUTAR antes de aceitar):

1. **Mint sincronizado.** A grade minta 1 token de playback por câmera no mesmo tick de render
   (`useLiveView` → POST `/stream/start`; TTL 3600 s, `playback_token.py:35`) → os 8 exp caem no mesmo
   segundo. Visto ao vivo no soak: 8 câmeras com `exp=1785887200` idêntico.
2. **Renovação frágil (playback).** `setInterval` fixo de 55 min: uma falha transitória só tentava de novo
   55 min depois (token morto aos 60); voltar de aba oculta — ou QUALQUER toggle de visibilidade da célula
   (scroll/drawer re-executa o efeito) — **reiniciava o relógio sem re-mintar**, empurrando a renovação
   para depois da expiração. É por isso que a renovação dos 55 min nunca disparou antes das 22:46.
3. **Renovação frágil (contexto).** Token de contexto assumido: TTL 30 min
   (`core/tenant_context.py:66`); a renovação era `setTimeout` único de 25 min com "falha não reagenda,
   best-effort" (`tenantContext.ts`). O `/renew` das ~21:59 caiu EXATAMENTE na janela de deploy
   21:58:49–55 ([[D-51]]/[[D-60]]) → corrente morta → contexto venceu às ~22:04 em silêncio.
4. **Silêncio estrutural.** A MonitoringPage não faz NENHUMA chamada REST periódica autenticada (vídeo via
   `serve_hls` público; resto via socket) — contexto morto só é descoberto na próxima chamada autenticada.
5. **A cascata terminal.** 22:46: tokens vencem juntos → 8× 404 → erro fatal de rede no hls.js → 8×
   `refreshLiveViewUrl` concorrentes → 8× **401** → CORRIDA no branch 401 do `api.ts`: a 1ª resposta
   restaura o backup do superadmin e navega p/ `/admin/tenants`; as 2ª..8ª acham o backup já consumido,
   caem em `removeToken()` — **apagando o token recém-restaurado** — e `href='/login'` (a última atribuição
   vence). Único `'/login'` do app é esse (`api.ts:152`): o `GET /login` ×10 do log só pode vir daí.
6. **Sinal indistinguível.** `serve_hls` devolvia 404 igual para expirado/forjado/inexistente — o player
   não tinha como tratar a expiração (rotina) diferente de câmera morta.

**Timeline fechada:** 21:34 auto-assume ([[D-48]], log `stream_info fora do tenant` na corrida de
inicialização) → ~21:59 `/renew` morto pelo deploy → 22:04 contexto expira mudo → 22:46 playback expira em
bloco → congelamento + logout. **Por que 3 soaks passaram "limpos": todos duraram menos que o TTL.**

**Hipóteses MORTAS na varredura (valem tanto quanto a viva):**
- *Segredo de assinatura rotacionado por deploy* — morta: HMAC usa `JWT_SECRET_KEY` (env estável);
  reinício NÃO invalida tokens.
- *GOP × `-c:v copy` desalinhado* — real (P2, segmentos irregulares possíveis), mas fenômeno contínuo
  por câmera: não sincroniza 8 câmeras num segundo nem desloga. Fica como melhoria (medir GOP do iNVD).
- *Buffer raso do hls.js (2 seg atrás numa playlist de 3)* — real (P2, stutter), não explica a assinatura.
- *TTL de segmento no Redis (20 s)* — dimensionado certo (P3); morta.
- *`_refresh_wanted`/chave `:active` parando câmera com espectador* — morta no caminho feliz (renova a
  cada request); fresta real: o `setex` da renovação engole falha em nível debug (P2, registrar).
- *425 manifesto-antes-do-segmento* — real e ESTRUTURAL (1–3 s por segmento novo), causa micro-engasgos
  mas não o congelamento terminal → corrigida mesmo assim ([[D-59]]).
