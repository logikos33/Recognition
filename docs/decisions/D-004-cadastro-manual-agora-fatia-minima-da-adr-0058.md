# D-004 · Cadastro manual agora + fatia mínima da ADR-0058

**Seção:** Câmeras e edge · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**03/08 · Vitor (AskUserQuestion) · ✅ vigente · PR #281 mergeado**

Descartadas: manual sem a fatia (repete SSH a cada câmera) e ADR-0058 completa primeiro (atrasa a coleta).
Entregue: mapa de canais via `config/poll`, divergência banco×edge visível no heartbeat.
Efeito colateral bom: expôs que o box rodava código anterior ao #281 e o `Permission denied` no cache de
config — corrigido com `EDGE_CONFIG_CACHE_PATH`.
