# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: 14-monitoring.spec.ts >> stream-health — empty (sem workers, sem câmeras)
- Location: src/test/e2e/visual-audit/14-monitoring.spec.ts:308:1

# Error details

```
TimeoutError: locator.waitFor: Timeout 30000ms exceeded.
Call log:
  - waiting for getByText('Stream Health') to be visible

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
          - link "🛡️ Painel Admin" [ref=e9] [cursor=pointer]:
            - /url: /modules
            - generic [ref=e10]: 🛡️
            - generic [ref=e11]: Painel Admin
          - generic [ref=e12]:
            - generic [ref=e13]: /
            - generic [ref=e14]: Observability
        - generic [ref=e15]:
          - button "Notificações" [ref=e17] [cursor=pointer]:
            - img [ref=e18]
          - generic [ref=e21]:
            - generic [ref=e22]:
              - img [ref=e23]
              - text: Pro
            - switch "Alternar tema" [ref=e25] [cursor=pointer]
          - generic [ref=e27]:
            - generic [ref=e28]: Auditor Visual
            - generic [ref=e29]: superadmin
          - button "Sair" [ref=e30] [cursor=pointer]
      - navigation "Menu lateral" [ref=e31]:
        - generic [ref=e32]:
          - generic [ref=e33]: 🦺 Módulos
          - button "Fechar menu" [ref=e34] [cursor=pointer]:
            - img [ref=e35]
        - generic [ref=e38]:
          - link "Dashboard" [ref=e39] [cursor=pointer]:
            - /url: /epi/dashboard
            - img [ref=e40]
            - text: Dashboard
          - link "Cameras" [ref=e45] [cursor=pointer]:
            - /url: /epi/cameras
            - img [ref=e46]
            - text: Cameras
          - link "Alertas" [ref=e49] [cursor=pointer]:
            - /url: /epi/alerts
            - img [ref=e50]
            - text: Alertas
          - link "Treinamento" [ref=e52] [cursor=pointer]:
            - /url: /epi/training
            - img [ref=e53]
            - text: Treinamento
          - link "Relatórios" [ref=e61] [cursor=pointer]:
            - /url: /epi/reports
            - img [ref=e62]
            - text: Relatórios
          - link "Investigação" [ref=e65] [cursor=pointer]:
            - /url: /epi/investigation
            - img [ref=e66]
            - text: Investigação
        - generic [ref=e70]:
          - link "Painel Admin" [ref=e71] [cursor=pointer]:
            - /url: /admin
            - img [ref=e72]
            - text: Painel Admin
          - button "Trocar Módulo" [ref=e75] [cursor=pointer]:
            - img [ref=e76]
            - text: Trocar Módulo
          - button "Configurações" [ref=e79] [cursor=pointer]:
            - img [ref=e80]
            - text: Configurações
          - button "Sair" [ref=e83] [cursor=pointer]:
            - img [ref=e84]
            - text: Sair
        - generic [ref=e87]:
          - generic [ref=e88]: v2.0.0
          - generic [ref=e89]: Railway
      - main [ref=e91]:
        - generic [ref=e92]:
          - heading "Erro inesperado" [level=3] [ref=e93]
          - paragraph [ref=e94]: Cannot read properties of undefined (reading 'length')
          - button "Tentar novamente" [ref=e95] [cursor=pointer]
      - button "Abrir dashboard de observability" [ref=e96] [cursor=pointer]:
        - generic [ref=e97]: Banco de dados
        - generic [ref=e100]: Redis
        - generic [ref=e103]: câmeras ativas
    - button "Abrir chat" [ref=e105] [cursor=pointer]:
      - img [ref=e106]
  - generic "Notificações"
```

# Test source

```ts
  197 | })
  198 | 
  199 | test('epi-monitoring — tab-epi (filtro por módulo EPI)', async ({ page }) => {
  200 |   await setupApp(page, { fixtures: MON_FIXTURES })
  201 |   await openMonitoring(page)
  202 |   await page.getByRole('button', { name: 'EPI', exact: true }).first().click()
  203 |   await page.getByText('Câmera Almoxarifado').waitFor({ timeout: 15_000 })
  204 |   await settle(page, 500)
  205 |   await shootBothThemes(page, MON, 'tab-epi')
  206 | })
  207 | 
  208 | test('epi-monitoring — drawer-feed (detalhe da câmera, tab Feed)', async ({ page }) => {
  209 |   await setupApp(page, { fixtures: MON_FIXTURES })
  210 |   await openMonitoring(page)
  211 |   await openDrawer(page)
  212 |   await shootBothThemes(page, MON, 'drawer-feed')
  213 | })
  214 | 
  215 | test('epi-monitoring — drawer-tab-logs (Logs ao vivo, aguardando detecções)', async ({ page }) => {
  216 |   await setupApp(page, { fixtures: MON_FIXTURES })
  217 |   await openMonitoring(page)
  218 |   await openDrawer(page)
  219 |   await page.getByRole('button', { name: 'Logs ao vivo' }).click()
  220 |   await page.getByText('Aguardando detecções...').waitFor({ timeout: 10_000 })
  221 |   await page.waitForTimeout(400)
  222 |   await shootBothThemes(page, MON, 'drawer-tab-logs')
  223 | })
  224 | 
  225 | test('epi-monitoring — drawer-tab-info (metadados da câmera)', async ({ page }) => {
  226 |   await setupApp(page, { fixtures: MON_FIXTURES })
  227 |   await openMonitoring(page)
  228 |   await openDrawer(page)
  229 |   await page.getByRole('button', { name: 'Info', exact: true }).click()
  230 |   await page.getByText('Fabricante').waitFor({ timeout: 10_000 })
  231 |   await page.waitForTimeout(400)
  232 |   await shootBothThemes(page, MON, 'drawer-tab-info')
  233 | })
  234 | 
  235 | test('epi-monitoring — hover (card de câmera + toggle Overlay) [só dark]', async ({ page }) => {
  236 |   await setupApp(page, { fixtures: MON_FIXTURES })
  237 |   await openMonitoring(page)
  238 | 
  239 |   await page.getByText('Câmera Pátio Norte').hover()
  240 |   await page.waitForTimeout(300)
  241 |   await shoot(page, MON, 'dark-hover-camera-card')
  242 | 
  243 |   await page.getByRole('button', { name: 'Overlay' }).hover()
  244 |   await page.waitForTimeout(300)
  245 |   await shoot(page, MON, 'dark-hover-overlay-toggle')
  246 | })
  247 | 
  248 | /* ================================================================== */
  249 | /* PÁGINA 2 — /epi/health (StreamHealthPage)                           */
  250 | /* ================================================================== */
  251 | 
  252 | const SH = 'stream-health'
  253 | const SH_ROUTE = '/epi/health'
  254 | 
  255 | const WORKERS = [
  256 |   { worker_id: 'celery@worker-inference-01', status: 'online', active_tasks: 3 },
  257 |   { worker_id: 'celery@worker-training-01', status: 'online', active_tasks: 1 },
  258 |   { worker_id: 'celery@worker-extraction-01', status: 'online', active_tasks: 0 },
  259 |   { worker_id: 'celery@worker-quality-02', status: 'offline', active_tasks: 0 },
  260 | ]
  261 | 
  262 | // /health e /streams/status são lidos na RAIZ do envelope → mock via `raw`.
  263 | const SH_RAW_OK: Record<string, { status?: number; body?: unknown }> = {
  264 |   '**/api/health': {
  265 |     body: { status: 'healthy', checks: { database: true, redis: true } },
  266 |   },
  267 |   '**/api/streams/status': {
  268 |     body: { status: 'ok', workers: WORKERS },
  269 |   },
  270 | }
  271 | 
  272 | // Status de stream variado por câmera (lido em res.data → `fixtures`).
  273 | const SH_FIXTURES_OK: Record<string, unknown> = {
  274 |   '**/api/cameras': { cameras: CAMERAS },
  275 |   '**/api/cameras/cam-1/stream/status': {
  276 |     streaming: true, gateway_online: true, ttl_seconds: 112,
  277 |   },
  278 |   '**/api/cameras/cam-2/stream/status': {
  279 |     streaming: true, gateway_online: true, ttl_seconds: 87,
  280 |   },
  281 |   '**/api/cameras/cam-3/stream/status': {
  282 |     streaming: false, gateway_online: true,
  283 |   },
  284 |   '**/api/cameras/cam-4/stream/status': {
  285 |     streaming: true, gateway_online: false,
  286 |   },
  287 |   '**/api/cameras/cam-5/stream/status': {
  288 |     streaming: false, gateway_online: false,
  289 |   },
  290 |   '**/api/cameras/cam-6/stream/status': {
  291 |     streaming: true, gateway_online: true, ttl_seconds: 45,
  292 |   },
  293 | }
  294 | 
  295 | async function openStreamHealth(page: Page) {
  296 |   await gotoAudit(page, SH_ROUTE)
> 297 |   await page.getByText('Stream Health').waitFor({ timeout: 30_000 })
      |                                         ^ TimeoutError: locator.waitFor: Timeout 30000ms exceeded.
  298 |   await settle(page)
  299 | }
  300 | 
  301 | test('stream-health — default (sistema saudável, workers e câmeras)', async ({ page }) => {
  302 |   await setupApp(page, { fixtures: SH_FIXTURES_OK, raw: SH_RAW_OK })
  303 |   await openStreamHealth(page)
  304 |   await page.getByText('celery@worker-inference-01').waitFor({ timeout: 15_000 })
  305 |   await shootBothThemes(page, SH, 'default', true)
  306 | })
  307 | 
  308 | test('stream-health — empty (sem workers, sem câmeras)', async ({ page }) => {
  309 |   await setupApp(page, {
  310 |     fixtures: { '**/api/cameras': { cameras: [] } },
  311 |     raw: {
  312 |       '**/api/health': {
  313 |         body: { status: 'healthy', checks: { database: true, redis: true } },
  314 |       },
  315 |       '**/api/streams/status': { body: { status: 'ok', workers: [] } },
  316 |     },
  317 |   })
  318 |   await openStreamHealth(page)
  319 |   await page.getByText('Nenhum worker detectado.').waitFor({ timeout: 15_000 })
  320 |   await page.getByText('Nenhuma câmera cadastrada.').waitFor({ timeout: 15_000 })
  321 |   await shootBothThemes(page, SH, 'empty', true)
  322 | })
  323 | 
  324 | test('stream-health — loading (endpoints nunca respondem → spinner)', async ({ page }) => {
  325 |   await setupApp(page, {
  326 |     stall: ['**/api/health', '**/api/streams/status', '**/api/cameras'],
  327 |   })
  328 |   await gotoAudit(page, SH_ROUTE)
  329 |   // O api.ts aborta em 15s → screenshot antes disso, com o spinner na tela.
  330 |   await page.waitForTimeout(2500)
  331 |   await shootBothThemes(page, SH, 'loading')
  332 | })
  333 | 
  334 | test('stream-health — error (500 em tudo → chips vermelhos + listas vazias)', async ({ page }) => {
  335 |   await setupApp(page, {
  336 |     raw: {
  337 |       '**/api/health': { status: 500, body: { status: 'error', error: 'Serviço indisponível' } },
  338 |       '**/api/streams/status': { status: 500, body: { status: 'error', error: 'Serviço indisponível' } },
  339 |       '**/api/cameras': { status: 500, body: { status: 'error', error: 'Serviço indisponível' } },
  340 |       '**/api/cameras/*/stream/status': { status: 500, body: { status: 'error' } },
  341 |     },
  342 |   })
  343 |   await gotoAudit(page, SH_ROUTE)
  344 |   await page.getByText('Stream Health').waitFor({ timeout: 30_000 })
  345 |   await page.waitForTimeout(1500) // toasts de erro (lazy-import)
  346 |   await shootBothThemes(page, SH, 'error', true)
  347 | })
  348 | 
  349 | test('stream-health — degraded (Redis fora, gateway degradado, worker offline)', async ({ page }) => {
  350 |   await setupApp(page, {
  351 |     fixtures: SH_FIXTURES_OK,
  352 |     raw: {
  353 |       '**/api/health': {
  354 |         body: { status: 'degraded', checks: { database: true, redis: false } },
  355 |       },
  356 |       '**/api/streams/status': {
  357 |         body: {
  358 |           status: 'degraded',
  359 |           workers: [
  360 |             { worker_id: 'celery@worker-inference-01', status: 'online', active_tasks: 2 },
  361 |             { worker_id: 'celery@worker-quality-02', status: 'offline', active_tasks: 0 },
  362 |           ],
  363 |         },
  364 |       },
  365 |     },
  366 |   })
  367 |   await openStreamHealth(page)
  368 |   await page.getByText('celery@worker-quality-02').waitFor({ timeout: 15_000 })
  369 |   await shootBothThemes(page, SH, 'degraded', true)
  370 | })
  371 | 
  372 | test('stream-health — hover (botão Atualizar + card de câmera) [só dark]', async ({ page }) => {
  373 |   await setupApp(page, { fixtures: SH_FIXTURES_OK, raw: SH_RAW_OK })
  374 |   await openStreamHealth(page)
  375 | 
  376 |   await page.getByRole('button', { name: /Atualizar/ }).hover()
  377 |   await page.waitForTimeout(300)
  378 |   await shoot(page, SH, 'dark-hover-atualizar')
  379 | 
  380 |   await page.getByText('Câmera Pátio Norte').hover()
  381 |   await page.waitForTimeout(300)
  382 |   await shoot(page, SH, 'dark-hover-camera-card')
  383 | })
  384 | 
```