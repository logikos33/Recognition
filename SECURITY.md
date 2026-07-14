# Política de Segurança — Recognition

Recognition é um SaaS de visão computacional multi-tenant sobre CFTV. Segurança e isolamento entre
clientes são requisitos de produto, não opcionais.

## Reporte de vulnerabilidades

- **Não** abra issue pública para vulnerabilidades. Envie em canal privado para **logikos33@gmail.com**
  (assunto: `SECURITY — Recognition`) com descrição, impacto, passos de reprodução e, se possível, PoC.
- Prazo-alvo de primeira resposta: 72h. Correções de severidade alta entram pelo fluxo `risk:security` com
  **STOP-for-review** humano antes de qualquer promoção a produção (`staging`).
- Divulgação coordenada: pedimos que aguarde a correção subir a produção antes de tornar público.

## Controles automatizados no CI

| Controle | Ferramenta | Workflow | Bloqueia merge? |
|---|---|---|---|
| Secret scanning | gitleaks | `.github/workflows/security-scan.yml` (`gitleaks`) | ✅ sim |
| License gate (zero AGPL no servido) | `scripts/check_license_gate.py` + pip-licenses | `.github/workflows/ci.yml` (`license-gate`) | ✅ sim |
| SAST (achados de código Python) | bandit | `security-scan.yml` (`bandit`) | ⚠️ não ainda — baseline documentado em `docs/runbooks/sast-sca-baseline-phase0.md`, promove a bloqueante após triagem |
| SCA (vulnerabilidades conhecidas em dependências Python) | pip-audit | `security-scan.yml` (`pip-audit`, matrix por arquivo de `requirements/`) | ⚠️ não ainda — mesmo motivo acima |
| SCA (dependências npm) | `npm audit --audit-level=high` | `security-scan.yml` (`npm-audit`, `apps/frontend` e `apps/landing`) | ⚠️ não — sinal informativo |
| SBOM por build | Syft (CycloneDX JSON) | `security-scan.yml` (`sbom`) | n/a — artefato, não gate |
| Actions de terceiros pinadas por SHA | — | todos os workflows em `.github/workflows/` | n/a — mitigação de supply chain |
| Atualização automatizada de dependências | Dependabot | `.github/dependabot.yml` (pip, npm, github-actions) | n/a |
| Lint + testes | ruff, pytest | `ci.yml` | ✅ sim |
| Pre-commit local | ruff + gitleaks | `.pre-commit-config.yaml` | n/a — roda antes do commit, não no CI |

## Escopo e princípios (o que o produto garante)

- **Isolamento multi-tenant (C-01):** schema-per-tenant; toda query filtra o tenant de `get_tenant_schema()`;
  acesso cross-tenant retorna **404** (nunca 403 — não vazamos existência). Sem fallback silencioso de tenant
  (ADR-0017). Ver `docs/security/THREAT_MODEL.md` para a análise STRIDE completa dessa fronteira, incluindo
  gaps conhecidos ainda não corrigidos.
- **Autenticação:** JWT com claims `tenant_id`/`tenant_schema`/`role`. Devices de edge usam **JWT RS256 com
  escopos** (ADR-0019), com enrollment por token one-time.
- **Rede edge↔cloud:** **MikroTik + WireGuard**, discagem outbound (ADR-0020). Câmeras nunca expostas à
  internet (port-forward proibido por design).
- **Cadeia de licença:** o detector servido é **ONNX Apache 2.0**; **zero ultralytics/AGPL** no caminho
  servido, garantido pelo license-gate no CI.
- **Migrations forward-only:** apenas `CREATE ... IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`; nunca
  `DROP`/`ALTER TYPE`/`DELETE`/`TRUNCATE`.

## Práticas exigidas de quem contribui

- Nunca commitar segredos; usar `.env` (ver `.env.example`) e variáveis do Railway.
- Zero f-string com input do usuário em SQL (inclusive `SET search_path`) — vetor de injection real já visto.
- `RTSPUrlValidator` antes de qualquer URL chegar ao FFmpeg; `CORS` com origins explícitas; sem `print()` no
  backend (`logging.getLogger(__name__)`).

## Privacidade (LGPD)
O produto processa imagem de pessoas identificáveis (dado pessoal). Ver `docs/security/LGPD_PRIVACIDADE_CFTV.md`
(RIPD, retenção, base legal, direitos do titular).

> ⚠️ Este documento descreve práticas de engenharia e não constitui aconselhamento jurídico.
