# ADR-0019 — Device Tokens RS256 + Escopos para Autenticação de Edge

**Data:** 2026-06-01
**Status:** Accepted
**Contexto:** Edge Deployment Plan — Fase 1 (schema foundation)
**Relacionado:** ADR-0016 (edge-tables-placement)

---

## Contexto

Mini PCs de edge precisam de credenciais para enviar eventos, heartbeats e baixar modelos
sem usar credenciais de usuário humano. O token precisa:
- Ser verificável offline (chave pública no cloud, chave privada apenas no cloud)
- Ter escopos granulares (um device de heartbeat não pode baixar modelos arbitrariamente)
- Suportar revogação imediata
- Permitir rotação de chaves sem downtime

## Decisão

**JWT RS256 com chave pública armazenada no banco** (`device_tokens.public_key_pem`).

### Fluxo de enrollment

1. Operator gera `enrollment_token` no painel (one-time, expira em N horas, hash SHA-256 armazenado em `enrollment_tokens.token_hash`).
2. Mini PC chama `/api/v1/edge/enrollment/redeem` com o enrollment token + `device_id` + `public_key_pem`.
3. API valida token, armazena chave pública + fingerprint em `device_tokens`, retorna JWT RS256 assinado pela chave privada do cloud.

### Claims do JWT de device

```json
{
  "tenant_id": "<uuid>",
  "site_id": "<uuid>",
  "device_id": "<string>",
  "scopes": ["heartbeat:write", "events:write"],
  "iat": 1700000000,
  "exp": 1700086400
}
```

### Escopos disponíveis (`DeviceTokenScope`)

| Escopo | Permite |
|--------|---------|
| `events:write` | Enviar eventos de detecção |
| `config:read` | Ler configuração do site/câmeras |
| `models:download` | Baixar modelos YOLO |
| `heartbeat:write` | Enviar telemetria de hardware |
| `streams:report` | Reportar status de streams |

### Rotação de chaves

- `device_tokens.fingerprint` (SHA-256 do token) permite identificar qual token foi usado no JWT inbound.
- Revogação imediata: `revoked = true` + `revoked_at` + `revoked_by`.
- Rotação: endpoint `/api/v1/edge/auth/rotate` — emite novo JWT sem exigir re-enrollment.

## Alternativas consideradas

**HMAC-SHA256 com segredo compartilhado:** Simples, mas exige segredo no dispositivo. Comprometimento de um device expõe o segredo de todos.

**mTLS:** Robusto, mas requer PKI, renovação de certificados e complexidade de configuração no Railway (TLS termination).

**API Key estática:** Sem expiração, sem escopos. Revogação exige rotação manual.

## Consequências

- Positivo: Revogação imediata, escopos granulares, chave privada nunca sai do cloud.
- Positivo: Verificação offline possível (chave pública pública).
- Negativo: Requer implementação de endpoint de enrollment e rotation (Fase 2).
- Neutro: `device_tokens.public_key_pem` armazena a chave pública, não o token bruto.

## Implementação (Fase 1)

Tabelas criadas em migration 051. Pydantic models em `shared/python/recognition_shared/device.py`.
Endpoints de enrollment e rotation são Fase 2.

---

## Reconciliação com a implementação real (2026-07-18) — S7

> A varredura de segurança (C-04) mostrou que a implementação **diverge** desta ADR em
> três pontos. Esta seção descreve o que o código REALMENTE faz, para a próxima sessão não
> confiar no desenho original. O modelo implementado funciona e é seguro; o texto acima é a
> proposta de jun/2026, não o estado atual.

**1. Endpoint de enrollment.** Não existe `/api/v1/edge/enrollment/redeem`. O real é
`POST /api/v1/edge/enroll` (`services/api/app/api/v1/edge/routes.py:625`), que valida o token
opaco por SHA-256 contra `enrollment_tokens.token_hash`.

**2. Modelo de confiança — o device AUTO-ASSINA (oposto da ADR).** A ADR dizia "API retorna JWT
RS256 assinado pela chave privada do cloud". Na prática o **device gera o próprio par de chaves**,
envia `public_key_pem` no enroll, e `/enroll` devolve apenas `{tenant_id, site_id, device_id,
scopes}`. O device então assina o próprio JWT RS256 com sua chave privada; o cloud verifica com a
chave pública guardada. A revogação é checada **antes** da verificação de assinatura
(`get_device_by_device_id` → `revoked` → `verify_device_token`) — correto. A chave privada do
device nunca sai do device; o cloud nunca teve chave privada de device.

**3. Rotação.** `/api/v1/edge/auth/rotate` **não existe**. Hoje não há rotação de chave sem
re-enrollment. Avaliar se entra no backlog do plano de controle (ADR-0054).

**4. Escopos — aplicação (S1).** Até 2026-07-18 os escopos eram **declarados e nunca aplicados**:
`_DEFAULT_SCOPES` (todos) era ecoado no enroll, mas nenhuma rota checava escopo. A trilha de
segurança introduziu o decorator `require_device_scope` (`app/core/device_auth.py`) aplicado a
`/heartbeat` (`heartbeat:write`), `/config/poll` (`config:read`), `/events/ingest` (`events:write`),
`/commands/pending` (`commands:read`) e `PATCH /commands/<id>` (`commands:write`). Token válido sem
o escopo → **403**.

**5. Escopos — catálogo atualizado.** Foram adicionados dois escopos ao enum `DeviceTokenScope`:

| Escopo | Permite |
|--------|---------|
| `commands:read` | Pollar comandos pendentes do site |
| `commands:write` | Reportar resultado de execução de comando |

> **Nota de rollout:** o enroll concede `_DEFAULT_SCOPES` (todos), então **novos** enrollments já
> recebem os escopos de commands. Devices enrolados ANTES desta mudança não têm `commands:*` no JWT
> auto-assinado — precisam re-enrollar para usar o canal de comandos. Como esta é uma mudança
> `risk:security` **não promovida** (fila humana), o re-enrollment entra no plano de promoção
> `develop→staging`.
