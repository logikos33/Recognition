# CHANGELOG

Todas as alterações relevantes deste projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).
Versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [v2.5.0] — 2026-04-19

### Adicionado

#### Database (Migration 033)
- Tabela `quality_pieces` — state machine de peças com 11 estados e 2 terminais (approved/rejected)
- Tabela `quality_reworks` — histórico de retrabalho por peça com fotos antes/depois e duração calculada
- Tabela `quality_wiser_exports` — log de exportações para o sistema Wiser com retry automático
- Tabela `quality_stations` — configuração de bancadas: câmeras overview/closeup, torre luminosa, tablet URL
- `create_tenant_schema()` atualizada para incluir as 4 tabelas RVB em novos tenants automaticamente

#### Backend — Novos Serviços
- `state_machine.py` — `PieceStateMachine` com mapa `VALID_TRANSITIONS` imutável; 11 estados, transições validadas, bloqueio em terminais
- `gate_repository.py` — `GateRepository` com CRUD completo para pieces/reworks/exports/stations; `overview_stats` e `rework_stats`
- `gate_service.py` — `GateService` orquestra state machine, Redis publish, Celery dispatch, tower signal e exportação Wiser
- `ocr_service.py` — `OcrService` com PaddleOCR primário e pyzbar como fallback para leitura de número de peça
- `tower_controller.py` — `TowerController` ABC com implementações Simulated, GPIO e HTTPRelay; seleção por `TOWER_CONTROLLER_TYPE`
- `photo_service.py` — `PhotoService` com save local e upload R2; fallback silencioso em falha de R2
- `wiser_integration.py` — `WiserIntegration` com 3-mode fallback: API REST → file share → PDF

#### Backend — Endpoints (17 novos em `/api/v1/quality/gate/`)
- `POST /gate/pieces` — criar peça no estado idle
- `GET /gate/pieces` — listar peças com filtros (status, work_order, data)
- `GET /gate/pieces/<id>` — obter peça por ID
- `POST /gate/pieces/<id>/identify` — transição idle→identified (OCR ou manual)
- `POST /gate/pieces/<id>/inspect` — iniciar inspeção, despacha task Celery
- `POST /gate/pieces/<id>/result` — processar resultado YOLO (OK/NOK)
- `POST /gate/pieces/<id>/false-positive` — reverter resultado NOK para identified
- `POST /gate/pieces/<id>/release-to-bench-b` — transição waiting_bench_b→validating_v3
- `GET /gate/reworks` — listar retrabalhos com filtros
- `POST /gate/reworks` — registrar início de retrabalho
- `PATCH /gate/reworks/<id>/complete` — concluir retrabalho com duração calculada
- `GET /gate/stations` — listar bancadas
- `GET /gate/stations/<code>` — status da bancada com peça atual
- `POST /gate/stations` — criar bancada
- `PUT /gate/stations/<code>` — atualizar bancada
- `GET /gate/stats/overview` — KPIs diários
- `GET /gate/stats/rework` — estatísticas de retrabalho

#### Backend — Celery
- Task `run_quality_gate_inspection` — inspeção sob demanda com algoritmo de votação N-frames
- Task `retry_failed_wiser_exports` — retry periódico (Beat, 5 min) de exports falhos
- `quality-wiser-retry` adicionado ao `beat_schedule` em `celery_app.py`

#### Backend — WebSocket
- Canal Redis `quality:piece_identified:<schema>` → evento `quality_piece_identified` no namespace `/quality`
- Canal Redis `quality:inspection_started:<schema>` → evento `quality_inspection_started`
- Canal Redis `quality:inspection_result:<schema>` → evento `quality_inspection_result`
- Canal Redis `quality:station_state:<schema>` → evento `quality_station_state`

#### Frontend — Tablet Kiosk
- `types/gate.ts` — interfaces TypeScript: PieceStatus, ValidationType, QualityPiece, QualityRework, QualityStation, WiserExport
- `useTabletWebSocket.ts` — hook WebSocket namespace `/quality` filtrado por `stationCode`
- `TabletKiosk.tsx` — state machine com 7 views (idle/identified/validating/ok/nok/transition/approved)
- `TabletIdle.tsx` — tela de espera com fundo navy e label da bancada
- `TabletIdentified.tsx` — número de peça, ordem de produção, barra de progresso V1/V2/V3
- `TabletValidating.tsx` — spinner CSS e label da validação em curso
- `TabletResultOK.tsx` — tela verde com auto-avanço em 3 segundos
- `TabletResultNOK.tsx` — tela vermelha com foto do defeito, botões CORRIGIR e FALSO POSITIVO
- `TabletTransition.tsx` — transição Bancada A→B com confirmação do operador
- `TabletApproved.tsx` — celebração 3/3 com métricas de retrabalho condicionais

#### Frontend — Páginas de Dashboard
- `QualityGateDashboard.tsx` — KPI cards, peças ativas ao vivo, status das bancadas, polling 15s
- `QualityPiecesPage.tsx` — tabela paginada com filtros e detalhe expandível
- `QualityReworkPage.tsx` — métricas e gráfico de barras inline por tipo de validação
- `QualityReportsPage.tsx` — agrupamento por ordem de produção, ícones Wiser, export CSV
- `QualityConfigPage.tsx` — editor inline de bancadas, sliders de threshold, configuração de padrão OCR

#### Testes
- `backend/tests/quality/` — 10 arquivos, 71 testes passando, 1 skipped, 0 falhas

### Modificado
- `backend/app/api/v1/quality/routes.py` — adicionados 17 endpoints Quality Gate
- `backend/app/core/socket_bridge.py` — adicionados 4 canais Redis do namespace `/quality`
- `backend/app/infrastructure/queue/tasks/quality_inference.py` — adicionadas tasks `run_quality_gate_inspection` e `retry_failed_wiser_exports`
- `backend/app/infrastructure/queue/celery_app.py` — adicionado `quality-wiser-retry` ao `beat_schedule`
- `frontend/src/AppRoutes.tsx` — adicionada rota pública `/tablet/:station` (lazy, sem JWT)
- `frontend/src/modules/quality/QualityLayout.tsx` — adicionados 5 itens de navegação e rotas correspondentes

---

*Versao anterior: consultar historico Git (branch staging)*
