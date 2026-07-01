# task-048 — White-label / theming por tenant (config 100% no frontend)

**risk:low**
**modo:** AUTO

## Objetivo
Permitir rebrand da plataforma por tenant — logo, cores primárias/secundárias, nome do produto,
favicon — configurável pelo painel admin, sem deploy nem código. Base do produto white-label
que a Camerite vende como SKU.

## Por que (Camerite)
Camerite vende White Label (identidade visual do parceiro, mensalidade, sem comprar equipamento)
como produto. Já está no nosso roadmap; confirma que é monetizável. Começar pelo theming
(o domínio próprio fica em task separada — ver nota).

## Escopo
### Backend (`services/api`)
- **Verificar** `tenant_settings`/`tenants` atuais. Guardar branding em JSONB:
  `branding = {logo_url, favicon_url, color_primary, color_secondary, product_name}`.
- Endpoint público leve `GET /api/tenant/branding` (resolve por host/tenant, sem auth pesada —
  é o que o frontend lê no boot pra pintar o tema). `PUT /api/admin/tenant/branding` (role admin).
- Upload de logo/favicon via R2 (reusar storage existente; validar tipo/tamanho).

### Frontend
- Carregar branding no boot e aplicar via CSS variables (cores) + trocar logo/favicon/título.
- Tela de admin "Aparência" com preview ao vivo.
- Fallback para o tema Logikos default quando o tenant não tem branding.

## Fora de escopo
- **Domínio próprio por tenant** (`cliente.logikosvision.com.br`) → task futura (envolve DNS/infra,
  TLS, roteamento por host; risk:security). Anotar, não fazer aqui.
- Tradução/i18n por tenant.

## Critérios de aceite
- Tenant A e Tenant B veem logos/cores diferentes sem rebuild.
- Branding ausente → tema default sem quebrar.
- Upload valida tipo/tamanho; serve do R2.
- Testes: resolução de branding por tenant; fallback.

## Migration
Aditiva se faltar a coluna: `ADD COLUMN IF NOT EXISTS branding JSONB DEFAULT '{}'::jsonb` em
`public.tenants` (ou `tenant_settings`). Idempotente.
