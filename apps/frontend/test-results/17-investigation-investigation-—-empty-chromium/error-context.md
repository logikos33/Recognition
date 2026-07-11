# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: 17-investigation.spec.ts >> investigation — empty
- Location: src/test/e2e/visual-audit/17-investigation.spec.ts:161:1

# Error details

```
Test timeout of 90000ms exceeded.
```

```
Error: locator.waitFor: Test timeout of 90000ms exceeded.
Call log:
  - waiting for getByText('Nenhum evento encontrado para os filtros aplicados') to be visible

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - generic [ref=e3]:
    - generic [ref=e4]:
      - banner [ref=e5]:
        - generic [ref=e6]:
          - button "Abrir menu lateral" [ref=e7] [cursor=pointer]:
            - img [ref=e8]
          - link "🦺 EPI" [ref=e9] [cursor=pointer]:
            - /url: /modules
            - generic [ref=e10]: 🦺
            - generic [ref=e11]: EPI
        - generic [ref=e12]:
          - button "Notificações" [ref=e14] [cursor=pointer]:
            - img [ref=e15]
          - generic [ref=e18]:
            - generic [ref=e19]:
              - img [ref=e20]
              - text: Pro
            - switch "Alternar tema" [ref=e22] [cursor=pointer]
          - generic [ref=e24]:
            - generic [ref=e25]: Auditor Visual
            - generic [ref=e26]: superadmin
          - button "Sair" [ref=e27] [cursor=pointer]
      - navigation "Menu lateral" [ref=e28]:
        - generic [ref=e29]:
          - generic [ref=e30]: 🦺 Módulos
          - button "Fechar menu" [ref=e31] [cursor=pointer]:
            - img [ref=e32]
        - generic [ref=e35]:
          - link "Dashboard" [ref=e36] [cursor=pointer]:
            - /url: /epi/dashboard
            - img [ref=e37]
            - text: Dashboard
          - link "Cameras" [ref=e42] [cursor=pointer]:
            - /url: /epi/cameras
            - img [ref=e43]
            - text: Cameras
          - link "Alertas" [ref=e46] [cursor=pointer]:
            - /url: /epi/alerts
            - img [ref=e47]
            - text: Alertas
          - link "Treinamento" [ref=e49] [cursor=pointer]:
            - /url: /epi/training
            - img [ref=e50]
            - text: Treinamento
          - link "Relatórios" [ref=e58] [cursor=pointer]:
            - /url: /epi/reports
            - img [ref=e59]
            - text: Relatórios
          - link "Investigação" [ref=e62] [cursor=pointer]:
            - /url: /epi/investigation
            - img [ref=e63]
            - text: Investigação
        - generic [ref=e67]:
          - link "Painel Admin" [ref=e68] [cursor=pointer]:
            - /url: /admin
            - img [ref=e69]
            - text: Painel Admin
          - button "Trocar Módulo" [ref=e72] [cursor=pointer]:
            - img [ref=e73]
            - text: Trocar Módulo
          - button "Configurações" [ref=e76] [cursor=pointer]:
            - img [ref=e77]
            - text: Configurações
          - button "Sair" [ref=e80] [cursor=pointer]:
            - img [ref=e81]
            - text: Sair
        - generic [ref=e84]:
          - generic [ref=e85]: v2.0.0
          - generic [ref=e86]: Railway
      - main [ref=e88]:
        - generic [ref=e89]:
          - generic [ref=e91]:
            - heading "Investigação de Eventos" [level=1] [ref=e92]
            - paragraph [ref=e93]: Busque e analise eventos de todos os módulos ativos
          - generic [ref=e94]:
            - heading "Filtros" [level=2] [ref=e97]
            - generic [ref=e98]:
              - generic [ref=e99]:
                - generic [ref=e101]:
                  - text: Classe de detecção
                  - 'img "Ajuda: Classe de detecção" [ref=e102]'
                - generic [ref=e105]:
                  - button "no_helmet" [ref=e106] [cursor=pointer]
                  - button "helmet" [ref=e107] [cursor=pointer]
                  - button "no_vest" [ref=e108] [cursor=pointer]
                  - button "vest" [ref=e109] [cursor=pointer]
                  - button "no_gloves" [ref=e110] [cursor=pointer]
                  - button "gloves" [ref=e111] [cursor=pointer]
                  - button "no_glasses" [ref=e112] [cursor=pointer]
                  - button "glasses" [ref=e113] [cursor=pointer]
                  - button "plate" [ref=e114] [cursor=pointer]
                  - button "truck" [ref=e115] [cursor=pointer]
                  - button "fuel_nozzle" [ref=e116] [cursor=pointer]
              - generic [ref=e117]:
                - generic [ref=e118]:
                  - generic [ref=e119]:
                    - text: Módulo
                    - 'img "Ajuda: Módulo" [ref=e120]'
                  - combobox "Módulo" [ref=e123]:
                    - option "Todos" [selected]
                - generic [ref=e124]:
                  - generic [ref=e125]:
                    - text: Câmeras
                    - 'img "Ajuda: Câmeras" [ref=e126]'
                  - button "Todas as câmeras" [ref=e129] [cursor=pointer]:
                    - text: Todas as câmeras
                    - img [ref=e130]
                - generic [ref=e132]:
                  - generic [ref=e133]:
                    - text: De
                    - 'img "Ajuda: De" [ref=e134]'
                  - textbox "Data inicial" [ref=e137]: 2026-06-30T09:42
                - generic [ref=e138]:
                  - generic [ref=e139]:
                    - text: Até
                    - 'img "Ajuda: Até" [ref=e140]'
                  - textbox "Data final" [ref=e143]: 2026-07-07T09:42
                - generic [ref=e144]:
                  - generic [ref=e145]:
                    - text: Confiança mín. (%)
                    - 'img "Ajuda: Confiança mín. (%)" [ref=e146]'
                  - spinbutton "Confiança mínima em porcentagem" [ref=e149]
                - generic [ref=e150]:
                  - generic [ref=e151]:
                    - text: Agrupamento
                    - 'img "Ajuda: Agrupamento" [ref=e152]'
                  - combobox "Agrupamento do gráfico" [ref=e155]:
                    - option "Por hora" [selected]
                    - option "Por dia"
                    - option "Por semana"
          - generic [ref=e156]:
            - generic [ref=e157]:
              - heading "Volume de eventos" [level=2] [ref=e159]
              - generic [ref=e161]: 0 períodos
            - generic [ref=e163]: Nenhum dado para o período selecionado
          - generic [ref=e164]:
            - heading "Eventos" [level=2] [ref=e167]
            - status [ref=e169]:
              - img [ref=e171]
              - paragraph [ref=e174]: Nenhum evento encontrado
              - paragraph [ref=e175]: Ajuste os filtros ou amplie o período de busca.
      - button "Abrir dashboard de observability" [ref=e176] [cursor=pointer]:
        - generic [ref=e177]: Banco de dados
        - generic [ref=e180]: Redis
        - generic [ref=e183]: câmeras ativas
    - button "Abrir chat" [ref=e185] [cursor=pointer]:
      - img [ref=e186]
  - generic "Notificações"
```

# Test source

```ts
  69  |     violations: ['no_gloves', 'no_glasses'],
  70  |     evidence_key: 'frames/ev-003.jpg',
  71  |     created_at: '2026-07-06T07:31:44Z',
  72  |     frame_url: FRAME_URL('ev-003'),
  73  |   },
  74  |   {
  75  |     id: 'ev-004',
  76  |     camera_id: 'cam-01',
  77  |     module_code: 'epi',
  78  |     confidence: 0.95,
  79  |     violations: ['helmet', 'vest'],
  80  |     evidence_key: null,
  81  |     created_at: '2026-07-06T06:58:02Z',
  82  |     frame_url: null, // sem frame → placeholder "sem frame"
  83  |   },
  84  |   {
  85  |     id: 'ev-005',
  86  |     camera_id: 'cam-04',
  87  |     module_code: 'epi',
  88  |     confidence: 0.64,
  89  |     violations: ['no_helmet'],
  90  |     evidence_key: 'frames/ev-005.jpg',
  91  |     created_at: '2026-07-05T17:20:38Z',
  92  |     frame_url: FRAME_URL('ev-005'),
  93  |   },
  94  |   {
  95  |     id: 'ev-006',
  96  |     camera_id: 'cam-05',
  97  |     module_code: 'fueling',
  98  |     confidence: 0.71,
  99  |     violations: ['truck', 'plate'],
  100 |     evidence_key: 'frames/ev-006.jpg',
  101 |     created_at: '2026-07-05T16:05:11Z',
  102 |     frame_url: FRAME_URL('ev-006'),
  103 |   },
  104 | ]
  105 | 
  106 | const SEARCH_RICH = { events: EVENTS, total: 47, page: 1, per_page: 20, pages: 3 }
  107 | 
  108 | const TIMELINE_RICH = {
  109 |   bucket_size: 'hour',
  110 |   buckets: [
  111 |     { bucket: '2026-07-06T00:00:00Z', count: 2 },
  112 |     { bucket: '2026-07-06T01:00:00Z', count: 1 },
  113 |     { bucket: '2026-07-06T02:00:00Z', count: 0 },
  114 |     { bucket: '2026-07-06T03:00:00Z', count: 3 },
  115 |     { bucket: '2026-07-06T04:00:00Z', count: 5 },
  116 |     { bucket: '2026-07-06T05:00:00Z', count: 4 },
  117 |     { bucket: '2026-07-06T06:00:00Z', count: 9 },
  118 |     { bucket: '2026-07-06T07:00:00Z', count: 12 },
  119 |     { bucket: '2026-07-06T08:00:00Z', count: 7 },
  120 |     { bucket: '2026-07-06T09:00:00Z', count: 3 },
  121 |     { bucket: '2026-07-06T10:00:00Z', count: 1 },
  122 |     { bucket: '2026-07-06T11:00:00Z', count: 0 },
  123 |   ],
  124 | }
  125 | 
  126 | /** Envelope { success, data } exigido pela página (ver bug WS4 no cabeçalho). */
  127 | const invRaw = (search: unknown, timeline: unknown) => ({
  128 |   '**/api/v1/events/search**': { status: 200, body: { success: true, data: search } },
  129 |   '**/api/v1/events/timeline**': { status: 200, body: { success: true, data: timeline } },
  130 |   '**/cdn.recognition.dev/**': { status: 200, body: FRAME_SVG, contentType: 'image/svg+xml' },
  131 | })
  132 | 
  133 | async function gotoInvRich(page: import('@playwright/test').Page) {
  134 |   // O shell tem overflow:hidden — fullPage não alcança abaixo da dobra.
  135 |   // Viewport alto revela a lista de eventos (thumbnails) + paginação.
  136 |   await page.setViewportSize({ width: 1440, height: 1900 })
  137 |   await setupApp(page, { raw: invRaw(SEARCH_RICH, TIMELINE_RICH) })
  138 |   await gotoAudit(page, ROUTE_INV)
  139 |   await page.getByText('Investigação de Eventos').waitFor()
  140 |   await page.getByText('92% confiança').waitFor()
  141 |   await settle(page)
  142 | }
  143 | 
  144 | /* ── Investigação — estados base ────────────────────────────────── */
  145 | 
  146 | test('investigation — default (rico, filtros + timeline + thumbnails + paginação)', async ({ page }) => {
  147 |   await gotoInvRich(page)
  148 |   await shootBothThemes(page, SLUG_INV, 'default', true)
  149 | })
  150 | 
  151 | test('investigation — filters-active (chips selecionados + confiança mín.)', async ({ page }) => {
  152 |   await gotoInvRich(page)
  153 |   await page.getByRole('button', { name: 'no_helmet', exact: true }).click()
  154 |   await page.getByRole('button', { name: 'no_vest', exact: true }).click()
  155 |   await page.getByPlaceholder('0.0 – 1.0').fill('0.7')
  156 |   await page.getByText('Limpar filtros de classe').waitFor()
  157 |   await settle(page)
  158 |   await shootBothThemes(page, SLUG_INV, 'filters-active', true)
  159 | })
  160 | 
  161 | test('investigation — empty', async ({ page }) => {
  162 |   await setupApp(page, {
  163 |     raw: invRaw(
  164 |       { events: [], total: 0, page: 1, per_page: 20, pages: 1 },
  165 |       { buckets: [], bucket_size: 'hour' }
  166 |     ),
  167 |   })
  168 |   await gotoAudit(page, ROUTE_INV)
> 169 |   await page.getByText('Nenhum evento encontrado para os filtros aplicados').waitFor()
      |                                                                              ^ Error: locator.waitFor: Test timeout of 90000ms exceeded.
  170 |   await settle(page)
  171 |   await shootBothThemes(page, SLUG_INV, 'empty', true)
  172 | })
  173 | 
  174 | test('investigation — empty com envelope padrão da API (bug WS4)', async ({ page }) => {
  175 |   // Catch-all do harness devolve o envelope PADRÃO {status:'success', data:{}}.
  176 |   // A página checa `res.success` → cai no branch de erro mesmo com API 200.
  177 |   await setupApp(page)
  178 |   await gotoAudit(page, ROUTE_INV)
  179 |   await page.getByText('Erro ao buscar eventos').waitFor()
  180 |   await settle(page)
  181 |   await shootBothThemes(page, SLUG_INV, 'empty-ws4-envelope', true)
  182 | })
  183 | 
  184 | test('investigation — loading (stall)', async ({ page }) => {
  185 |   await setupApp(page, {
  186 |     stall: ['**/api/v1/events/search**', '**/api/v1/events/timeline**'],
  187 |   })
  188 |   await gotoAudit(page, ROUTE_INV)
  189 |   await page.getByText('Investigação de Eventos').waitFor()
  190 |   await page.getByText('Buscando…').waitFor()
  191 |   // settle() esperaria networkidle que nunca chega (requests penduradas)
  192 |   await page.waitForTimeout(1500)
  193 |   await shootBothThemes(page, SLUG_INV, 'loading', true)
  194 | })
  195 | 
  196 | test('investigation — error (500)', async ({ page }) => {
  197 |   await setupApp(page, {
  198 |     raw: {
  199 |       '**/api/v1/events/search**': {
  200 |         status: 500,
  201 |         body: { status: 'error', error: 'Erro interno do servidor' },
  202 |       },
  203 |       '**/api/v1/events/timeline**': {
  204 |         status: 200,
  205 |         body: { success: true, data: { buckets: [], bucket_size: 'hour' } },
  206 |       },
  207 |     },
  208 |   })
  209 |   await gotoAudit(page, ROUTE_INV)
  210 |   await page.getByText('Não foi possível conectar à API').waitFor()
  211 |   await page.waitForTimeout(1200) // deixa o toast de erro aparecer
  212 |   await shootBothThemes(page, SLUG_INV, 'error', true)
  213 | })
  214 | 
  215 | /* ── Investigação — modal de frame ampliado ─────────────────────── */
  216 | 
  217 | test('investigation — modal frame ampliado', async ({ page }) => {
  218 |   await gotoInvRich(page)
  219 |   // Clique na linha do ev-001 (92%) abre o modal de frame ampliado
  220 |   await page.getByText('92% confiança').click()
  221 |   await page.getByRole('button', { name: '✕' }).waitFor()
  222 |   await settle(page, 500)
  223 |   await shootBothThemes(page, SLUG_INV, 'modal-frame')
  224 | })
  225 | 
  226 | /* ── Investigação — hovers (só tema dark) ───────────────────────── */
  227 | 
  228 | test('investigation — hovers (dark)', async ({ page }) => {
  229 |   await gotoInvRich(page)
  230 | 
  231 |   await page.getByRole('button', { name: 'no_helmet', exact: true }).hover()
  232 |   await page.waitForTimeout(300)
  233 |   await shoot(page, SLUG_INV, 'hover-class-chip')
  234 | 
  235 |   await page.getByText('92% confiança').hover()
  236 |   await page.waitForTimeout(300)
  237 |   await shoot(page, SLUG_INV, 'hover-event-row')
  238 | })
  239 | 
  240 | /* ── Fixtures pt-BR — Contagem ──────────────────────────────────── */
  241 | 
  242 | const CAMERAS_CNT = [
  243 |   { id: 'cam-01', name: 'Câmera Pátio Norte', is_streaming: true },
  244 |   { id: 'cam-02', name: 'Câmera Doca 02', is_streaming: true },
  245 |   { id: 'cam-03', name: 'Câmera Portaria Principal', is_streaming: false },
  246 |   { id: 'cam-04', name: 'Câmera Almoxarifado', is_streaming: false },
  247 |   { id: 'cam-05', name: 'Câmera Linha de Produção A', is_streaming: true },
  248 | ]
  249 | 
  250 | const SESSIONS_CNT = [
  251 |   {
  252 |     id: 'sess-8f2c41aa-0001',
  253 |     camera_id: 'cam-02',
  254 |     module_code: 'epi',
  255 |     status: 'active',
  256 |     started_at: '2026-07-06T09:12:00Z',
  257 |     truck_plate: 'RVB4D23',
  258 |     direction: 'load',
  259 |     acceptance_status: 'pending',
  260 |   },
  261 |   {
  262 |     id: 'sess-3b9d02fe-0002',
  263 |     camera_id: 'cam-01',
  264 |     module_code: 'epi',
  265 |     status: 'active',
  266 |     started_at: '2026-07-06T08:47:00Z',
  267 |     truck_plate: 'BRA2E19',
  268 |     direction: 'unload',
  269 |     acceptance_status: 'accepted',
```