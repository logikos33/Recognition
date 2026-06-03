---
title: "Edge heartbeat ingest endpoint (O1/Fase 2)"
pr_title: "feat(edge): endpoint POST /api/v1/edge/heartbeat (ingest + device-token auth)"
commit_message: "feat(edge): heartbeat ingest endpoint com device-token RS256 + repo + testes"
eval: default
budget_minutes: 60
---

# Tarefa 002 — Endpoint de ingest de heartbeat do edge

## Objetivo
Criar POST /api/v1/edge/heartbeat: o edge-sync-agent envia telemetria; o cloud valida o payload,
autentica por device token (RS256) e grava em public.edge_heartbeats (tabela já existe — Fase 1).
Primeiro sinal vital do edge → destrava a Fase O1 (observabilidade). Sem hardware.

## Contexto (LER antes — princípio C-04, não adivinhar)
- Ler CLAUDE.md, /constitution.md, e a seção Fase 1/edge do EDGE_DEPLOYMENT_PLAN.md.
- Ler shared/python/recognition_shared/ (models Heartbeat, DeviceClaims) — reusar, não recriar.
- Ler como blueprints são registrados (services/api/app/api/v1/*/routes.py + onde são montados).
- Ler app/core/responses.py (success/error), app/infrastructure/database/connection.py (DatabasePool),
  e um repository existente como referência de padrão (psycopg2 + RealDictCursor, SQL no repository).
- Ler services/api/tests/conftest.py pra usar o harness de teste existente (DB/fixtures) — seguir o padrão.

## Comportamento do endpoint
- Rota: POST /api/v1/edge/heartbeat (criar o blueprint app/api/v1/edge/ se não existir e registrá-lo).
- Auth: header Authorization: Bearer <device_token RS256>. Verificar assinatura contra
  device_tokens.public_key_pem (lookup por device_id/fingerprint), checar revoked=false e expiração.
  Extrair tenant_id/site_id/device_id das claims (DeviceClaims). Token inválido/revogado → 401/403.
- Body: validar com recognition_shared.Heartbeat (Pydantic v2). Payload inválido → 422.
- Persistir em public.edge_heartbeats (tenant_id, site_id, device_id + métricas) via um repository novo
  (EdgeHeartbeatRepository) usando DatabasePool. Atualizar device_tokens.last_seen_at.
- Resposta: success() com 200/201. Zero PII em log; usar logging, nunca print (C-05).

## Arquivos (criar/alterar — NÃO tocar fora disto)
- app/api/v1/edge/__init__.py, routes.py (blueprint + rota)
- app/infrastructure/database/repositories/edge_heartbeat_repository.py
- registro do blueprint onde os outros são montados
- app/core/ — só se precisar de um helper de verificação de device token (ex: device_auth.py)
- tests novos em services/api/tests/ (ver eval)
- NÃO tocar: infra/migrations/, .github/, railway_start.py (guard-rail aborta se tocar).

## Eval (default: ruff + pytest + tsc) — os testes SÃO o critério de sucesso
Escrever testes de API (seguindo o conftest existente) cobrindo:
- token válido + payload válido → 200/201 e 1 linha gravada em edge_heartbeats (assert no banco/mocked repo).
- token assinado por chave errada / revogado / expirado → 401 ou 403; nada gravado.
- sem Authorization → 401.
- payload fora do schema Heartbeat → 422.
Os testes devem semear um device_tokens + gerar um keypair RS256 no próprio teste (não depender de enrollment).
Se o suite de api mockar o banco, mockar o repository; se usar DB de teste, usar a fixture existente.

## Critérios de aceitação
- [ ] Endpoint funciona conforme acima; multi-tenant (tenant_id/site_id SEMPRE do registro de enrollment (device_tokens no banco), nunca das claims nem do body).
- [ ] Verificação RS256 real contra public_key_pem; revoked/expirado barrados.
- [ ] Pydantic Heartbeat valida o body (422 em inválido).
- [ ] Testes novos cobrindo os 4 casos acima, todos verdes.
- [ ] ruff + pytest + tsc verdes. Sem print, CORS/SQL conforme constituição.
- [ ] PR para develop (o driver cuida — branch agent/*, base develop).

## Checkpoint
- Só PR (humano revisa). Sem banco de produção. Se faltar contexto, ler os arquivos — não adivinhar.
