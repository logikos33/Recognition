# Política de Segurança — Recognition

Recognition é um SaaS de visão computacional multi-tenant sobre CFTV. Segurança e isolamento entre clientes
são requisitos de produto, não opcionais.

## Reporte de vulnerabilidades
- **Não** abra issue pública para vulnerabilidades. Envie em canal privado para **logikos33@gmail.com**
  (assunto: `SECURITY — Recognition`) com descrição, impacto, passos de reprodução e, se possível, PoC.
- Prazo-alvo de primeira resposta: 72h. Correções de severidade alta entram pelo fluxo `risk:security` com
  STOP-for-review humano antes de qualquer promoção a produção (`staging`).
- Divulgação coordenada: pedimos que aguarde a correção subir a produção antes de tornar público.

## Escopo e princípios (o que o produto garante)
- **Isolamento multi-tenant (C-01):** schema-per-tenant; toda query filtra o tenant de `get_tenant_schema()`;
  acesso cross-tenant retorna **404** (nunca 403 — não vazamos existência). Sem fallback silencioso de tenant (ADR-0017).
- **Autenticação:** JWT com claims `tenant_id`/`tenant_schema`/`role`. Devices de edge usam **JWT RS256 com escopos**
  (ADR-0019), com enrollment por token one-time.
- **Rede edge↔cloud:** **MikroTik + WireGuard**, discagem outbound (ADR-0020). Câmeras nunca expostas à internet
  (port-forward proibido por design).
- **Cadeia de licença:** o detector servido é **ONNX Apache 2.0**; **zero ultralytics/AGPL** no caminho servido,
  garantido por gate de licença no CI.

## Controles no CI (já ativos)
- **Secret scanning:** gitleaks (`.github/workflows/security-scan.yml` + `.gitleaks.toml`).
- **License gate:** `scripts/check_license_gate.py` (bloqueia AGPL no servido).
- **Lint/testes:** ruff + pytest.

## Práticas exigidas de quem contribui
- Nunca commitar segredos; usar `.env` (ver `.env.example`) e variáveis do Railway.
- Zero f-string com input do usuário em SQL (inclusive `SET search_path`) — vetor de injection real já visto.
- `RTSPUrlValidator` antes de qualquer URL chegar ao FFmpeg; `CORS` com origins explícitas; sem `print()` no backend.
- Migrations forward-only; nunca `DROP`/`ALTER TYPE`/`DELETE`/`TRUNCATE`.

## Privacidade (LGPD)
O produto processa imagem de pessoas identificáveis (dado pessoal). Ver `docs/security/LGPD_PRIVACIDADE_CFTV.md`
(RIPD, retenção, base legal, direitos do titular).

> ⚠️ Este documento descreve práticas de engenharia e não constitui aconselhamento jurídico.
