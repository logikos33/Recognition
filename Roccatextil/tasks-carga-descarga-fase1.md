# Backlog — Recognition Carga & Descarga · Fase 1 (Rocabella)

**Criado em:** 11/06/2026 · Numeração provisória CD-xx (renumerar no padrão do repo)
**Legenda de prioridade (se a Rocabella embarcar primeiro):**
- 🔴 **P0** — caminho crítico do go-live em 25 dias; sem isso não há ativação
- 🟡 **P1** — precisa estar pronto até a ativação assistida (dias 21-25), mas não bloqueia o início
- 🟢 **P2** — pós-go-live / Fase 2; não gastar hora agora, só não bloquear na arquitetura

**Mapa do cronograma de 25 dias:** instalação (1-5) · calibração (6-20) · ativação assistida (21-25)

---

## 🔴 CD-01 — Operation-type de contagem de rolo com histerese (linha + zona)
**O quê:** criar o operation-type de contagem na doca usando linha de cruzamento + zona de confirmação (histerese), não linha única. Direção: out=carga, in=descarga (descarga fica dormante na Fase 1). Integrar voto multi-amostra (reusa 038).
**Por quê (pesquisa):** nvdsanalytics conta pelo ponto inferior central da bbox; linha única gera dupla contagem com objeto oscilando sobre ela.
**Reuso:** counting_line, task-038.
**Aceite:** rolo parado em cima da linha não conta 2×; vai-e-volta na zona conta saldo líquido correto; teste com replay de vídeo gravado.
**Janela:** dias 1-10.

## 🔴 CD-02 — Benchmark de tracker: ByteTrack vs NvDCF
**O quê:** rodar os dois trackers sobre os mesmos vídeos da doca (assim que houver gravação real) e medir ID-switches e erro de contagem. Decidir e travar o tracker do produto.
**Por quê (pesquisa):** ID-switch é a principal causa de contagem falsa; NvDCF tem caso conhecido de reatribuição de ID gerando cruzamento fantasma; ByteTrack mostrou ~32% menos ID-switches em benchmark público.
**Aceite:** relatório curto com métricas dos dois + decisão registrada; config do escolhido versionada.
**Janela:** dias 6-12 (precisa de vídeo real da instalação).

## 🔴 CD-03 — Migration `loading_sessions` + ingest real (mata o mock)
**O quê:** tabela de sessões (baia + caminhão/placa + direção + total + início/fim + vídeo + campos `esperado`/`divergencia` nulos) e pipeline de ingest ligando eventos de cruzamento à sessão aberta da baia. Remover dados fictícios do superadmin.
**Reuso:** modelo já esboçado no fueling; frames/R2.
**Aceite:** evento de cruzamento real aparece numa sessão real em <5s; sessão fechada é imutável; mock desligado por feature flag.
**Janela:** dias 1-15.

## 🔴 CD-04 — Coleta de dataset embutida (active learning desde o dia 1)
**O quê:** o pipeline salva automaticamente frames de baixa confiança (e amostra aleatória por turno) num bucket de re-anotação; fluxo de export pra ferramenta de anotação e re-treino.
**Por quê (pesquisa):** modelo de rolo é o único treino custom e o caminho crítico dos 25 dias; meta de produção ≥1.500 imagens/≥10k instâncias, com 5-10% de frames de fundo.
**Reuso:** frames/R2, task-039 (tuning), task-045 (modelo por câmera).
**Aceite:** desde o dia 1 da instalação o sistema acumula dataset sem intervenção; primeiro re-treino executado até o dia 15.
**Janela:** dias 1-20 (contínuo).

## 🟡 CD-05 — Abertura automática de sessão por presença de caminhão + placa
**O quê:** detecção de `truck` na doca abre a sessão; leitura de `plate` vincula; saída do caminhão fecha. Fallback manual (1 toque) enquanto a detecção amadurece.
**Por quê (pesquisa):** é o padrão dos líderes (Zebra "load", Vimaan); elimina o último passo manual do fluxo.
**Reuso:** classes truck/plate da migration 041.
**Aceite:** sessão abre/fecha sem toque humano em ≥90% dos casos no piloto; fallback manual sempre disponível.
**Nota de priorização:** o go-live PODE acontecer com abertura manual — se o prazo apertar, degrada pra P2 sem quebrar a promessa ao cliente.
**Janela:** dias 10-20.

## 🟡 CD-06 — Evidência de primeira classe por sessão
**O quê:** clipe de vídeo + placa + timestamps + thumbnail por sessão, acessível em 1 clique no dashboard e exportável (link compartilhável).
**Por quê (pesquisa):** prova visual foi o diferencial de venda unânime entre os players; persona do conferente: "desconfio de número sem vídeo".
**Reuso:** frames/R2.
**Aceite:** de qualquer sessão no dashboard chega-se ao vídeo do carregamento em ≤2 cliques; clipe cobre do 1º ao último cruzamento.
**Janela:** dias 10-20.

## 🟡 CD-07 — Modo validação/aceite (a tela do go/no-go)
**O quê:** tela que pareia contagem do sistema vs. contagem manual por sessão durante a ativação assistida, calcula erro por sessão/turno e gera o relatório de aceite (critério sugerido: erro ≤2-5% por turno).
**Por quê (pesquisa):** validar eventos e não só totais (FP e FN se cancelam); critério de aceite contratual definido ANTES protege a ativação. Vira ferramenta de QA permanente.
**Reuso:** task-043 (relatórios).
**Aceite:** relatório de aceite por turno sai em PDF/export com 1 clique; usado de verdade nos dias 21-25 da Rocabella.
**Janela:** pronto até o dia 18.

## 🟡 CD-08 — Dashboard real em três visões + export
**O quê:** substituir o mock por: (a) visão SUPERVISOR — status das 6 docas agora, sessão em andamento, alerta de doca parada; (b) visão GERENTE — tendências (tempo médio, throughput, ociosidade por turno/semana); (c) visão ANALISTA — export CSV no grão de sessão.
**Por quê (pesquisa):** personas mostraram 3 leituras do mesmo dado; uma tela única erra para 2 dos 3 usuários. Benchmarks pro dashboard: dock-to-stock ≤3,5h best-in-class (WERC), turnaround <2h.
**Reuso:** dashboard do fueling, task-043.
**Aceite:** supervisor entende o estado das 6 docas em ≤30s (teste com persona); export bate com as sessões do banco.
**Janela:** dias 12-20 (versão mínima); refinamento pós-go-live.

## 🟢 CD-09 — Shadow mode de modelo
**O quê:** rodar modelo candidato em paralelo ao oficial, comparando contagens sem afetar produção; promover com 1 clique e rollback automático.
**Nota:** não construir agora — apenas garantir que a arquitetura do CD-04 (versionamento de modelo+config) não impeça isso depois.

## 🟢 CD-10 — Gatilho de faturamento e conferência (Fase 2)
**O quê:** evento "sessão fechada com total X" exposto via API/webhook para liberar faturamento; campos `esperado`/`divergencia` ativados com fonte manual → ERP/OCR de romaneio (PaddleOCR do Qualidade).
**Nota:** é o coração da venda da Fase 2 (anti-furto, anti-disputa, NF correta antes da circulação). Só não bloquear: CD-03 já deixa os campos no schema.

---

## Ordem de ataque se a Rocabella assinar amanhã

| Semana | Foco |
|---|---|
| 1 (dias 1-5, instalação) | CD-03 (sessões+ingest) e CD-04 (coleta ligada no 1º dia) começam junto com a instalação física; CD-01 em bancada com vídeo gravado |
| 2 (dias 6-12) | CD-02 (benchmark tracker com vídeo real) → trava config; CD-01 calibrado na doca; 1º re-treino do modelo |
| 3 (dias 13-20) | CD-07 (validação) e CD-08 (dashboard mínimo); CD-05 e CD-06 em paralelo conforme folga |
| 4 (dias 21-25) | Ativação assistida usando CD-07 como instrumento do aceite; ajustes finos |
