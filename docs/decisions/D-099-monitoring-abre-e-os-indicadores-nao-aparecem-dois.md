# D-099 · "/monitoring abre e os indicadores não aparecem": DOIS problemas independentes (deploy sobrescrito + crash de render que apagava a página), fail-loud + gráficos dinâmicos + downsample

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · Claude · ✅ código mergeado para develop** _(era D-94 nesta branch)_

Diagnóstico dos 4 elos da corrente (dado real, não chute):

1. **Coletor grava (box)** — SAUDÁVEL para o sintoma: 726 amostras/2h no ring buffer
   (`~/edge-telemetry/metrics.db`, res 10s/1m/5m). ⚠️ Mas a unit `edge-monitoring-collector`
   entrou em **crash-loop** às 11:43 UTC — `No module named app.monitoring`: um OTA da rodada
   de propagação repontou `recognition/current` para o release `f8a3f1d4`, que **não continha
   `app/monitoring/`** (o módulo só existia em `feat/edge-monitoring`, agora mergeado). Há 2h de
   histórico — não é a causa do "vazio total", virou problema só 15 min antes.
2. **Comando nuvem→box — MORRIA AQUI.** A API-V3 do DEV **não servia o blueprint**
   `/api/v1/monitoring` (`GET /sites` → catch-all `{"frontend":"separate service"}` 200;
   `POST .../query` → 405) — deploy sobrescrito pela rodada paralela. **Zero comandos
   `monitoring.*` em 8h** (último sucesso 04:09 UTC, 2,1MB). Classe [[dev-api-singleton-race]];
   a saída definitiva foi o merge para develop (uma origem única de deploy).
3. **Box responde→API** — N/A (nenhum comando chegava).
4. **Front renderiza** — ALÉM do catch-all, havia um **bug de código que apagava a página
   INTEIRA**: `InferencePanel` lia `detections.chain.detection_to_ingest_s`, mas o contrato real
   aninha `chain` **por câmera** (`routes.py site_detections`) — `detections.chain` `undefined`
   → TypeError no render → o `<ErrorBoundary>` global trocava todo o conteúdo por "Erro
   inesperado". `usePolling(loadDetections)` dispara na montagem, então a página **branqueava no
   primeiro RTT** mesmo com API e box saudáveis. Este era o "200 e nada aparece".

Decisões/correções (código):

- **Vazio nunca mudo (a correção mais importante, independente da causa).** `ErrorState`
  (vermelho, ícone, motivo) **visualmente distinto** do `EmptyState` neutro; `PanelBoundary`
  por painel — um card que quebra no render degrada só a si mesmo com o motivo, **nunca derruba
  a página** (re-arma sozinho quando chega amostra nova). Banner de frescor distingue os quatro
  estados: coletando desde X · coletor parado há Y (vermelho) · não implementado (inferência) ·
  erro ao buscar (+ tentar de novo).
- **Fail-loud no envelope**: `monitoringService.unwrap()` — um 200 catch-all (deploy
  sobrescrito) vira erro diagnóstico *"a API não está servindo o monitoramento — verifique o
  deploy"* em vez de `undefined` silencioso. `loadDetections` ganhou try/catch (erro ≠ "sem
  detecção").
- **Contrato alinhado ao que o box/API realmente emitem** (C-04, verificado contra código e
  dado ao vivo): detecções `last_occurred_at`/`detections_in_window`/`chain` por câmera;
  `net.api_ok`+`api_status_age_s` (não `api_last_ok_ts`); `collection.available` (não
  `enabled`). Teste de regressão falha-antes/passa-depois (`EdgeMonitoring.contract.test.tsx`).
- **Gráficos dinâmicos** (recharts): domínio de tempo controlado, **zoom por arraste** +
  ctrl/alt-scroll, **pan** (shift-drag / modo mover), **tooltip com valor e timestamp**, **séries
  sincronizadas** (`syncId`) — cruzar throttling térmico × queda de FPS no mesmo instante.
  Navegação **sob demanda**: pan/zoom para antes do carregado sobe para a janela que cobre —
  só em interação do usuário, zero-egress preservado.
- **Downsample no BOX antes do egress** (`MetricsReader.query` honra `layers` + `max_points`,
  extrema-preserving): baseline 2h all-layers **1,79MB** → `layers=[hw,net] max_points=400`
  **262KB**; **30d `layers=[hw]` 290KB** (vs 57MB sem cap). O front pede
  `layers=[hw,net,collection]`+cap para a série (painéis usam o snapshot completo no `latest`).

Merge para develop unifica a origem de deploy: com o monitoring na develop, deploys baseados em
develop param de sobrescrever o coletor/blueprint. Falta redeploy da API-V3 DEV + OTA do box a
partir da develop atualizada (coordenar com a propagação, que também vive nesses singletons).
