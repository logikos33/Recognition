---
title: "Deployment modes: fluxo cloud-only para cliente SEM edge (feature)"
pr_title: "feat(platform): fluxo cloud-only (cliente sem edge) como feature"
commit_message: "feat(platform): suporte a cliente sem edge (cloud-only)"
eval: default
risk: security
depende_de: ADR-0046, task-093
bloco: 6 (Deployment modes)
---

# Task 094 — Fluxo cloud-only

## Status (2026-07-15, investigação C-04 completa)

**Conclusão: a infraestrutura técnica de "operar sem edge" já era o comportamento padrão — confirmado por
leitura de código, não construído do zero.** Trabalho desta task foi fechar os gaps reais encontrados
(documentação do trade-off de segurança + UX de onboarding), não reimplementar o caminho câmera→nuvem.

**Já era o default (confirmado, não presumido):**
- `stream_handlers.py::stream_info` retorna `stream_type="hls"` (nuvem) para toda câmera por padrão; só muda
  para `"edge_hls"` se a câmera pertencer a um `edge_site` com `deployment_mode='edge'`.
- `POST /api/cameras` (`crud_handlers.py::create_camera`) não exige `site_id` — só `name`/`host`. Tenant nunca
  precisa cadastrar um `edge_site` para operar câmeras.
- `quality_clips.py::_should_upload_evidence_to_r2` (task-092) já é fail-safe: sem `edge_sites` cadastrado (ou
  qualquer erro de leitura), mantém upload de evidência pro R2 — cloud-only nunca perde evidência.

**Gaps reais encontrados e fechados nesta task:**
1. **Trade-off de segurança (lockout de câmera) documentado formalmente** — ver **ADR-0051**. Confirmado que
   ADR-0020 (MikroTik/WireGuard) e `public.site_gateways` (migration 072) + `probe_camera` (`is_behind_nat` /
   `_check_gateway_available`) já implementam o "edge mínimo" (gateway de rede, não Jetson) — só não estava
   nomeado como parte do fluxo cloud-only. Cloud-only agora tem 2 sub-níveis documentados: com gateway
   (mínimo recomendado em produção) e sem gateway (não recomendado, tecnicamente não bloqueado).
2. **`public.tenants.deployment_mode` (migration 067) confirmado morto** — nunca lido em nenhum código de
   produção (só `edge_sites.deployment_mode`, por site, é usado). Decisão: **não wireá-lo** — seria uma
   segunda fonte de verdade dessincronizável da granularidade por site já gerenciada pela task-093. Documentado
   em ADR-0051 para não ser reinterpretado como fonte de verdade numa sessão futura.
3. **UX do `EpiSitesPage` (task-093) corrigida** — o estado vazio ("nenhum site cadastrado") agora explica que
   isso já É o modo cloud-only funcionando, e cita o requisito de gateway se a câmera estiver atrás de NAT.
   Não havia nenhuma trava que assumisse implicitamente um `edge_site` (camera CRUD já funciona sem ele) —
   então nenhum wizard de onboarding novo foi construído (sem evidência de que faltasse).

## Objetivo
Cliente sem edge opera direto na nuvem. Tratar como feature explícita, ciente do trade-off de isolamento de câmera.

## Escopo
- Caminho câmera→nuvem quando `mode=cloud_only`; documentar a limitação de segurança (lockout de câmera) e quando
  exige um edge mínimo.
- Live view e evidência resolvidos pela nuvem nesse modo.

## Aceite
- [x] Um tenant cloud-only opera (câmeras/evidência/live) sem edge; limitações documentadas.
  - Confirmado via leitura de código (não construído nesta task — já era o comportamento padrão).
  - Limitações documentadas em ADR-0051 (trade-off de isolamento de câmera, quando exige gateway mínimo).

## Checkpoint
- STOP-for-review.
