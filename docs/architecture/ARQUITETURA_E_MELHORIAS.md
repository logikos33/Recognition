# Recognition — Arquitetura idealizada + melhorias e gaps

> **Data:** 2026-06-05 · **Âncora:** RVB Isolantes (28 câmeras Intelbras VIP, Blumenau) · **Edge:** Jetson Orin NX 16GB.
> Companion: `CONTENCAO_RISCOS_ESCALA.md`, `PLATAFORMA_CENARIOS.md`, `ROADMAP_GO_LIVE.md`.
> Objetivo deste doc: fechar a visão de ponta a ponta, **explorar o que ainda não pensamos** e listar melhorias
> que aumentam fluidez e reduzem risco **reusando o ecossistema que já temos**.

---

## 1. Visão geral (o diagrama em palavras)

Quatro planos, um fluxo:

1. **Site (RVB):** 28 câmeras Intelbras (substream H.265, rede isolada sem internet) → **Edge Orin NX 16GB**: DeepStream com 3 frentes (EPI `epi_zone`, Qualidade `defect_trigger`, Contagem `counting_line`) em TensorRT INT8 + tracker; **edge-sync-agent** (buffer SQLite, uploader idempotente, config poller); MQTT local pros eventos críticos; self-healing + gravação.
2. **Rede segura:** **MikroTik WireGuard** hub-and-spoke — saída, sem porta aberta; câmeras nunca expostas.
3. **Cloud (Railway):** API+SocketIO (ingest, cenários, rollout, alertas), Worker (treino, cloud-fallback), PostgreSQL multi-tenant + Redis (bus/WS), R2 (evidência + modelos).
4. **Consumo + Operação:** Dashboard React (cenários, Sites&Saúde) · **[novo]** notificação, relatórios, LGPD · e a operação Logikos (NOC, pipeline autônomo, flywheel).

**Fluxos:** detecção (câmera→edge→batch idempotente→cloud→dashboard) · comandos (cloud→polling→edge) · **feedback** (operador marca erro → flywheel → retrain → canário → edge) · **offline** (edge bufferiza e drena ao voltar, sem perda).

---

## 2. O que já temos vs o que falta (resumo)

- **Pronto (cloud):** ingest de heartbeat/health, enrollment/device-token, fleet/Sites&Saúde, cenários (leitura+escrita+3 tipos), model-rollout (canário/pin), edge-agent core, harness sintético. Pipeline autônomo (driver+revisor+fila).
- **Em contenção (fila AUTO):** 038 contagem multi-amostra, 039 tuning por câmera, 040 liveness por câmera.
- **Gated migration:** 029 events ingest, 030 commands, 031 gateways, 041 hardening de câmera.
- **Hardware (Mini PC):** 032 DeepStream, 033 stack+MikroTik, 034 edge real, 035 self-healing, 036 dual-mode, 037 go-live.

---

## 3. Novas soluções / gaps que ainda não exploramos

Cada item: **o quê · risco que reduz · o que reusa · esforço/gate**. Ordem por impacto.

### 🔴 Alta prioridade

**A. Camada de notificação (WhatsApp/Telegram).**
Hoje geramos alerta + evidência (`alert_rules`, `frames`), mas **não entregamos ao humano**. No Brasil, alerta sem WhatsApp não chega. Serviço de notificação no cloud: alerta crítico → mensagem com **snapshot + timestamp + câmera/zona** pro técnico de segurança; com rate-limit/agrupamento (anti-spam) e confirmação de leitura.
- *Reduz:* tempo de resposta a violação; "ninguém viu o alerta". · *Reusa:* alert_rules + frames + R2. · *Esforço:* serviço novo (cloud, AUTO). WhatsApp Cloud API ou Telegram Bot.

**B. LGPD / privacidade (risco legal real).**
Detectar pessoas = dado pessoal. Falta: **política de retenção** (apaga evidência após N dias), **máscaras de privacidade** (não processar banheiro/vestiário — reusa `exclude_zones` da 039), **blur de rosto** na evidência onde não é necessário identificar, **auditoria de acesso** (quem viu o quê) e sinalização/consentimento.
- *Reduz:* multa LGPD, exposição de dados, processo trabalhista. · *Reusa:* frames + R2 (lifecycle) + exclude_zones + RBAC do JWT. · *Esforço:* política de retenção (migration leve + job) + masks (já na 039) + log de auditoria. Misto AUTO/migration.

**C. Relatórios de compliance agendados.**
O cliente não compra detecção — compra **gestão**. Relatório diário/semanal (PDF) com **% de conformidade de EPI, violações por turno/zona, tendência, top reincidências**, enviado ao gestor. Vira ferramenta de management, não só alarme.
- *Reduz:* risco de churn ("não vejo valor"); transforma dados em decisão. · *Reusa:* dashboard/export Excel já existente + tarefas agendadas. · *Esforço:* gerador de relatório + agendador (cloud, AUTO).

**D. Flywheel de modelo (active learning).**
Captamos evidência (`frames`). Um botão **"isso estava errado"** no dashboard alimenta um dataset rotulado → retrain → **canário** (model-rollout 025) → edge. A acurácia sobe com o uso, com custo mínimo de rotulagem.
- *Reduz:* falso-positivo/negativo ao longo do tempo (pesquisa: ~93% real vs ~99% paper → fechar o gap). · *Reusa:* frames + **AnnotationInterface (já existe!)** + training + model-rollout. · *Esforço:* botão de feedback + fila de curadoria + gatilho de retrain. AUTO + trilha de dados.

### 🟡 Média prioridade

**E. Ação física (atuação no local).**
Fechar o loop: `no_helmet` numa zona → **sinaleiro/buzzer/catraca** via GPIO do edge ou integração (relé/Modbus). "Sistema que age", não só que detecta.
- *Reduz:* a violação em si (não só registra). · *Reusa:* edge + MQTT + operations (a regra já existe). · *Esforço:* driver de saída no edge (hardware).

**F. Failover edge→cloud para câmeras críticas.**
Se o edge cai (nó único = SPOF), as **câmeras críticas** (zona perigosa) caem temporariamente pra **inferência no cloud** (Worker/Ultralytics) até o edge voltar. Degradação graciosa em vez de cegueira total.
- *Reduz:* SPOF do nó único. · *Reusa:* Worker cloud-fallback + edge-agent buffer + dual-mode (036). · *Esforço:* roteador de inferência + flag de criticidade por câmera. Misto.

**G. NOC multi-site (operação Logikos).**
Painel de **frota** acima dos tenants pra VOCÊ operar: SLA por site, saúde proativa, auto-abertura de ticket quando degrada. É o que torna escalar pra cliente #2, #3 sustentável.
- *Reduz:* custo operacional ao crescer; "descobrir o problema pelo cliente reclamando". · *Reusa:* fleet-overview (016) + heartbeat + liveness (040). · *Esforço:* agregação multi-tenant + SLA (cloud).

**H. NTP / sincronização de tempo.**
Evidência legal precisa de **timestamp confiável**. NTP nos edges + carimbo consistente cloud/edge; correlação de eventos entre câmeras.
- *Reduz:* contestação de prova; eventos fora de ordem. · *Reusa:* edge config + ingest. · *Esforço:* baixo (config + validação).

### 🟢 Incremental

**I. Onboarding zero-touch:** caixa chega, pluga, **auto-enrolla** (enrollment token 004) e baixa o cenário. Reduz tempo on-site (037).
**J. Tiering de storage:** R2 lifecycle (quente→frio→apaga) alinhado à retenção LGPD. Reduz custo de storage.
**K. Observabilidade:** Sentry (014) + Grafana/Prometheus da frota a partir do heartbeat. Reduz tempo de diagnóstico.

---

## 4. Operação fluida — o "dia a dia" (day-in-the-life)

1. **Detecção:** câmera (substream 5–15 fps H.265) → DeepStream no edge → evento (com snapshot) → MQTT/Redis → edge-agent.
2. **Entrega:** edge-agent → batch idempotente → MikroTik → cloud → Postgres/R2 → SocketIO → **dashboard ao vivo** + **WhatsApp ao técnico** (item A).
3. **Ação:** técnico vê o snapshot, age; (opcional) sinaleiro local já disparou (item E). Tudo auditado.
4. **Gestão:** fim do dia → **relatório de compliance** ao gestor (item C).
5. **Melhoria:** falso-positivo? operador marca → **flywheel** → modelo melhora → canário → edge (item D).
6. **Se o cloud cai:** dashboard cai pro **edge.local** (dual-mode 036); edge continua detectando e bufferiza; drena ao voltar.
7. **Se o edge cai:** câmeras críticas → **cloud-fallback** (item F); NOC abre ticket (item G).

---

## 5. Mapa de redução de risco

| Risco operacional | Contenção | Item |
|---|---|---|
| Alerta não chega ao humano | Notificação WhatsApp + snapshot | A |
| Multa/exposição LGPD | Retenção + máscara + blur + auditoria | B |
| Churn ("não vejo valor") | Relatório de compliance agendado | C |
| Acurácia estagnada | Flywheel (feedback → retrain → canário) | D |
| Violação só registrada, não evitada | Atuação física no local | E |
| Nó único cai = site cego | Failover edge→cloud + dual-mode | F |
| Descobrir falha pelo cliente | NOC multi-site + saúde proativa | G |
| Prova contestável | NTP / timestamp confiável | H |
| Crash 24/7 (decode/energia/memória) | substream+H.265, drop-on-latency, UPS, ECC | (hardware) |

---

## 6. Próximos passos sugeridos (sem mexer no que está rodando)

1. Terminar a **fila AUTO de contenção** (038/039/040) — já enfileirada.
2. **Migrations** (029/030/031/041) pelo checkpoint — destrava ingest/comandos/gateway/hardening.
3. Especificar como tasks: **A (notificação)**, **C (relatórios)**, **D (flywheel)** — são cloud/AUTO, alto valor, testáveis na nuvem **sem o Mini PC**.
4. **B (LGPD)** como trilha própria (parte migration, parte política) — começar cedo pelo risco legal.
5. **E/F/G/H** entram junto com o hardware (Mini PC) e o crescimento multi-site.
