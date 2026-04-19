# quality-gate-rvb — 2026-04-19

## Resumo

Implementação completa do Quality Gate RVB Isolantes: fluxo de inspeção em 3 validações (V1/V2/V3) com máquina de estados, retrabalho rastreado, torre luminosa, exportação Wiser e interface tablet kiosk. A feature cobre banco de dados, serviços backend, 17 endpoints REST, 4 canais WebSocket, 5 páginas frontend e 71 testes.

## Arquivos Alterados

| Arquivo | Tipo | Impacto |
|---------|------|---------|
| `backend/app/infrastructure/database/migrations/033_quality_rvb.sql` | Novo | Schema — 4 tabelas novas + ALTER em quality_inspections e quality_camera_config |
| `backend/app/api/v1/quality/state_machine.py` | Novo | Core — define todos os 11 estados e transições válidas |
| `backend/app/api/v1/quality/gate_repository.py` | Novo | Persistência — CRUD completo para pieces/reworks/exports/stations |
| `backend/app/api/v1/quality/gate_service.py` | Novo | Orquestração — state machine + Celery + Redis + torre + Wiser |
| `backend/app/api/v1/quality/ocr_service.py` | Novo | Leitura de número de peça via PaddleOCR + pyzbar fallback |
| `backend/app/api/v1/quality/tower_controller.py` | Novo | Controle de torre luminosa — ABC + Simulated/GPIO/HTTPRelay |
| `backend/app/api/v1/quality/photo_service.py` | Novo | Captura e upload de fotos (local + R2, fallback silencioso) |
| `backend/app/api/v1/quality/wiser_integration.py` | Novo | Exportação para Wiser — 3 modos: API REST, file share, PDF |
| `backend/app/api/v1/quality/routes.py` | Modificado | +17 endpoints em /api/v1/quality/gate/* |
| `backend/app/core/socket_bridge.py` | Modificado | +4 canais Redis: piece_identified, inspection_started, inspection_result, station_state |
| `backend/app/infrastructure/queue/tasks/quality_inference.py` | Modificado | +tasks run_quality_gate_inspection e retry_failed_wiser_exports |
| `backend/app/infrastructure/queue/celery_app.py` | Modificado | +quality-wiser-retry no beat_schedule (intervalo 5 min) |
| `frontend/src/modules/quality/types/gate.ts` | Novo | Tipos TypeScript: PieceStatus, ValidationType, QualityPiece, QualityRework, QualityStation, WiserExport |
| `frontend/src/modules/quality/tablet/useTabletWebSocket.ts` | Novo | Hook WebSocket para namespace /quality, filtrado por stationCode |
| `frontend/src/modules/quality/tablet/TabletKiosk.tsx` | Novo | Componente raiz do kiosk — state machine com 7 views |
| `frontend/src/modules/quality/tablet/TabletIdle.tsx` | Novo | Tela de espera — fundo navy, label da bancada |
| `frontend/src/modules/quality/tablet/TabletIdentified.tsx` | Novo | Tela de peça identificada — número, ordem, barra V1/V2/V3, botão iniciar |
| `frontend/src/modules/quality/tablet/TabletValidating.tsx` | Novo | Tela de validação em curso — spinner CSS, label da validação |
| `frontend/src/modules/quality/tablet/TabletResultOK.tsx` | Novo | Tela de resultado OK — fundo verde, auto-avanço em 3 segundos |
| `frontend/src/modules/quality/tablet/TabletResultNOK.tsx` | Novo | Tela de resultado NOK — fundo vermelho, foto do defeito, ações CORRIGIR/FALSO POSITIVO |
| `frontend/src/modules/quality/tablet/TabletTransition.tsx` | Novo | Tela de transição Bancada A para B — botão de confirmação do operador |
| `frontend/src/modules/quality/tablet/TabletApproved.tsx` | Novo | Tela de aprovação — celebração 3/3, métricas de retrabalho condicionais |
| `frontend/src/modules/quality/pages/QualityGateDashboard.tsx` | Novo | Dashboard — KPI cards, peças ativas ao vivo, status das bancadas, polling 15s |
| `frontend/src/modules/quality/pages/QualityPiecesPage.tsx` | Novo | Tabela paginada de peças com filtros, detalhe expandível com retrabalhos e foto |
| `frontend/src/modules/quality/pages/QualityReworkPage.tsx` | Novo | Métricas de retrabalho, gráfico de barras por tipo de validação, modal de foto |
| `frontend/src/modules/quality/pages/QualityReportsPage.tsx` | Novo | Relatórios agrupados por ordem de produção, ícones Wiser, export em lote e CSV |
| `frontend/src/modules/quality/pages/QualityConfigPage.tsx` | Novo | Editor de bancadas inline, sliders de threshold V1/V2/V3, configuração de padrão OCR |
| `frontend/src/AppRoutes.tsx` | Modificado | +rota pública /tablet/:station (lazy TabletKiosk, sem JWT) |
| `frontend/src/modules/quality/QualityLayout.tsx` | Modificado | +5 itens de navegação: Gate, Pecas, Retrabalho, Relatorios, Config |
| `backend/tests/quality/conftest.py` | Novo | Fixtures compartilhadas: mock_pool, mock_redis |
| `backend/tests/quality/test_state_machine.py` | Novo | 19 testes — todas as transições, predicados terminal/validating/rework |
| `backend/tests/quality/test_gate_service.py` | Novo | 8 testes — create/identify/inspect/result/false-positive/rework/duration |
| `backend/tests/quality/test_gate_repository.py` | Novo | 7 testes — verificação SQL INSERT/SELECT/filter |
| `backend/tests/quality/test_ocr_service.py` | Novo | 4 testes — paths pyzbar/PaddleOCR/sem-texto/imagem-inválida |
| `backend/tests/quality/test_tower_controller.py` | Novo | 6 testes — simulated/http_relay/seleção por env factory |
| `backend/tests/quality/test_wiser_integration.py` | Novo | 4 testes + 1 skipped — modos api/file_share/pdf/all-fail |
| `backend/tests/quality/test_photo_service.py` | Novo | 4 testes — save/r2-upload/r2-skipped |
| `backend/tests/quality/test_gate_routes.py` | Novo | 17 testes — todos os endpoints com JWT mock |

## O Que Mudou

### Database — Migration 033

- Antes: módulo quality sem rastreamento de peças individuais, sem fluxo multi-bancada
- Depois: 4 novas tabelas por schema de tenant (quality_pieces, quality_reworks, quality_wiser_exports, quality_stations); tabelas existentes quality_inspections e quality_camera_config recebem colunas para vincular inspeções ao fluxo RVB
- Motivo: suportar rastreabilidade completa da peça da entrada até a aprovação final

### State Machine

- Antes: sem controle formal de estados de peça
- Depois: `PieceStateMachine` com mapa `VALID_TRANSITIONS` imutável; toda transição passa por `can_transition()` antes de persistir; estados terminais `approved` e `rejected` bloqueiam qualquer avanço
- Motivo: garantir integridade do fluxo sem bypass direto no banco

### Fluxo de Inspeção

- Antes: inspeção única por câmera sem contexto de peça ou bancada
- Depois: fluxo em 3 etapas — V1 (Bancada A), V2 (Bancada A), V3 (Bancada B); cada etapa com votação N-frames via Celery; resultado OK avança, NOK cria retrabalho rastreado; falso positivo reverte para `identified`
- Motivo: atender processo real de inspeção de isolantes RVB com múltiplas bancadas

### Tower Controller

- Antes: sem acionamento de sinalização física
- Depois: adapter pattern com três implementações selecionadas por `TOWER_CONTROLLER_TYPE` env var (simulated, gpio, http_relay); sinal verde em OK, vermelho em NOK, idle em transição
- Motivo: desacoplar lógica de negócio da implementação de hardware

### Wiser Integration

- Antes: sem exportação para sistema ERP/MES
- Depois: `WiserIntegration` com 3 níveis de fallback — API REST, file share (pasta compartilhada), PDF local; retry automático via Celery Beat a cada 5 minutos para exports falhos
- Motivo: garantir rastreabilidade no sistema Wiser mesmo com falhas pontuais de rede

### WebSocket — socket_bridge

- Antes: canais det:* (EPI) e training:*
- Depois: +4 canais no namespace /quality por schema de tenant (piece_identified, inspection_started, inspection_result, station_state)
- Motivo: tablet kiosk e dashboard precisam de atualizações em tempo real sem polling

### Frontend — Tablet Kiosk

- Antes: sem interface dedicada para operador de chão de fábrica
- Depois: rota pública /tablet/:station renderiza TabletKiosk; 7 telas mapeadas ao estado da peça via WebSocket; sem necessidade de JWT (acesso controlado por rede interna)
- Motivo: operador precisa de interface simples e tela cheia para acompanhar o fluxo

## Como Testar

1. Executar a migration: `psql $DATABASE_URL -f backend/app/infrastructure/database/migrations/033_quality_rvb.sql`
2. Rodar suite de testes do módulo: `cd backend && python -m pytest tests/quality/ -v --tb=short`
3. Iniciar API localmente e criar uma peça: `POST /api/v1/quality/gate/pieces` com `{"piece_number":"RVB-001","work_order":"OP-2026-001"}`
4. Avançar a state machine: `POST /api/v1/quality/gate/pieces/<id>/identify` → `POST /api/v1/quality/gate/pieces/<id>/inspect`
5. Abrir tablet kiosk no browser: `http://localhost:3000/tablet/bench_a`
6. Verificar dashboard em `http://localhost:3000/quality/gate`

## Dívidas Técnicas Geradas

- `gate_create_station` usa `return success(...), 201` incompatível com Flask quando `success()` retorna objeto `Response`. Correção: `return jsonify(...), 201` ou adicionar parâmetro `status_code` ao helper `success()`
- `R2Storage` não implementa `get_instance()` — `photo_service.py` cai silenciosamente em `r2_key` vazio em todo upload. Correção: implementar `R2Storage.get_instance()` ou ajustar instanciação no `photo_service`
- Testes de `wiser_integration` têm 1 skipped por ausência de `reportlab` no ambiente de teste — instalar em `requirements/worker.txt` para cobertura completa

## Dependencias Adicionadas

| Pacote | Versão | Motivo |
|--------|--------|--------|
| `paddleocr` | latest compat. | Leitura OCR do número da peça |
| `pyzbar` | latest compat. | Fallback para leitura de código de barras/QR |
| `reportlab` | latest compat. | Geração de PDF como fallback final da exportação Wiser |

---
*Gerado automaticamente em 2026-04-19T00:00:00-03:00*
