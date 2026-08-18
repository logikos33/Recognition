# D-058 · Expiração de token NUNCA desloga — single-flight no 401 + renovação ancorada no exp real

**Seção:** Rodada 4 — a caça ao congelamento (04/08, noite) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · PR #307**

Quatro mudanças no frontend, cada uma com teste falha-antes/passa-depois:
1. **Single-flight no branch 401** (`api.ts`): só a primeira 401 da página decide (restaurar backup OU
   deslogar); as demais lançam sem tocar em storage/location. Mata a corrida do elo 5 do [[D-56]].
2. **Contexto** (`tenantContext.ts`): agendamento pelo claim `exp` do JWT corrente; falha → retry 30 s
   enquanto o token vive; catch-up imediato ao voltar visível com renovação atrasada; desiste só após o
   exp (aí o 401 restaura o superadmin — comportamento correto).
3. **Playback** (`useLiveView.ts`): renovação por `setTimeout` ancorado no exp REAL do token (legível na
   URL, formato `<exp>.<sig>`); retry 30 s; catch-up de visibilidade; teto de TTL no delay (delay gigante
   estoura o int32 do timer e vira loop de 1 ms — achado do teste).
4. **Player** (`CameraPlayer.tsx`): reage ao 410 no PRIMEIRO evento do hls.js, re-assinando a URL sem
   esperar os 2×2 s de retry interno escalarem para fatal.
