# D-047 · R2 CORS bloqueado por falta de permissão da credencial — ação do Vitor

**Seção:** Rodada de 04/08 — Live view fluido + canal 6 · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (achado) · 📌 dívida**

No boot, `PutBucketCors` retorna `AccessDenied` — a credencial R2 usada é de escopo *object-level*, sem
permissão de gerenciar o bucket (confirmado: `Get` e `Put BucketCors` negados no DEV). Hoje **não** quebra
a exibição de imagens de anotação (a tag `<img>` não dispara preflight CORS), mas **vai** quebrar upload
direto do browser e leitura via canvas/`fetch`.

Resolver antes da etapa de anotação: ou dar permissão de bucket à credencial no dashboard Cloudflare R2,
ou configurar o CORS do bucket fora da aplicação. **Ação do Vitor** — não automatizável sem token
Cloudflare.
