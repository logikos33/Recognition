# Quality Gate Module — Changelog

## [Unreleased] — 2026-04-19

### Added (Quality Gate RVB Isolantes)

#### Database
- Migration 033_quality_rvb.sql: tables quality_pieces, quality_reworks, quality_wiser_exports, quality_stations
- ALTER quality_inspections: piece_id, validation_type, station, defect_description, is_rework, rework_attempt, photo_raw_path, photo_raw_r2_key
- ALTER quality_camera_config: inspection_mode, station, camera_type, validation_types, capture_frames_count, voting_threshold

#### Backend Services
- state_machine.py: PieceStateMachine — 11 states (idle→approved), validated transitions
- gate_repository.py: GateRepository — CRUD for pieces/reworks/exports/stations, overview_stats, rework_stats
- gate_service.py: GateService — orchestrates state machine, Celery dispatch, Redis publish, tower signal, Wiser export
- ocr_service.py: OcrService — PaddleOCR + pyzbar fallback for piece number reading
- tower_controller.py: TowerController ABC + Simulated/GPIO/HTTPRelay implementations
- photo_service.py: PhotoService — local save + R2 upload with silent fallback
- wiser_integration.py: WiserIntegration — 3-mode export: API REST → file share → PDF

#### API Endpoints (17 new under /api/v1/quality/gate/)
- POST /gate/pieces — create piece in idle state
- GET /gate/pieces — list pieces with filters (status, work_order, date)
- GET /gate/pieces/<id> — get piece by ID
- POST /gate/pieces/<id>/identify — transition idle→identified (OCR or manual)
- POST /gate/pieces/<id>/inspect — start inspection, dispatch Celery task
- POST /gate/pieces/<id>/result — process YOLO inspection result (OK/NOK)
- POST /gate/pieces/<id>/false-positive — revert NOK result, return to identified
- POST /gate/pieces/<id>/release-to-bench-b — transition waiting_bench_b→validating_v3
- GET /gate/reworks — list reworks with filters
- POST /gate/reworks — register rework start
- PATCH /gate/reworks/<id>/complete — complete rework with duration
- GET /gate/stations — list workstations
- GET /gate/stations/<code> — station status with current piece
- POST /gate/stations — create workstation
- PUT /gate/stations/<code> — update workstation
- GET /gate/stats/overview — daily overview KPIs
- GET /gate/stats/rework — rework statistics

#### Celery Tasks
- run_quality_gate_inspection — on-demand inspection with N-frame voting algorithm
- retry_failed_wiser_exports — periodic Beat task (5 min) to retry failed exports
- Beat schedule: quality-wiser-retry added to celery_app.py

#### WebSocket Events (Redis → /quality namespace)
- quality:piece_identified:* → quality_piece_identified
- quality:inspection_started:* → quality_inspection_started
- quality:inspection_result:* → quality_inspection_result
- quality:station_state:* → quality_station_state

#### Frontend — Tablet Kiosk
- types/gate.ts: PieceStatus, ValidationType, QualityPiece, QualityRework, QualityStation, WiserExport, event types
- tablet/useTabletWebSocket.ts: WebSocket hook for /quality namespace, filters by stationCode
- tablet/TabletKiosk.tsx: state machine with 7 views (idle/identified/validating/ok/nok/transition/approved)
- tablet/TabletIdle.tsx: navy background, station label
- tablet/TabletIdentified.tsx: piece number, work order, V1/V2/V3 progress bar, start button
- tablet/TabletValidating.tsx: CSS spinner, validation label
- tablet/TabletResultOK.tsx: green screen, auto-advance 3s
- tablet/TabletResultNOK.tsx: red screen, defect photo, CORRIGIR/FALSO POSITIVO buttons
- tablet/TabletTransition.tsx: bench A→B transition with confirm button
- tablet/TabletApproved.tsx: 3/3 celebration, conditional rework metrics

#### Frontend — Dashboard Pages
- QualityGateDashboard.tsx: KPI cards, live active pieces, station status, 15s polling
- QualityPiecesPage.tsx: paginated table with filters, expandable detail with reworks and photo
- QualityReworkPage.tsx: metrics cards, inline bar chart by validation type, photo modal
- QualityReportsPage.tsx: grouped by work order, Wiser icons, batch export, CSV download
- QualityConfigPage.tsx: inline station editor, threshold sliders V1/V2/V3, OCR pattern config

#### Tests (worker-tests — quality-gate-rvb)
- backend/tests/quality/conftest.py: shared fixtures mock_pool, mock_redis
- backend/tests/quality/test_state_machine.py: 19 tests covering all transitions, terminal/validating/rework predicates
- backend/tests/quality/test_gate_service.py: 8 tests covering create/identify/inspect/result/false-positive/rework/duration
- backend/tests/quality/test_gate_repository.py: 7 tests covering INSERT/SELECT/filter SQL verification
- backend/tests/quality/test_ocr_service.py: 4 tests covering pyzbar/PaddleOCR/no-text/invalid-image paths
- backend/tests/quality/test_tower_controller.py: 6 tests covering simulated/http_relay/factory env selection
- backend/tests/quality/test_wiser_integration.py: 4 tests (+1 skipped) covering api/file_share/pdf/all-fail modes
- backend/tests/quality/test_photo_service.py: 4 tests covering save/r2-upload/r2-skipped behaviors
- backend/tests/quality/test_gate_routes.py: 17 tests covering all 17 gate endpoints with JWT mock
- Total: 71 passed, 1 skipped (reportlab not installed in test env), 0 failed

### Changed
- AppRoutes.tsx: added /tablet/:station public route (lazy TabletKiosk)
- QualityLayout.tsx: added Gate/Pecas/Retrabalho/Relatorios/Config nav items and routes
- celery_app.py: added quality-wiser-retry to beat_schedule

### Known Issues / Technical Debt
- Route gate_create_station uses 'return success(...), 201' pattern which is incompatible
  with Flask versions that disallow (Response, int) tuples. Fix: return jsonify(...), 201
  or update success() helper to accept a status_code parameter.
- R2Storage does not implement get_instance() class method — photo_service.py silently
  falls back to empty r2_key on every upload attempt. Fix: implement R2Storage.get_instance()
  or update photo_service to use a different instantiation pattern.

### Architecture Notes
- State machine enforces all piece transitions — no direct DB status writes bypass it
- Tower controller uses adapter pattern — swap implementations via TOWER_CONTROLLER_TYPE env var
- Wiser integration has automatic 3-level fallback — API > file share > PDF
- Tablet kiosk is a public route (/tablet/:station) — no JWT required, access controlled by internal network
- All Redis channels follow pattern quality:<event_type>:<schema> for per-tenant isolation
