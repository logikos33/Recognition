---
title: "Edge device enrollment endpoint (Fase 2)"
pr_title: "feat(edge): endpoint POST /api/v1/edge/enroll (one-time, tenant server-bound)"
commit_message: "feat(edge): device enrollment — consome enrollment token one-time, registra public key"
eval: default
budget_minutes: 60
---

# Tarefa 004 — Endpoint de enrollment do device

## Objetivo
POST /api/v1/edge/enroll: o device (Mini PC) se registra usando um enrollment token one-time (gerado na
task-003), envia seu device_id + public_key_pem, e o cloud cria o registro em public.device_tokens
ligando o device ao tenant/site do enrollment token. Fecha o ciclo do device token (o heartbeat da
task-002 valida contra esse registro). Usa tabelas existentes. Sem hardware, sem migration.

## Contexto (LER antes — C-04)
- /constitution.md (C-01, C-05), CLAUDE.md, app/api/v1/edge/routes.py (task-002), app/core/device_auth.py.
- recognition_shared: EnrollmentRequest, EnrollmentResponse, DeviceClaims (reusar; ler os campos reais).
- migrations 051 (enrollment_tokens, device_tokens): campos token_hash, used_at, expires_at, public_key_pem,
  fingerprint, UNIQUE(tenant_id, device_id).
- Como a task-002 atribui tenant/site pelo ENROLLMENT (banco), nunca por dado auto-declarado — seguir igual.

## Comportamento
- Body (validar com recognition_shared.EnrollmentRequest): enrollment_token, device_id, device_name, public_key_pem.
- Validar enrollment token de forma ATÔMICA e one-time:
  - Hash do token recebido; UPDATE public.enrollment_tokens SET used_at=now(), used_by_device_id=<device_id>
    WHERE token_hash=<hash> AND used_at IS NULL AND expires_at > now() RETURNING tenant_id, site_id.
  - Se não retornou linha → 401 (inválido, expirado ou já usado). Isso previne corrida de duplo-uso.
- Criar public.device_tokens: tenant_id e site_id VINDOS DA LINHA do enrollment token (server), device_id e
  public_key_pem do body, fingerprint (derivar do public_key se o model exigir), revoked=false.
  - UNIQUE(tenant_id, device_id): se já existir, decidir conflito → 409 (não sobrescrever silenciosamente).
- Resposta (EnrollmentResponse): identidade ligada do device — tenant_id, site_id, device_id, scopes — para
  o device montar seus próprios JWTs RS256. NUNCA confiar em tenant/site vindo do body.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py (rota /enroll)
- app/infrastructure/database/repositories/ (enrollment repo — pode estender edge_site/device repo existente)
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- token válido (seed enrollment_tokens com tenant_a/site_a, not used, not expired) → 201; device_tokens criado
  com tenant_id=tenant_a/site_a (do token), public_key do body; enrollment_token marcado used_at.
- MESMO token usado 2x → 2ª chamada 401 e nenhum device novo criado (one-time atômico).
- token expirado → 401, nada criado.
- body tentando forjar tenant_id diferente → IGNORADO; device fica no tenant do enrollment token (C-01).
- device_id já existente no tenant → 409.

## Critérios de aceitação
- [ ] tenant_id/site_id do device SEMPRE do enrollment token (server), nunca do body (C-01).
- [ ] one-time atômico (UPDATE ... WHERE used_at IS NULL RETURNING); reuso barrado.
- [ ] public_key_pem persistido; UNIQUE(tenant_id, device_id) respeitado (409 em duplicata).
- [ ] Testes acima verdes; ruff + pytest + tsc verdes; SQL parametrizado; sem print.
- [ ] PR para develop.

## Checkpoint
- Só PR. Sem produção. Sem migration. Faltou contexto → ler os arquivos.
