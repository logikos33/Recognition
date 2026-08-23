# Consumidores — gerado por `tools/frontend_api_calls.py`

- Chamadas do front extraídas: **309** (casadas: 300, sem regra: 9, dinâmicas: 0)
- Sockets do front: 7 · hits em edge/worker/scripts/tests: 2029
- Rótulo preliminar por regra: {'BACKEND-ONLY': 38, 'FRONT-ATUAL': 248, 'SEM-CONSUMIDOR': 135}
- Env vars do front: {'VITE_API_URL': 22, 'VITE_WS_URL': 5}

## Chamadas do front SEM regra correspondente (404/405 no matcher)

| Arquivo:linha | Método | Path resolvido | Status | Raw |
|---|---|---|---|---|
| `apps/frontend/src/hooks/useScenario.ts:25` | GET | `/api/cameras/<param>/scenario` | 404 | ``/cameras/${cameraId}/scenario`` |
| `apps/frontend/src/modules/quality/pages/QualityConfigPage.tsx:93` | PATCH | `/api/v1/quality/gate/config` | 405 | `'/v1/quality/gate/config'` |
| `apps/frontend/src/modules/quality/pages/QualityConfigPage.tsx:121` | PATCH | `/api/v1/quality/gate/stations/<param>` | 405 | ``/v1/quality/gate/stations/${editStationCode}`` |
| `apps/frontend/src/modules/quality/pages/QualityPiecesPage.tsx:378` | GET | `/api/v1/quality/gate/photos/<param>` | 404 | ``${API_BASE}/api/v1/quality/gate/photos/${encodeURIComponent(detail.photo_qualit` |
| `apps/frontend/src/modules/quality/pages/QualityReportsPage.tsx:99` | POST | `/api/v1/quality/gate/pieces/<param>/export-wiser` | 405 | ``/v1/quality/gate/pieces/${pieceId}/export-wiser`` |
| `apps/frontend/src/modules/quality/pages/QualityReportsPage.tsx:126` | POST | `/api/v1/quality/gate/export-wiser/batch` | 405 | `'/v1/quality/gate/export-wiser/batch'` |
| `apps/frontend/src/modules/quality/pages/QualityReworkPage.tsx:428` | GET | `/api/v1/quality/gate/photos/<param>` | 404 | ``${API_BASE}/api/v1/quality/gate/photos/${encodeURIComponent(modalRework.photo_b` |
| `apps/frontend/src/modules/quality/pages/QualityReworkPage.tsx:452` | GET | `/api/v1/quality/gate/photos/<param>` | 404 | ``${API_BASE}/api/v1/quality/gate/photos/${encodeURIComponent(modalRework.photo_a` |
| `apps/frontend/src/modules/quality/tablet/TabletResultNOK.tsx:61` | GET | `/api/v1/quality/gate/photos/<param>` | 404 | ``${API_BASE}/v1/quality/gate/photos/${encodeURIComponent(result.photo_path)}`` |

## Chamadas dinâmicas (não resolvidas)

| Arquivo:linha | Via | Trecho |
|---|---|---|

## Sockets (cliente)

| Arquivo:linha | Namespace | on | emit |
|---|---|---|---|
| `apps/frontend/src/hooks/useEdgeTelemetrySocket.ts:44` | `/monitor` | connect, disconnect, edge_telemetry | — |
| `apps/frontend/src/hooks/useMonitoringSocket.ts:51` | `/monitor` | alert, connect, detection, disconnect | subscribe_camera, unsubscribe_camera |
| `apps/frontend/src/hooks/useOperationLiveStatus.ts:37` | `/monitor` | connect, disconnect, operation:reloaded, operation:status_changed | — |
| `apps/frontend/src/hooks/useTrainingSocket.ts:73` | `/training` | connect, disconnect, training_progress | — |
| `apps/frontend/src/modules/admin/hooks/useAdminWebSocket.ts:23` | `/admin` | connect, disconnect | — |
| `apps/frontend/src/modules/quality/hooks/useQualityWebSocket.ts:36` | `/quality` | connect, disconnect, quality_cep_alert, quality_inspection | — |
| `apps/frontend/src/modules/quality/tablet/useTabletWebSocket.ts:46` | `/quality` | connect, connect_error, disconnect, quality_gate_result, quality_piece_identified, quality_station_state | — |
