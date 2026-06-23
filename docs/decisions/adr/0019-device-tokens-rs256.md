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
