# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: 17-investigation.spec.ts >> investigation — filters-active (chips selecionados + confiança mín.)
- Location: src/test/e2e/visual-audit/17-investigation.spec.ts:151:1

# Error details

```
Test timeout of 90000ms exceeded.
```

```
Error: locator.waitFor: Test timeout of 90000ms exceeded.
Call log:
  - waiting for getByText('Investigação de Eventos') to be visible

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
          - heading "Erro inesperado" [level=3] [ref=e90]
          - paragraph [ref=e91]: Cannot read properties of undefined (reading 'startsWith')
          - button "Tentar novamente" [ref=e92] [cursor=pointer]
      - button "Abrir dashboard de observability" [ref=e93] [cursor=pointer]:
        - generic [ref=e94]: Banco de dados
        - generic [ref=e97]: Redis
        - generic [ref=e100]: câmeras ativas
    - button "Abrir chat" [ref=e102] [cursor=pointer]:
      - img [ref=e103]
  - generic "Notificações"
```

# Test source

```ts
  39  | </svg>`
  40  | 
  41  | const FRAME_URL = (id: string) => `https://cdn.recognition.dev/frames/${id}.jpg`
  42  | 
  43  | const EVENTS = [
  44  |   {
  45  |     id: 'ev-001',
  46  |     camera_id: 'cam-01',
  47  |     module_code: 'epi',
  48  |     confidence: 0.92,
  49  |     violations: ['no_helmet', 'vest'],
  50  |     evidence_key: 'frames/ev-001.jpg',
  51  |     created_at: '2026-07-06T08:14:23Z',
  52  |     frame_url: FRAME_URL('ev-001'),
  53  |   },
  54  |   {
  55  |     id: 'ev-002',
  56  |     camera_id: 'cam-02',
  57  |     module_code: 'epi',
  58  |     confidence: 0.87,
  59  |     violations: ['no_vest'],
  60  |     evidence_key: 'frames/ev-002.jpg',
  61  |     created_at: '2026-07-06T07:52:10Z',
  62  |     frame_url: FRAME_URL('ev-002'),
  63  |   },
  64  |   {
  65  |     id: 'ev-003',
  66  |     camera_id: 'cam-03',
  67  |     module_code: 'epi',
  68  |     confidence: 0.78,
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
> 139 |   await page.getByText('Investigação de Eventos').waitFor()
      |                                                   ^ Error: locator.waitFor: Test timeout of 90000ms exceeded.
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
  169 |   await page.getByText('Nenhum evento encontrado para os filtros aplicados').waitFor()
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
```