# GO-LIVE CHECKLIST — Recognition / EPI Monitor V2 (cliente âncora: RVB Isolantes)

**Data:** 2026-06-22 · **Branch de integração:** `develop` · **Produção:** Railway (deploy a partir de `staging`/`main`)

> Separação que importa: o que é **software e roda autônomo agora** (Bloco A) vs. o que **depende
> de hardware/estar no site da RVB** (Bloco B) vs. o que é **gate humano** (Bloco C). O prompt de
> autorun ataca só o Bloco A; B e C ficam registrados aqui como pendência explícita.

---

## Estado atual (verificado no código)
- Mutirão de qualidade **em andamento** (branch `quality/item-07`). P0 de IDOR cross-tenant já
  mergeados (#52 alerts, #53 counting). 2 P0 do CLAUDE.md eram falso-positivo (schema sem `tenant_id`).
- Testes deselecionados sendo reabilitados (#54/#55/#56). Gate de cobertura ainda em 30 (sobe no fim).
- Plataforma cloud madura: ~30 blueprints, multi-tenant por schema, 64 migrations, vitest+playwright.
- Edge: `edge-sync-agent` existe, camera-gateway real, DeepStream esboçado, migrations de edge no banco
  (050/053/055/056/057). Fases 6–10 do `EDGE_DEPLOYMENT_PLAN.md` **bloqueadas por hardware**.

---

## BLOCO A — Software, executável AGORA (autônomo, sem hardware)

- [ ] **A1. Concluir o mutirão de qualidade.** Terminar a fila `queue-mutirao.txt` (P0 restantes,
      contrato front↔back, cobertura). Regras do `MUTIRAO.md` (teste de regressão nos P0, anti-gaming).
- [ ] **A2. Corrigir o contrato front↔back** (matriz `CONTRATO_FRONT_BACK.md`): rotas que o front
      chama e não existem (`/classes` no AnnotationInterface, `/quality/gate/rework/start` no tablet),
      alinhar shapes ao envelope `{status,data}`, migrar `fetch()` raw → `api.ts` (AnnotationInterface
      em PR próprio, needs-human).
- [ ] **A3. Subir o gate de cobertura para ≥60%** num PR final dedicado (`chore(ci): raise coverage gate`),
      em `ci.yml` e no comando de portão do AUTORUN — só depois que os testes reais aterrissarem.
- [ ] **A4. Endpoints de edge gated por migration (029/030/031/041).** Migrations já existem
      (edge_events 055, edge_commands 056, site_gateways 057, camera hardening). Rodar **duplo-boot em
      staging** (run_migrations 2×, idempotente) e então ligar os endpoints. Protocolo de Migration (CLAUDE.md).
- [ ] **A5. Notificação (042) + flywheel (044).** MIGRATION + endpoint. Mesmo fluxo de duplo-boot.
- [ ] **A6. Frontend dual-mode (Fase 7 do edge plan) — parte de código.** A UI precisa operar
      edge+cloud (resolução de fonte de stream por câmera/site). Validação de fallback real é on-site (B).
- [ ] **A7. Provisionamento RVB (Fase 8) — scaffolding.** Seed/migração para criar o tenant RVB,
      cadastrar as 28 câmeras Intelbras VIP e as zonas/operações via frontend. Sem segredo de produção no repo.
- [ ] **A8. Promoção `develop → staging`.** PR `develop→staging` → Railway builda → `./scripts/smoke_test.sh
      <url-staging>` 200 → acompanhar o 1º boot (migrations auto-rodam com backfill por tenant).

---

## BLOCO B — Depende de HARDWARE / estar no site da RVB (NÃO automatizável)

- [ ] **B1. Hardware físico:** Jetson Orin NX 16GB + MikroTik + 28 câmeras Intelbras VIP cabeadas/PoE.
- [ ] **B2. Compilar engines TensorRT no próprio device** (específico do device/JetPack — não pré-compila na cloud).
- [ ] **B3. Deploy do edge stack on-site** (Fase 6): DeepStream + edge-sync-agent pareado com a cloud, plug-and-play.
- [ ] **B4. Self-healing + hot-swap (035)** — validação real só on-site.
- [ ] **B5. Validar fallback do dual-mode (036)** com queda de link real no site.
- [ ] **B6. Modelo treinado nos dados da RVB:** instalar câmeras → coletar frames → anotar (UI +
      pre-annotation) → treinar → publicar. Encanamento existe; o modelo de produção depende de dados reais.
- [ ] **B7. Plug-and-play day (037):** go-live assistido no site.

---

## BLOCO C — Gate humano (não auto-merge)

- [ ] **C1. Promoção `staging → main` (produção).** Cutover que afeta o Railway de produção — sign-off humano.
- [ ] **C2. Revisão de segurança dos endpoints de edge** (ingestão/ comandos): authz por device, replay, SSRF.
- [ ] **C3. Variáveis/segredos de produção:** `JWT_SECRET_KEY`, `CAMERA_SECRET_KEY` (Fernet), R2_*, `CORS_ORIGINS`, TLS.

---

## Sequência recomendada
A1 → A2 → A3 (fecha o mutirão) · A4/A5 (edge endpoints via duplo-boot) · A6/A7 (dual-mode + provisioning) ·
A8 (sobe pra staging) → **para em C1/C3** (humano). Bloco B só com o hardware no site.
