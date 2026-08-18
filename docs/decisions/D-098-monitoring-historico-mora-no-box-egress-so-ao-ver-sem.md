# D-098 · /monitoring: histórico mora NO BOX, egress só ao ver (sem Prometheus, sem jtop)

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · pedido do Vitor, arquitetura Claude · ✅ (mergeado para develop)** _(era D-93 nesta branch; renumerado no merge — D-93..D-97 ficaram com a rodada de propagação)_

O Jetson da operação era caixa-preta (journald volátil, sinks desligados de propósito, toda
investigação dependia de SSH aberto na hora). Pedido: visão total com histórico, **mas só
consumindo egress quando o Vitor estiver acessando**. Esse requisito decide a arquitetura:

- **Coletor residente no box** (`python -m app.monitoring`, unit `edge-monitoring-collector`
  com CPUQuota=10%/MemoryMax=128M/OOMScoreAdjust=300) grava as 7 camadas num **ring buffer
  SQLite local** com downsample (10s/2h · 1min/48h · 5min/30d) e guarda de reserva de disco.
  Zero conexão de rede no coletor — por construção.
- **Acesso = comando**: a página cria `monitoring.query|snapshot|logtail` na fila
  `edge_commands`; o box responde pelo **canal outbound que já existia** (ADR-0020 — nada
  inbound, nenhuma porta nova). Poll ocioso segue 60s; `monitoring.*` liga **burst de 2s por
  180s**. Página fechada → burst expira → regime idle.
- **Logtail redigido NO BOX** (`redact_url_credentials` antes de qualquer byte sair — senha
  de câmera vive nesses logs).
- **Gate por papel, não por obscuridade**: rota fora do menu E superadmin-only; não-superadmin
  recebe na API **404** e no front o MESMO comportamento de rota inexistente (C-01). Acesso
  auditado em `public.audit_log` (query/snapshot dedup 15min; logtail/thresholds sempre).
- ⛔ **Sem stack Prometheus/Grafana** (outro serviço para operar num box de 16GB, superfície
  nova) — fica no produto. ⛔ **Sem jtop/jetson-stats (AGPL-3.0)** — o agente edge é código
  distribuído ao site do cliente e o gate de licença do CI não olha esse caminho; fontes são
  `tegrastats` (binário NVIDIA, sem encargo, modo contínuo — nunca fork por amostra) + /sys +
  /proc + `systemctl --user show`. Throttling térmico vem dos cooling devices
  `*-throttle-alert` (cur_state>0), OOM kills de `/proc/vmstat` — ambos sem sudo.
- **Substitui o `edge-telemetry-collector` antigo** (JSONL sem teto — 230MB acumulados no
  box); a unit antiga sai de cena no deploy desta rodada. A nova entra nas
  `_DEFAULT_SECONDARY_UNIT_NAMES` do OTA (dívida D-42: unit fora da lista roda código velho).
- **Inferência (operação assistida)**: painéis desenhados AGORA; o runtime preencherá
  `inference.json` (contrato em `app/monitoring/sampler.py`). O indicador central é o
  **heartbeat de detecção** ("câmera X sem detecção há Y min") — na operação assistida,
  silêncio é indistinguível de pipeline morto.

Migration 117 (`edge_monitoring_thresholds`, harness 2x verde). Código: `app/monitoring/` no
edge-sync-agent, blueprint `/api/v1/monitoring`, página `/monitoring` no frontend.
