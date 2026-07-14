# ADR-0042 — Fluxo de recuperação de senha (admin reset + self-service por e-mail)

**Status:** Aceita · **Data:** 2026-07-13 · **Data de aceite:** 2026-07-14 ·
**Implementado em:** PR #153 (Fase 2 — self-service por e-mail). Fase 1 (reset
por admin) já existia previamente em `admin/routes.py`. · **Relaciona:**
ADR-0019 (device tokens RS256 — auth), ADR-0017 (tenant isolation), ADR-0025
(roles/permissões por tenant), `services/api/app/api/v1/auth/`,
`services/api/app/api/v1/admin/routes.py`, `apps/frontend/src/pages/Login.tsx`.

## Contexto

Validamos em sessão que **não existe nenhum fluxo de recuperação de senha** no sistema. As senhas
são hash **bcrypt** (`$2b$12$`, mão única) — irrecuperáveis por design. Hoje, um usuário que esquece
a senha fica travado: a única saída é `UPDATE users SET password_hash` manual no Postgres (foi o que
fizemos para `vitor@logikos.com` no banco local nesta sessão — solução pontual, não escalável).

Recon do que já existe (grounding, não memória):
- **Auth** (`auth/routes.py`): só `register` / `login` / `me`. Nenhuma rota de forgot/reset.
- **Admin** (`admin/routes.py`): `POST /users/<id>/force-password-reset` **apenas liga a flag**
  `force_password_reset=true` — não gera senha nova. O padrão de gerar senha temporária
  (`secrets.token_urlsafe(12)` + `hash_password`) + token no Redis (`first_access:{token}`, TTL 48h)
  existe, porém no caminho de **criar/convidar** usuário, não no de resetar um existente.
- **Redis** já é usado para tokens efêmeros (bridge SocketIO + first-access). `REDIS_URL` disponível.
- **Tabela `users`** já tem a coluna `force_password_reset boolean`.
- **Login é pré-auth, fora do `AppRoutes`** — renderizado direto no `App.tsx` (gate de auth). O
  `AppRoutes`/`ThemeProvider` só montam depois de autenticado.
- **Sem infra de e-mail:** zero SMTP/SendGrid/SES/Resend no código; nenhuma env de e-mail além de
  `ADMIN_EMAIL`. Enviar link de reset é uma **dependência nova**.

## Decisão

Entregar recuperação de senha em **duas fases**, em **PRs separados para `staging`**.

### 1. Provedor de e-mail: Resend (com SMTP como fallback plugável)
Escolha do **Resend**: API HTTP simples (sem SMTP), boa entregabilidade, free tier ~3.000 e-mails/mês,
setup rápido (verificar domínio + API key). O módulo de e-mail (`app/infrastructure/email/`) é
**plugável por env**, permitindo trocar para SMTP genérico sem mudar as rotas.
**Bloqueio da Fase 2:** o Vitor precisa criar a conta Resend, verificar o domínio e fornecer
`RESEND_API_KEY`. Enquanto isso, a Fase 1 avança sozinha.

### 2. Tokens no Redis — SEM migration
Tokens de reset vivem no Redis (`pwreset:{token} → user_id`, TTL ~30min), reaproveitando o padrão
`first_access`. A coluna `force_password_reset` já existe. **Nenhuma migration necessária** — evita o
overhead do protocolo de migration P0 e mantém a mudança forward-only trivial.

### 3. Fase 1 — Reset por admin (sem dependência externa)
- **Backend:** `POST /admin/users/<id>/reset-password` (só `superadmin`) — gera senha temporária,
  atualiza o hash, seta `force_password_reset=true`, retorna a senha temporária **uma única vez**.
- **Frontend:** ação "Resetar senha" por usuário em `AdminUsersPage.tsx` → modal exibindo a senha
  temporária uma vez (botão copiar).
- **Enforcement (opcional na fase):** login detecta `force_password_reset` e obriga troca no 1º acesso
  (tela "definir nova senha" + `POST /auth/set-password`).

### 4. Fase 2 — Self-service por e-mail (após a conta Resend)
- **Backend:**
  - `POST /auth/forgot-password` {email} → **sempre 200** (não vaza existência do e-mail); se existir,
    gera token no Redis e envia link `{FRONTEND_URL}/reset-password?token=…`. **Rate-limit** por e-mail/IP.
  - `POST /auth/reset-password` {token, nova_senha} → valida token, troca hash, limpa a flag,
    **invalida sessões**, apaga o token.
  - Módulo de e-mail plugável (Resend default / SMTP fallback).
- **Frontend:**
  - Link "Esqueci minha senha" no Login → `ForgotPasswordPage` (mensagem de confirmação **neutra**).
  - `ResetPasswordPage` (lê token da URL → nova senha → volta pro login).
  - **Roteamento pré-auth no `App.tsx`** para essas telas serem acessíveis sem login.
- **Config (env/Railway):** `RESEND_API_KEY`, `EMAIL_FROM`, `FRONTEND_URL`.

## Alternativas consideradas
- **SMTP direto em vez de Resend:** mais fricção de config/entregabilidade; mantido como fallback.
- **Tabela `password_reset_tokens` no Postgres em vez de Redis:** exigiria migration P0 e limpeza de
  expirados; Redis com TTL nativo é mais simples e já é o padrão do projeto para tokens efêmeros.
- **Só reset por admin (sem self-service):** insuficiente — não resolve auto-atendimento do usuário
  final; por isso a Fase 2.

## Consequências / trade-offs
- **A favor:** Fase 1 destrava o caso imediato sem dependência externa; Redis evita migration;
  módulo de e-mail plugável não amarra ao Resend; resposta neutra + rate-limit reduzem enumeração.
- **Contra:** Fase 2 fica **bloqueada** até a conta Resend/domínio verificado; roteamento pré-auth é
  um novo padrão no `App.tsx` (hoje sem router antes do login).
- **Segurança:** tratar `nova_senha` com política mínima; invalidar sessões no reset; jamais logar
  token/senha; e-mail de reset nunca confirma se a conta existe.

## Referências
`services/api/app/api/v1/auth/routes.py`, `services/api/app/api/v1/admin/routes.py`,
`apps/frontend/src/pages/Login.tsx`, `apps/frontend/src/App.tsx`,
`apps/frontend/src/modules/admin/pages/AdminUsersPage.tsx`, ADR-0019, ADR-0017, ADR-0025.
Resend — https://resend.com/docs.
