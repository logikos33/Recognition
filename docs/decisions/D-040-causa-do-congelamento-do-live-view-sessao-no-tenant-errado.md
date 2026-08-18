# D-040 · Causa do congelamento do live view: sessão no tenant errado, não buffer/rede/capacidade

**Seção:** Rodada de 04/08 — Live view fluido + canal 6 · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · PR #296**

O superadmin (`vitor@devlogikos.com`, tenant DEV `22222222…`) abria a grade com as 8 câmeras da RVB
(`63c219d8…`) **sem assumir o contexto**. `stream_info` recusava o cross-tenant com 404 (C-01, correto),
o token de playback expirava, e a imagem congelava sem explicação na tela. O playback seguia rodando
enquanto o token antigo valia — override por role superadmin em `build_stream_url` — o que mascarava a
causa real por minutos.

Descartadas por medição: buffer, rede, capacidade — GPU a 0%, segmentos em 30–50ms no momento do
congelamento.

Correção: falha **visível** na tela + CTA "assumir contexto", sem afrouxar o 404 do cross-tenant
(ADR-0017, C-01 preservados — nenhuma exceção nova de tenant).
