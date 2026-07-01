# Harness — Plano de Implementação

> **Status:** plano executável para discussão e refinamento.
> **Data:** 2026-06-02 · **Cliente âncora:** RVB Isolantes · **Deadline RVB:** ~2026-07-12.
> **Pré-requisito de leitura:** `docs/architecture/HARNESS_EXPLORATORIO.md` (o porquê). Este documento é o "como".
> **Companion:** `EDGE_DEPLOYMENT_PLAN.md` (Fase 9 = test harness original, aqui antecipado e ampliado).

Este plano organiza a construção do harness em **duas trilhas paralelas** — **Trilha O (Operação remota)** e **Trilha D (Desenvolvimento autônomo)** — mais uma **camada transversal de economia**. Cada fase tem objetivo, entregáveis, critérios de aceitação, dependência de hardware e nota de custo. O formato segue o padrão do `EDGE_DEPLOYMENT_PLAN`: fases sequenciais com gates obrigatórios.

---

## 0. Princípios (do que a pesquisa confirmou)

Antes das fases, as práticas externas que adotamos como regra. Cada uma vira requisito nas fases abaixo.

**Operação de fleet edge:**
- **Telemetria proativa, não reativa** — o dispositivo reporta saúde sozinho (CPU/mem/GPU/conectividade/uptime) e a equipe detecta degradação *antes* de virar outage, em vez de esperar o cliente reclamar.
- **Staged rollout** — toda mudança vai em fases: canário (subconjunto) monitorado, depois piloto, depois geral, com **rollback** e **delta updates** (só o diff, não o pacote inteiro).
- **Self-healing por política** — agentes de saúde + automação reiniciam/realocam workload em falha localizada sem humano.
- **Plataforma de gestão de containers** — como o edge roda docker-compose, usar uma ferramenta de fleet (Portainer, open-source, self-hosted) dá deploy/restart/logs remoto de container sem SSH manual.

**Desenvolvimento autônomo:**
- **Headless é a base** — `claude -p --output-format json` roda o loop completo (pensar→agir→verificar) e sai, sem REPL. É o que tira o copy-paste.
- **Pré-autorizar ferramentas** — `--allowedTools` especifica exatamente o que o agente pode fazer (abordagem mais segura).
- **Spec + testes = autonomia** — com plano/spec detalhado e bons testes, o agente verifica o próprio código contra a spec e itera sozinho por períodos longos. Sem isso, autonomia vira dívida.
- **Orquestrador injeta contexto** — um driver monta o prompt com árvore de arquivos, diffs recentes e resultado dos testes, e roda um loop multi-turno validando cada iteração com teste+lint.
- **Segurança do agente** — `.claudeignore` para `.env` (segredos nunca vão pra API); tratar texto de PR/issue como dado não-confiável (anti prompt-injection).

**Economia (transversal):**
- **Prompt caching** — contexto repetido (CLAUDE.md, specs, ADRs) cacheado custa ~10% do preço de input (90% off). Maior alavanca isolada.
- **Model routing** — Haiku para classificação/extração/formatação; Sonnet para implementação padrão; Opus só para síntese arquitetural/decisão de alto risco. Economia típica 60–80%.
- **Batch API** — para trabalho não-real-time (ex: rodar suíte de cenários à noite), 50% off.
- **Observability econômica** — começar com a tabela `edge_heartbeats` + painel admin (custo zero); plugar Sentry cedo (barato, erros/traces); OpenObserve (open-source, free tier ~50GB/dia) ou Grafana self-hosted só quando o volume justificar.

> Combinando caching + routing + batch, a redução conservadora de custo de agente fica em **70–85%**.

---

# TRILHA O — Operação Remota

Meta para o go-live RVB: **Nível N2 (comandos remotos estruturados) com pedaços de N3 (auto-cura)**, conforme a escala da Parte I do exploratório.

## Fase O1 — Observabilidade base *(pode começar AGORA, sem hardware)*

**Objetivo:** ter os sinais vitais do edge visíveis no cloud.

**Entregáveis:**
- Endpoint `/api/v1/edge/heartbeat` (ingest) gravando em `edge_heartbeats` (tabela já criada na Fase 1).
- Painel admin "Sites & Saúde": por site, último heartbeat, status, FPS, câmeras online/total, GPU/CPU/disco, profundidade de fila, versão do edge.
- Regra de "site offline" (sem heartbeat há > N min) → evento de saúde.
- Logs estruturados (JSON, sem PII) do edge enviados em batch + retidos no cloud.
- Sentry plugado no cloud e no edge-sync-agent (erros/traces) — barato, alto valor.

**Critérios de aceitação:**
- [ ] Heartbeat de um edge simulado (harness) aparece no painel em < 30s.
- [ ] Status muda para `offline` automaticamente quando o heartbeat para.
- [ ] Erros do edge aparecem no Sentry com stack trace e tag de site.
- [ ] Zero PII nos logs (auditoria manual de amostra).

**Hardware:** não precisa (usa edge simulado do harness). **Custo:** Sentry tier dev (baixo); resto é infra que já existe.

## Fase O2 — Acesso remoto seguro *(precisa do PC, mas configura em minutos)*

**Objetivo:** entrar na máquina da RVB de qualquer lugar, sem abrir porta.

**Entregáveis:** Tailscale SSH (`ssh user@rvb-blumenau-01`) + Cloudflare Tunnel (expõe API/live-view LAN do edge ao cloud) — ambos já decididos no plano. Runbook de acesso + revogação.

**Critérios de aceitação:**
- [ ] SSH via hostname Tailscale de outra máquina funciona.
- [ ] Live-view LAN acessível via Tunnel sem inbound aberto.
- [ ] Revogar um device do Tailscale corta o acesso na hora.

**Hardware:** sim (Mini PC). **Custo:** Tailscale e Cloudflare Tunnel têm tier gratuito que cobre 1 site.

## Fase O3 — Plano de comandos remotos (N2) *(parte agora no harness, fecha com PC)*

**Objetivo:** agir na operação sem SSH — do painel/celular.

**Entregáveis:**
- Fila de comandos no cloud (tabela `edge_commands`: site_id, tipo, payload, status, X-Command-Id idempotente, auditoria de quem/quando/resultado).
- Edge consome por polling (mesmo padrão HTTP polling + idempotência do ADR-0004) e reporta resultado.
- Comandos v1: `restart_pipeline`, `restart_stack`, `reload_model`, `recalibrate_camera`, `set_camera_fps`, `toggle_camera`, `rotate_device_token`, `pull_diagnostics`, `drain_buffer`.
- Botões correspondentes no painel admin, com confirmação e log visível.

**Critérios de aceitação:**
- [ ] Cada comando é idempotente (reenvio não duplica efeito) e versionado.
- [ ] Comando executado no edge simulado retorna resultado ao painel em < 10s.
- [ ] Toda execução fica auditada (autor, timestamp, resultado).
- [ ] Comando sem device token válido / escopo errado → 403.

**Hardware:** lógica e idempotência testáveis no harness agora; validação real com o PC. **Custo:** zero (infra existente).

## Fase O4 — Self-healing (N3) *(fecha com PC)*

**Objetivo:** o edge se conserta sozinho no trivial e só te chama no que precisa.

**Entregáveis:**
- Supervisão de processo (systemd/supervisord + restart policy no docker-compose) — pipeline morto reinicia.
- Watchdog de câmera com reconnect/backoff (o `camera_manager` já reconecta a 2s; formalizar + métrica).
- Autonomia offline: inferência continua, eventos vão pra SQLite, drena ao voltar (cenário 2 da Fase 9).
- Circuit breaker de GPU: fila estourando → derruba FPS antes de travar + emite evento de saúde.
- Escalonamento: quando a auto-cura não resolve, notificação (canal a definir) com pacote de diagnóstico anexado.
- **Gestão de fleet via Portainer** (open-source, self-hosted): deploy/restart/logs de container remoto sem SSH manual.

**Critérios de aceitação:**
- [ ] Matar um pipeline → reinicia sozinho em < 30s, registrado.
- [ ] Cloud offline 1h → zero perda de eventos no drain (cenário 2 verde).
- [ ] GPU saturada → FPS cai automaticamente, sistema não trava, evento emitido.
- [ ] Falha não-recuperável → alerta chega com diagnóstico em < 2 min.

**Hardware:** sim (especialmente circuit breaker de GPU). **Custo:** Portainer CE gratuito.

## Fase O5 — OTA e rollout controlado *(fecha com PC, crítico pré go-live)*

**Objetivo:** atualizar modelo/config/edge sem ir à fábrica e sem risco.

**Entregáveis:**
- Rollout em fases: canário (subconjunto de câmeras/um pipeline) → piloto → site inteiro.
- **Delta updates** (só o diff) + **checksum** + **rollback** automático se a saúde degradar pós-update (o hot-swap de modelo do cenário 3 já é a base).
- Manifest de versão publicado pelo cloud; edge faz polling, valida checksum, aplica, reporta.

**Critérios de aceitação:**
- [ ] Publicar modelo novo → edge aplica via canário, valida saúde, expande; rollback automático se FPS/erro degradam.
- [ ] Update interrompido no meio não corrompe o estado (idempotente/atômico).
- [ ] Runbook de rollout + rollback documentado.

**Hardware:** sim. **Custo:** zero.

---

# TRILHA D — Desenvolvimento Autônomo

Meta: sair de L0 (copy-paste) para **L2 (loop headless com auto-retry, humano revisa PR + checkpoints)** nas fases de software puro (1, 2, 4).

## Fase D1 — Fonte de verdade: harness de migrations *(AGORA, retorno imediato)*

**Objetivo:** matar a classe de bug das Sprints 0.5/0.6 (inferir schema em vez de verificar).

**Entregáveis:**
- `tests/harness/` inicial com `docker-compose` subindo Postgres efêmero.
- Runner que aplica `infra/migrations/*.sql` num banco limpo (na ordem do `railway_start.py`) e valida o schema resultante (tabelas, colunas, tipos, índices, FKs).
- Teste de idempotência: aplica tudo 2x sem erro (espelha o runner de produção, que não tem `schema_migrations`).
- Plugado no CI (check rápido a cada PR).

**Critérios de aceitação:**
- [x] Migrations 050–054 (Fase 1) validadas pelo harness contra Postgres real efêmero.
- [x] Rodar 2x = zero erro.
- [x] CI roda o harness de migrations em < 2 min por PR.

**Status:** ✅ Concluída em 2026-06-02 — ver `tests/harness/migrations/` e CI job `migrations-harness`.

**Hardware:** não. **Custo:** zero (docker local + CI).

## Fase D2 — Synthetic RTSP + cenários núcleo *(AGORA, antecipa Fase 9)*

**Objetivo:** ter o ambiente que simula a RVB localmente — fonte de verdade do edge e fixture de operação.

**Entregáveis:**
- MediaMTX servindo um vídeo loop como câmera RTSP fake (`tests/harness/fixtures/synthetic-rtsp/`).
- `docker-compose.harness.yml` subindo cloud (api+redis+postgres) + edge simulado.
- Cenário 1 (baseline: enrollment → evento chega no cloud) e Cenário 5 (multi-tenant isolation: tenant A não vê dados de B; token de A em B → 403).
- `runner/fault_injection.py` mínimo (derruba rede do edge).

**Critérios de aceitação:**
- [ ] Cenário 1 verde: evento sintético chega ao cloud em < 5s.
- [ ] Cenário 5 verde: isolamento e 403 confirmados.
- [ ] Subset rápido roda no CI; completo roda sob demanda.

**Hardware:** não (synthetic RTSP). **Custo:** zero.

## Fase D3 — Driver headless L1 *(AGORA, depois de D1/D2)*

**Objetivo:** rodar uma tarefa fechada de ponta a ponta sem copy-paste.

**Entregáveis:**
- Script orquestrador (Node ou Python) que chama `claude -p --output-format json` com `--allowedTools` restrito, injetando no prompt: árvore de arquivos, diff recente e resultado dos testes.
- Loop multi-turno: roda harness (D1/D2) + ruff + tsc; verde → commita e abre PR pra `develop`; vermelho → devolve o erro pro agente (até N tentativas); irreversível → para e escala.
- `.claudeignore` cobrindo `.env` e segredos; política de tratar input externo como não-confiável.
- Aplicar primeiro numa tarefa real e fechada (ex: uma sub-tarefa da Fase 2).

**Critérios de aceitação:**
- [ ] Uma tarefa fechada vai de prompt a PR aberto sem intervenção manual de código.
- [ ] Agente nunca toca `main`, nunca faz `DROP`, para nos checkpoints.
- [ ] Segredos comprovadamente fora do que vai pra API.

**Hardware:** não. **Custo:** tokens do agente — ver Camada E (caching + routing cortam 70–85%).

## Fase D4 — Driver autônomo L2 *(depois de D3 validado)*

**Objetivo:** o agente puxa tarefas de uma fila e desenvolve sozinho as fases de software puro, com humano só no PR e nos checkpoints.

**Entregáveis:**
- Fila de tarefas (as sub-tarefas das Fases 2 e 4 decompostas, com critérios de aceitação por tarefa).
- Driver L2: pega próxima → executa headless → valida no harness → PR → (humano revisa) → próxima. Auto-retry no vermelho, orçamento/parada por tarefa.
- Spec-driven: contratos OpenAPI/AsyncAPI em `shared/proto/` (ADR-0009) como alvo inequívoco que agente e harness compartilham.
- Onde roda: decidir entre script local, GitHub Actions, ou serviço dedicado (ver decisões em aberto).

**Critérios de aceitação:**
- [ ] Fase 2 (blueprint `/edge`) avança por múltiplas tarefas em loop, cada uma com CI verde, com humano só revisando PRs.
- [ ] Custo por tarefa dentro do orçamento definido.
- [ ] Nenhuma regressão escapa do harness (medido por cobertura de cenário).

**Hardware:** não (Fases 2 e 4 são software puro). **Custo:** controlado por orçamento + Camada E.

> **Limite explícito:** Fases 5/6 (DeepStream/TensorRT/GPU Blackwell) **não entram em L2** sem o PC — não há fonte de verdade local. Lá o agente assiste, o humano decide.

---

# CAMADA E — Economia (transversal a todas as fases)

Aplicar desde a primeira execução de agente:

1. **Prompt caching** no contexto estável (CLAUDE.md, specs, ADRs, este plano) → ~90% off no input repetido.
2. **Model routing**: Haiku (classificar tarefa, extrair, formatar, sumarizar logs), Sonnet (implementação diária), Opus (decisão arquitetural, revisão de migration P0). Economia 60–80%.
3. **Batch API** para o que não é interativo (rodar a suíte completa de cenários à noite, gerar relatórios) → 50% off.
4. **Observability**: começar com `edge_heartbeats` + painel (zero) → Sentry cedo (baixo) → OpenObserve/Grafana self-hosted só quando volume justificar.
5. **Fleet/tunnel/infra**: Portainer CE, Tailscale free, Cloudflare Tunnel free — cobrem 1 site (RVB) sem custo de licença.

**Meta de custo:** manter o gasto de agente 70–85% abaixo do naïve, e a stack de operação da RVB perto de **zero licença** até existir um segundo cliente.

---

# Sequenciamento vs. deadline RVB (~12/07)

**Esta semana (sem PC):** D1 (harness de migrations) → D2 (synthetic RTSP + cenários 1 e 5) → O1 (observabilidade base) → D3 (driver headless L1). Tudo software puro, alto retorno, destrava o resto.

**Quando o PC chegar (semana que vem):** O2 (acesso remoto) → O3 (comandos remotos N2) → começo de O4 (self-healing).

**Pré go-live:** O4 fechado, O5 (OTA/rollout) verde, cenários de fault injection (offline-recovery, isolamento, hot-swap) verdes. D4 (L2) rodando as Fases 2/4 em paralelo durante todo o período.

**Caminho crítico para a RVB funcionar com EPI:** O1 → O2 → O3 → O4(núcleo) → O5(canário+rollback). A Trilha D acelera a entrega, mas a Trilha O é o que te deixa operar sem ir a Blumenau.

---

# Decisões em aberto (destravar antes de executar)

1. **Observability:** confirmar começar com `edge_heartbeats` + painel + Sentry, e deixar OpenObserve/Grafana para depois? (recomendado)
2. **Onde mora o driver autônomo:** script local, GitHub Actions, ou serviço dedicado?
3. **Nível alvo da Fase 2:** rodar em L1 (revisa cada PR) ou já L2 (loop com auto-retry)?
4. **Canal de escalonamento em produção:** e-mail, WhatsApp ou Slack?
5. **Portainer agora ou pós-RVB:** adotar o Portainer já no harness (treina o fluxo) ou só quando o PC chegar?
6. **Orçamento de tokens por tarefa** para o loop autônomo (define a parada).

---

## Fontes (pesquisa 2026)

Operação de fleet edge / OTA / self-healing:
- [2026 Fleet Device Management: Guide for IoT & Edge Teams (Portainer)](https://www.portainer.io/blog/fleet-device-management)
- [Managing an Edge Device Fleet: OTA Updates and Remote Monitoring (Robustel)](https://www.robustel.store/blogs/industrial-iot-blog/managing-an-edge-device-fleet-ota-updates-and-remote-monitoring)
- [How to Configure OTA Updates for Edge Devices (OneUptime)](https://oneuptime.com/blog/post/2026-01-25-configure-ota-updates-edge-devices/view)
- [Best Practices for Edge Device Management with Portainer (OneUptime)](https://oneuptime.com/blog/post/2026-03-20-best-practices-edge-device-management-portainer/view)
- [Edge AI: Applications, Challenges & Best Practices (floLIVE)](https://flolive.net/blog/glossary/edge-ai-8-real-world-applications-challenges-best-practices/)

Agentes de código autônomos / headless / CI:
- [Claude Code as an Autonomous Agent: Advanced Workflows 2026 (SitePoint)](https://www.sitepoint.com/claude-code-as-an-autonomous-agent-advanced-workflows-2026/)
- [Claude Code Headless Mode: CI/CD Automation Playbook (Code With Seb)](https://www.codewithseb.com/blog/claude-code-headless-mode-cicd-automation-playbook)
- [Claude Code Headless Mode: Complete Self-Hosting Guide (amux)](https://amux.io/guides/claude-code-headless/)
- [Best practices for Claude Code (Claude Code Docs)](https://code.claude.com/docs/en/best-practices)

Economia de custo de LLM:
- [Claude Cost Optimization 2026: Batch API + Prompt Caching (PE Collective)](https://pecollective.com/tools/claude-pricing-guide/)
- [LLM Cost Optimization: 5 Levers to Cut API Spend 70-85% (Morph)](https://www.morphllm.com/llm-cost-optimization)
- [Token optimization 2026: Saving up to 80% LLM costs (Obvious Works)](https://www.obviousworks.ch/en/token-optimization-saves-up-to-80-percent-llm-costs/)

Observability econômica:
- [Top Observability Tools & Platforms 2026 (OpenObserve)](https://openobserve.ai/blog/top-10-observability-tools/)
- [7 Grafana Alternatives in 2026 (SigNoz)](https://signoz.io/blog/grafana-alternatives/)
