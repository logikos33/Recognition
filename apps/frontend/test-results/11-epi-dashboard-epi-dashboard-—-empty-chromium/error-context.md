# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: 11-epi-dashboard.spec.ts >> epi-dashboard — empty
- Location: src/test/e2e/visual-audit/11-epi-dashboard.spec.ts:268:1

# Error details

```
Test timeout of 90000ms exceeded.
```

```
Error: locator.waitFor: Test timeout of 90000ms exceeded.
Call log:
  - waiting for getByText('Nenhum alerta recente') to be visible

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
            - generic [ref=e13]: /
            - generic [ref=e14]: Dashboard
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
          - generic [ref=e94]:
            - generic [ref=e95]:
              - img [ref=e97]
              - generic [ref=e100]:
                - generic [ref=e101]:
                  - text: Cameras Ativas
                  - 'generic "Sobre: Cameras Ativas" [ref=e102]':
                    - img [ref=e103]
                - generic [ref=e106]: "0"
                - generic [ref=e107]: de 0 total
            - generic [ref=e108] [cursor=pointer]:
              - img [ref=e110]
              - generic [ref=e113]:
                - generic [ref=e114]:
                  - text: Taxa de Conformidade
                  - 'generic "Sobre: Taxa de Conformidade" [ref=e115]':
                    - img [ref=e116]
                - generic [ref=e119]: —
                - generic [ref=e120]: ultimas 24h
            - generic [ref=e121] [cursor=pointer]:
              - img [ref=e123]
              - generic [ref=e125]:
                - generic [ref=e126]:
                  - text: Alertas Hoje
                  - 'generic "Sobre: Alertas Hoje" [ref=e127]':
                    - img [ref=e128]
                - generic [ref=e131]: "0"
            - generic [ref=e132]:
              - img [ref=e134]
              - generic [ref=e136]:
                - generic [ref=e137]:
                  - text: Alertas/Hora
                  - 'generic "Sobre: Alertas/Hora" [ref=e138]':
                    - img [ref=e139]
                - generic [ref=e142]: "0"
            - generic [ref=e143]:
              - img [ref=e145]
              - generic [ref=e153]:
                - generic [ref=e154]:
                  - text: Modelo Ativo
                  - 'generic "Sobre: Modelo Ativo" [ref=e155]':
                    - img [ref=e156]
                - generic [ref=e159]: —
                - generic [ref=e160]: nenhum modelo ativo
          - generic [ref=e162]:
            - button "Abrir painel de controle" [ref=e163] [cursor=pointer]:
              - img [ref=e164]
            - generic [ref=e165]:
              - generic [ref=e166]:
                - button "Adicionar câmera na posição 1" [ref=e167]:
                  - button "Adicionar câmera na posição 1" [ref=e168] [cursor=pointer]:
                    - img [ref=e169]
                    - generic [ref=e170]: Adicionar câmera
                - button "Adicionar câmera na posição 2" [ref=e171]:
                  - button "Adicionar câmera na posição 2" [ref=e172] [cursor=pointer]:
                    - img [ref=e173]
                    - generic [ref=e174]: Adicionar câmera
                - button "Adicionar câmera na posição 3" [ref=e175]:
                  - button "Adicionar câmera na posição 3" [ref=e176] [cursor=pointer]:
                    - img [ref=e177]
                    - generic [ref=e178]: Adicionar câmera
                - button "Adicionar câmera na posição 4" [ref=e179]:
                  - button "Adicionar câmera na posição 4" [ref=e180] [cursor=pointer]:
                    - img [ref=e181]
                    - generic [ref=e182]: Adicionar câmera
              - status [ref=e183]
            - generic [ref=e184]:
              - generic [ref=e185]:
                - img [ref=e186]
                - button "Layout 1x1" [ref=e188] [cursor=pointer]: 1x1
                - button "Layout 2x2" [ref=e189] [cursor=pointer]: 2x2
                - button "Layout 3x3" [ref=e190] [cursor=pointer]: 3x3
                - button "Layout 4x4" [ref=e191] [cursor=pointer]: 4x4
                - button "Layout 1+5" [ref=e192] [cursor=pointer]: 1+5
                - button "Layout 1+7" [ref=e193] [cursor=pointer]: 1+7
              - button "Toggle labels" [ref=e194] [cursor=pointer]:
                - img [ref=e195]
              - button "Salvar preset" [ref=e198] [cursor=pointer]:
                - img [ref=e199]
                - generic [ref=e203]: Salvar
              - button "Fullscreen" [ref=e204] [cursor=pointer]:
                - img [ref=e205]
          - generic [ref=e210]:
            - generic [ref=e211]: Indicadores
            - generic [ref=e212]:
              - group "Período dos indicadores" [ref=e213]:
                - button "Hoje (24h)" [ref=e214] [cursor=pointer]
                - button "7 dias" [pressed] [ref=e215] [cursor=pointer]
                - button "30 dias" [ref=e216] [cursor=pointer]
              - button "Personalizar" [ref=e217] [cursor=pointer]:
                - img [ref=e218]
                - text: Personalizar
          - generic [ref=e219]:
            - generic [ref=e221]:
              - generic [ref=e222]:
                - 'heading "Alertas ao longo do tempo Sobre: Alertas ao longo do tempo" [level=2] [ref=e224]':
                  - generic [ref=e225]:
                    - text: Alertas ao longo do tempo
                    - 'generic "Sobre: Alertas ao longo do tempo" [ref=e226]':
                      - img [ref=e227]
                - generic [ref=e230]:
                  - button "Mover widget Alertas ao longo do tempo" [ref=e231]:
                    - img [ref=e232]
                  - button "Ocultar widget Alertas ao longo do tempo" [ref=e239] [cursor=pointer]:
                    - img [ref=e240]
              - status [ref=e247]:
                - paragraph [ref=e248]: Sem dados no período
                - paragraph [ref=e249]: Nenhum evento registrado no intervalo selecionado.
            - generic [ref=e251]:
              - generic [ref=e252]:
                - 'heading "Distribuição de Violações Sobre: Distribuição de Violações" [level=2] [ref=e254]':
                  - generic [ref=e255]:
                    - text: Distribuição de Violações
                    - 'generic "Sobre: Distribuição de Violações" [ref=e256]':
                      - img [ref=e257]
                - generic [ref=e260]:
                  - button "Mover widget Distribuição de Violações" [ref=e261]:
                    - img [ref=e262]
                  - button "Ocultar widget Distribuição de Violações" [ref=e269] [cursor=pointer]:
                    - img [ref=e270]
              - status [ref=e277]:
                - paragraph [ref=e278]: Sem dados no período
                - paragraph [ref=e279]: Nenhum evento registrado no intervalo selecionado.
            - generic [ref=e281]:
              - generic [ref=e282]:
                - 'heading "Câmeras com mais alertas Sobre: Câmeras com mais alertas" [level=2] [ref=e284]':
                  - generic [ref=e285]:
                    - text: Câmeras com mais alertas
                    - 'generic "Sobre: Câmeras com mais alertas" [ref=e286]':
                      - img [ref=e287]
                - generic [ref=e290]:
                  - button "Mover widget Câmeras com mais alertas" [ref=e291]:
                    - img [ref=e292]
                  - button "Ocultar widget Câmeras com mais alertas" [ref=e299] [cursor=pointer]:
                    - img [ref=e300]
              - status [ref=e307]:
                - paragraph [ref=e308]: Sem dados no período
                - paragraph [ref=e309]: Nenhum evento registrado no intervalo selecionado.
            - generic [ref=e311]:
              - generic [ref=e312]:
                - 'heading "Últimos Alertas Sobre: Últimos Alertas" [level=2] [ref=e314]':
                  - generic [ref=e315]:
                    - text: Últimos Alertas
                    - 'generic "Sobre: Últimos Alertas" [ref=e316]':
                      - img [ref=e317]
                - generic [ref=e320]:
                  - button "Mover widget Últimos Alertas" [ref=e321]:
                    - img [ref=e322]
                  - button "Ocultar widget Últimos Alertas" [ref=e329] [cursor=pointer]:
                    - img [ref=e330]
              - status [ref=e337]:
                - paragraph [ref=e338]: Sem dados no período
                - paragraph [ref=e339]: Nenhum evento registrado no intervalo selecionado.
            - generic [ref=e341]:
              - generic [ref=e342]:
                - 'heading "Registro de Eventos Sobre: Registro de Eventos" [level=2] [ref=e344]':
                  - generic [ref=e345]:
                    - text: Registro de Eventos
                    - 'generic "Sobre: Registro de Eventos" [ref=e346]':
                      - img [ref=e347]
                - generic [ref=e350]:
                  - button "Mover widget Registro de Eventos" [ref=e351]:
                    - img [ref=e352]
                  - button "Ocultar widget Registro de Eventos" [ref=e359] [cursor=pointer]:
                    - img [ref=e360]
              - status [ref=e367]:
                - paragraph [ref=e368]: Sem dados no período
                - paragraph [ref=e369]: Nenhum evento registrado no intervalo selecionado.
          - status [ref=e370]
      - button "Abrir dashboard de observability" [ref=e371] [cursor=pointer]:
        - generic [ref=e372]: Banco de dados
        - generic [ref=e375]: Redis
        - generic [ref=e378]: câmeras ativas
    - button "Abrir chat" [ref=e380] [cursor=pointer]:
      - img [ref=e381]
  - generic "Notificações"
```

# Test source

```ts
  171 |     vest: 88.7,
  172 |     gloves: 71.3,
  173 |     glasses: 65.8,
  174 |   },
  175 | }
  176 | 
  177 | const RICH_FIXTURES = {
  178 |   '**/api/alerts*': { alerts: ALERTS, total: 12, page: 1, pages: 1 },
  179 |   '**/api/cameras': { cameras: CAMERAS },
  180 |   '**/api/modules/epi/stats': STATS,
  181 |   '**/api/cameras/*/stream/info': {
  182 |     type: 'hls',
  183 |     url: 'http://localhost:3001/streams/demo/stream.m3u8',
  184 |   },
  185 | }
  186 | 
  187 | const ERROR_500 = {
  188 |   status: 500,
  189 |   body: { status: 'error', error: 'Erro interno do servidor' },
  190 | }
  191 | 
  192 | /* ── Helpers locais ─────────────────────────────────────────────── */
  193 | 
  194 | /** Seeda o grid DVR (zustand persist) com 3 câmeras + 1 célula vazia. */
  195 | async function seedGrid(page: Page) {
  196 |   await page.addInitScript(() => {
  197 |     localStorage.setItem(
  198 |       'epi-camera-grid',
  199 |       JSON.stringify({
  200 |         state: {
  201 |           activeLayoutId: '2x2',
  202 |           cellAssignments: { 0: 'cam-1', 1: 'cam-2', 2: 'cam-3', 3: null },
  203 |           customPresets: [],
  204 |           showLabels: true,
  205 |         },
  206 |         version: 0,
  207 |       })
  208 |     )
  209 |   })
  210 | }
  211 | 
  212 | async function gotoRich(page: Page) {
  213 |   await setupApp(page, { fixtures: RICH_FIXTURES })
  214 |   await seedGrid(page)
  215 |   await gotoAudit(page, ROUTE)
  216 |   await page.getByText('Últimos Alertas').waitFor()
  217 |   await settle(page)
  218 | }
  219 | 
  220 | async function openWizard(page: Page) {
  221 |   await page.getByLabel('Abrir painel de controle').click()
  222 |   await page.getByText('Painel de Controle').waitFor()
  223 |   await page.getByRole('button', { name: /Nova Camera/i }).click()
  224 |   await page.getByText('Passo 1 de 4').waitFor()
  225 | }
  226 | 
  227 | async function wizardToStep2(page: Page) {
  228 |   await page.getByRole('button', { name: 'Intelbras' }).click()
  229 |   await page.getByRole('button', { name: 'Próximo →' }).click()
  230 |   await page.getByText('Passo 2 de 4').waitFor()
  231 | }
  232 | 
  233 | async function wizardToStep3(page: Page) {
  234 |   await page.getByPlaceholder('192.168.1.100').fill('10.0.42.15')
  235 |   await page.getByPlaceholder('admin').fill('admin')
  236 |   await page.getByPlaceholder('Senha de acesso').fill('recognition123')
  237 |   await page.getByRole('button', { name: 'Próximo →' }).click()
  238 |   await page.getByText('Passo 3 de 4').waitFor()
  239 | }
  240 | 
  241 | async function wizardToStep4(page: Page) {
  242 |   await page.getByPlaceholder('Ex: Entrada Principal, Baia 1...').fill('Câmera Portaria Sul')
  243 |   await page.getByPlaceholder('Ex: Bloco A, Térreo...').fill('Portaria Sul')
  244 |   await page.getByRole('button', { name: 'Próximo →' }).click()
  245 |   await page.getByText('Passo 4 de 4').waitFor()
  246 | }
  247 | 
  248 | /* ── Estados base ───────────────────────────────────────────────── */
  249 | 
  250 | test('epi-dashboard — default (rico)', async ({ page }) => {
  251 |   await gotoRich(page)
  252 |   await shootBothThemes(page, SLUG, 'default', true)
  253 | })
  254 | 
  255 | test('epi-dashboard — default quadrantes Q3/Q4 (viewport alto)', async ({ page }) => {
  256 |   // O shell tem overflow:hidden — em 900px de altura a 2ª linha do quadrantGrid
  257 |   // (Registro de Eventos + Distribuição de Violações) fica clipada. Viewport
  258 |   // alto revela os quadrantes inferiores para a auditoria.
  259 |   await page.setViewportSize({ width: 1440, height: 1700 })
  260 |   await setupApp(page, { fixtures: RICH_FIXTURES })
  261 |   await seedGrid(page)
  262 |   await gotoAudit(page, ROUTE)
  263 |   await page.getByText('Registro de Eventos').waitFor()
  264 |   await settle(page)
  265 |   await shootBothThemes(page, SLUG, 'default-quadrantes')
  266 | })
  267 | 
  268 | test('epi-dashboard — empty', async ({ page }) => {
  269 |   await setupApp(page) // catch-all {} → sem alertas, sem câmeras, sem stats
  270 |   await gotoAudit(page, ROUTE)
> 271 |   await page.getByText('Nenhum alerta recente').waitFor()
      |                                                 ^ Error: locator.waitFor: Test timeout of 90000ms exceeded.
  272 |   await settle(page)
  273 |   await shootBothThemes(page, SLUG, 'empty', true)
  274 | })
  275 | 
  276 | test('epi-dashboard — loading (stall)', async ({ page }) => {
  277 |   await setupApp(page, {
  278 |     stall: [
  279 |       '**/api/alerts*',
  280 |       '**/api/cameras',
  281 |       '**/api/cameras/**',
  282 |       '**/api/modules/epi/stats',
  283 |     ],
  284 |   })
  285 |   await gotoAudit(page, ROUTE)
  286 |   await page.getByText('Cameras Ativas').waitFor()
  287 |   // settle() esperaria networkidle que nunca chega (requests penduradas)
  288 |   await page.waitForTimeout(1500)
  289 |   await shootBothThemes(page, SLUG, 'loading', true)
  290 | })
  291 | 
  292 | test('epi-dashboard — error (500)', async ({ page }) => {
  293 |   await setupApp(page, {
  294 |     raw: {
  295 |       '**/api/alerts*': ERROR_500,
  296 |       '**/api/cameras': ERROR_500,
  297 |       '**/api/modules/epi/stats': ERROR_500,
  298 |     },
  299 |   })
  300 |   await gotoAudit(page, ROUTE)
  301 |   await page.getByText('Cameras Ativas').waitFor()
  302 |   await page.waitForTimeout(1500) // deixa o toast de erro aparecer
  303 |   await shootBothThemes(page, SLUG, 'error', true)
  304 | })
  305 | 
  306 | /* ── Drawers dos KPIs ───────────────────────────────────────────── */
  307 | 
  308 | test('epi-dashboard — drawer KPI Alertas Hoje', async ({ page }) => {
  309 |   await gotoRich(page)
  310 |   await page.getByText('Alertas Hoje').click()
  311 |   await page.getByText('Ultimos Alertas').waitFor() // título do drawer (sem acento)
  312 |   await settle(page, 500)
  313 |   await shootBothThemes(page, SLUG, 'modal-kpi-alertas')
  314 | })
  315 | 
  316 | test('epi-dashboard — drawer KPI Conformidade', async ({ page }) => {
  317 |   await gotoRich(page)
  318 |   await page.getByText('Taxa de Conformidade').click()
  319 |   await page.getByText('Conformidade por EPI').waitFor()
  320 |   await settle(page, 500)
  321 |   await shootBothThemes(page, SLUG, 'modal-kpi-conformidade')
  322 | })
  323 | 
  324 | /* ── Painel/menus do grid de câmeras ────────────────────────────── */
  325 | 
  326 | test('epi-dashboard — painel de controle do grid', async ({ page }) => {
  327 |   await gotoRich(page)
  328 |   await page.getByLabel('Abrir painel de controle').click()
  329 |   await page.getByText('Painel de Controle').waitFor()
  330 |   await settle(page, 500)
  331 |   await shootBothThemes(page, SLUG, 'modal-painel-cameras')
  332 | })
  333 | 
  334 | test('epi-dashboard — seletor de câmera (célula vazia)', async ({ page }) => {
  335 |   await gotoRich(page)
  336 |   // getByLabel evita o wrapper sortable do dnd-kit (também expõe role=button)
  337 |   await page.getByLabel('Adicionar câmera na posição 4').click()
  338 |   await page.getByText('Selecionar câmera').waitFor()
  339 |   await settle(page, 500)
  340 |   await shootBothThemes(page, SLUG, 'modal-seletor-camera')
  341 | })
  342 | 
  343 | test('epi-dashboard — menu de contexto da célula', async ({ page }) => {
  344 |   await gotoRich(page)
  345 |   // primeira ocorrência no DOM = header da célula do grid (Q1 vem antes de Q2/Q3)
  346 |   await page.getByText('Câmera Pátio Norte').first().click({ button: 'right' })
  347 |   await page.getByText('Trocar câmera').waitFor()
  348 |   await shootBothThemes(page, SLUG, 'modal-menu-contexto')
  349 | })
  350 | 
  351 | /* ── Wizard Nova Câmera (aberto a partir do painel do grid) ─────── */
  352 | 
  353 | test('epi-dashboard — wizard nova câmera passo 1', async ({ page }) => {
  354 |   await gotoRich(page)
  355 |   await openWizard(page)
  356 |   await settle(page, 500)
  357 |   await shootBothThemes(page, SLUG, 'wizard-step1')
  358 | })
  359 | 
  360 | test('epi-dashboard — wizard nova câmera passo 2', async ({ page }) => {
  361 |   await gotoRich(page)
  362 |   await openWizard(page)
  363 |   await wizardToStep2(page)
  364 |   await settle(page, 500)
  365 |   await shootBothThemes(page, SLUG, 'wizard-step2')
  366 | })
  367 | 
  368 | test('epi-dashboard — wizard nova câmera passo 3', async ({ page }) => {
  369 |   await gotoRich(page)
  370 |   await openWizard(page)
  371 |   await wizardToStep2(page)
```