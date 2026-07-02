# Inventário de Funcionalidades Não Produtizadas

> Auditoria: 2026-07-01 | Branch: chore/audit-unproductized
>
> Escopo: `services/api/app/` (backend) + `apps/frontend/src/components/` (frontend)
> Metodologia: grep de imports, leitura de AppRoutes.tsx, CollapsibleSidebar.tsx, routes.py de cada blueprint.

---

## Tabela Principal

| # | Componente / Serviço | Existe no Código | Tem UI Completa | Gap | Esforço (h) |
|---|---|:---:|:---:|---|:---:|
| 1 | `ScenarioEditor.tsx` + `DrawingCanvas.tsx` | Sim | Sim | Rota `/epi/cameras/:id/scenario` existe mas **nenhum botão no `CamerasPage` aponta para ela**. Acessível apenas digitando a URL. | 3 |
| 2 | `RoiDrawer.tsx` | Sim | Sim | **Zero imports** em qualquer página/modal. Mencionado apenas num comentário em `PositionForm.tsx`. Precisa ser conectado nos modals de criação/edição de operação. | 8 |
| 3 | `VerificationQueuePage` (`/epi/verification`) | Sim | Sim | Rota registrada em `AppRoutes.tsx`. **Nenhum item na sidebar (`EPI_NAV_BASE`) aponta para ela.** Backend completo (3 endpoints). | 1 |
| 4 | `CountingPage` (`/epi/counting`) | Sim | Sim | Rota registrada. `TopBar.tsx` tem o breadcrumb mas **não há link de navegação**. Sidebar sem entrada. Backend counting completo. | 1 |
| 5 | `FuelingValidationPage` (`/fueling/validation`) | Sim | Sim | Rota registrada. `FuelingPage` e `FUELING_NAV` **não têm link** para `/fueling/validation`. Backend: `countingService.getValidationReport` existe. | 1 |
| 6 | `feedback/routes.py` + `DetectionFeedbackRepository` | Sim | Não | Backend com 3 endpoints (POST, GET, GET `/summary`). **Frontend sem nenhum componente ou página de feedback**. | 12 |
| 7 | `LiveVideoWithOperations.tsx` | Sim | Sim | **SURFACED** — usado por `TrainingModeLayout` → `EpiOperationsPage` → botão "Operações" no `CamerasPage`. Nenhum gap. | — |
| 8 | `countingService.ts` | Sim | Parcial | `getCameraModels`/`setCameraModel` usados em `CameraModelAssignment` (surfaced). `updateSession`/`getValidationReport` usados em `CountingPage`/`FuelingValidationPage` — ambas sem link de nav (ver #4 e #5). | — |
| 9 | `LivenessAlertRepository` | Sim | Não | `get_open_gap_alert`, `create_gap_alert`, `acknowledge_gap_alerts` — uso interno no worker. **Sem endpoint HTTP nem UI de admin** para ver/ack alertas de gap de liveness. | 8 |
| 10 | `OperationRepository.update_live_value` / `insert_result` | Sim | N/A | Chamadas internas do worker (inference). Não precisam de endpoint HTTP. Nenhum gap de produto. | — |

---

## Detalhes por Item

### 1. ScenarioEditor + DrawingCanvas — rota sem link de entrada

**Localização:**
- `apps/frontend/src/components/scenario/ScenarioEditor.tsx`
- `apps/frontend/src/components/scenario/DrawingCanvas.tsx`
- `apps/frontend/src/pages/epi/EpiScenarioEditorPage.tsx` (rota `/epi/cameras/:cameraId/scenario`)

**Situação:** A página está 100% implementada. O editor visual permite escolher tipo de operação, desenhar geometria (zona/linha/ponto), nomear e salvar via `POST /api/v1/cameras/:id/operations`. O backend tem `GET /api/v1/cameras/:id/scenario` (leitura) e o CRUD de operações para escrita.

**Gap:** `CamerasPage.tsx` (linha 330) navega para `/epi/cameras/${id}/operations` ao clicar "Operações", mas **não tem botão "Cenário"** para `/epi/cameras/${id}/scenario`.

**Fix:** Adicionar `<Button onClick={() => navigate(`/epi/cameras/${selected.id}/scenario`)}>Cenário</Button>` próximo ao botão de Operações no `CamerasPage.tsx`.

---

### 2. RoiDrawer — componente órfão

**Localização:** `apps/frontend/src/components/training/canvas/RoiDrawer.tsx`

**Situação:** Canvas SVG interativo para desenho de polígonos ROI com coordenadas normalizadas [0,1]. Interface completa com drag de pontos, hover, readOnly mode. Segue o padrão `pointerEvents:'none'` do projeto.

**Gap:** Nenhum arquivo importa `RoiDrawer` (grep de `import.*RoiDrawer` retorna vazio). `PositionForm.tsx` menciona RoiDrawer num comentário dizendo "é passado como prop" — mas o form não o importa.

**Fix:** Integrar `RoiDrawer` nos modais `OperationCreateModal.tsx` e `OperationEditModal.tsx` para operações do tipo `position` (que usam `PositionForm`). Passar a frame atual do vídeo como `backgroundSrc`.

---

### 3. VerificationQueuePage — sidebar sem entrada

**Localização:** `apps/frontend/src/pages/VerificationQueuePage.tsx` (rota `/epi/verification`)

**Situação:** Página funcional para revisão humana de alertas. Backend: `GET /api/verification/queue`, `GET /api/verification/queue/count`, `POST /api/verification/<id>/review`.

**Gap:** Nenhum item em `EPI_NAV_BASE` em `CollapsibleSidebar.tsx` aponta para `/epi/verification`. A `TopBar.tsx` tem o título mapeado (`'/epi/verification': 'Verificação'`) mas sem nav.

**Fix:** Adicionar `{ to: '/epi/verification', label: 'Verificação', icon: ShieldCheck, module: null }` em `EPI_NAV_BASE`.

---

### 4. CountingPage — sidebar sem entrada

**Localização:** `apps/frontend/src/pages/CountingPage.tsx` (rota `/epi/counting`)

**Situação:** Página de sessões de contagem com start/stop, stats por classe, chips de placa/direção/aceite. Backend counting routes completos (6 endpoints). `TopBar.tsx` tem `'/epi/counting': 'Contagem'` como breadcrumb.

**Gap:** Sidebar (`EPI_NAV_BASE`) não tem entrada para `/epi/counting`. Usuário não tem como acessar a não ser digitando a URL.

**Fix:** Adicionar `{ to: '/epi/counting', label: 'Contagem', icon: Hash, module: null }` em `EPI_NAV_BASE` (condicional ao módulo `counting` estar habilitado).

---

### 5. FuelingValidationPage — link ausente no módulo fueling

**Localização:** `apps/frontend/src/pages/fueling/FuelingValidationPage.tsx` (rota `/fueling/validation`)

**Situação:** Página de validação/aceite de sessões de contagem (CD-07). Usa `countingService.getValidationReport` para relatório `system vs manual`. Backend: `GET /counting/sessions/validation-report`.

**Gap:** `FUELING_NAV` em `CollapsibleSidebar.tsx` tem dashboard/baias/eventos mas **não tem link** para `/fueling/validation`. `FuelingPage` também não linka.

**Fix:** Adicionar `{ to: '/fueling/validation', label: 'Validação', icon: ClipboardCheck }` em `FUELING_NAV`.

---

### 6. Detection Feedback — backend completo, zero frontend

**Backend:** `services/api/app/api/v1/feedback/routes.py` — 3 endpoints (`POST /`, `GET /`, `GET /summary`). `DetectionFeedbackRepository` com `create` e `list_by_module`.

**Frontend:** Nenhum componente ou página de feedback existe (`grep -r "feedback" apps/frontend/src` retorna vazio exceto tipos).

**Fix:** Criar `FeedbackPage` com lista de detecções e botões approve/reject. Esforço ~12h (página + componentes de card + integração com `AlertsPanel`).

---

### 7. Liveness Gap Alerts — uso interno sem UI de admin

**Backend:** `LivenessAlertRepository` com `get_open_gap_alert`, `create_gap_alert`, `acknowledge_gap_alerts`, `find_camera_for_tenant` — chamados pelo worker/scheduler para detectar janelas sem detecção.

**Gap:** Sem endpoint HTTP para listar alertas abertos ou fazer acknowledge. Nenhuma UI de admin para operar esses alertas.

**Fix:** Criar `GET /api/streams/liveness-alerts` e `POST /api/streams/liveness-alerts/<id>/acknowledge`. UI: painel de saúde ou seção em `EpiSitesHealthPage`. Esforço ~8h.

---

## Lista Prioritária — O Que Está Quase Pronto

Ordenado por custo/benefício (menor esforço, maior visibilidade):

1. **[1h] CountingPage — adicionar sidebar link** (#4): 1 linha em `CollapsibleSidebar.tsx`. Módulo inteiro já funcional.
2. **[1h] VerificationQueuePage — adicionar sidebar link** (#3): 1 linha em `CollapsibleSidebar.tsx`. Backend completo.
3. **[1h] FuelingValidationPage — adicionar link no FUELING_NAV** (#5): 1 linha. Página já funcionando.
4. **[3h] ScenarioEditor — botão de entrada no CamerasPage** (#1): 1 botão em `CamerasPage.tsx`. Editor 100% implementado, só falta a porta de entrada.
5. **[8h] RoiDrawer — conectar ao OperationCreateModal/EditModal** (#2): Componente pronto, precisa ser integrado como input de ROI nos forms de operação tipo `position`.
6. **[8h] Liveness Gap Alerts — endpoint de ack + painel** (#7): Repository pronto, criar rotas + seção em SitesHealth.
7. **[12h] Feedback UI** (#6): Backend 100% funcional, criar a página de revisão no frontend.

---

## Análise dos Testes Deselecionados no CI

11 testes deselecionados no `AUTORUN.md`. Avaliação de re-habilitação:

| Teste | Causa Provável | Re-habilitável Hoje? |
|---|---|:---:|
| `test_invalid_scheme` | `match="Scheme"` pode não bater com mensagem atual do `RTSPUrlValidator` | Talvez — verificar texto da exceção |
| `test_upload_file_calls_upload_file` | ExtraArgs no mock boto3 não bate com assinatura atual | Talvez — atualizar mock |
| `test_delete_camera_success` | Impl. atual usa `str(camera["tenant_id"]) != str(user_id)` — lógica bate com teste | **Provavelmente sim** |
| `test_delete_camera_wrong_user` | Idem — lógica de AuthorizationError bate com teste | **Provavelmente sim** |
| `test_delete_camera_admin_override` | Idem — `is_admin=True` bypass bate com impl. | **Provavelmente sim** |
| `test_build_rtsp_url_with_override` | Teste usa URL privada válida `192.168.1.1` — `validate()` não rejeita IPs privados | **Provavelmente sim** |
| `test_build_rtsp_url_generated` | Patch de `RTSPUrlValidator.validate` com `side_effect=lambda url: url` — impl. ignora retorno de `validate()`, só usa efeito colateral | **Provavelmente sim** |
| `test_build_rtsp_url_wrong_user_raises` | `str(owner) != str(other)` → `AuthorizationError` — lógica bate | **Provavelmente sim** |
| `test_create_camera` (repositories) | Mock `fetchone` pode não bater com SQL atual do `CameraRepository.create` | Incerto |
| `test_get_for_camera_returns_video_for_superadmin` | Assinatura de `DemoVideoService` alterada | Incerto |
| `test_export_pdf_creates_file` | Dependência de biblioteca PDF ou path de arquivo | Incerto |

**Recomendação:** Criar `fix/reenable-camera-service-tests` e rodar os 6 testes `test_delete_camera_*` + `test_build_rtsp_url_*` localmente. Se todos passarem, remover os `--deselect` correspondentes do `AUTORUN.md` e do CI.

---

## Endpoints Backend vs Repositories — Mapa de Cobertura

| Blueprint | Repository | Métodos no Repo | Endpoints HTTP | Status |
|---|---|:---:|:---:|:---:|
| `counting/routes.py` | `CountingRepository` | 8 | 6 | Completo |
| `feedback/routes.py` | `DetectionFeedbackRepository` | 2 | 3 | Backend OK, UI ausente |
| `scenarios/routes.py` | `OperationRepository` | 10 | GET-only cenário | Sem save de cenário (save = ops CRUD) |
| `streams/routes.py` | `LivenessAlertRepository` | 4 | 1 (status only) | Gap: ack/list de gap alerts |
| `notifications/routes.py` | `NotificationRepository` | 6 | 4 | Completo (sem `log_delivery` exposto — correto) |
| `models/routes.py` | `ModelRolloutRepository` | 3 | — | Uso interno inference |

---

*Gerado por audit workflow — tarefa 1d do MUTIRÃO. Para próximos passos ver Lista Prioritária acima.*
