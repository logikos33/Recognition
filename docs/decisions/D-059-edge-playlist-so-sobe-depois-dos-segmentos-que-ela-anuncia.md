# D-059 · Edge: playlist só sobe DEPOIS dos segmentos que ela anuncia

**Seção:** Rodada 4 — a caça ao congelamento (04/08, noite) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · PR #308**

O pusher subia `[playlist, *segments]` e o `.ts` novo ainda aguardava 1 s de settle + até 2 s de tick →
1–3 s por segmento com o manifesto na nuvem anunciando arquivo inexistente (rajadas de 425 no player,
micro-congelamentos). Regra nova no `tick`: segmentos primeiro; playlist só quando nada listado ficou para
trás (assentando/falhou/sumiu/vazio) — a playlist anterior, ainda válida, cobre o intervalo (TTL 20 s).
