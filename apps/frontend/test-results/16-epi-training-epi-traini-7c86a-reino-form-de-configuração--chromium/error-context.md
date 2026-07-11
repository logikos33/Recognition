# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: 16-epi-training.spec.ts >> epi-training — modal novo treino (form de configuração)
- Location: src/test/e2e/visual-audit/16-epi-training.spec.ts:270:1

# Error details

```
Test timeout of 90000ms exceeded.
```

```
Error: locator.waitFor: Test timeout of 90000ms exceeded.
Call log:
  - waiting for getByText('Learning Rate') to be visible

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
            - generic [ref=e14]: Treinamento
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
          - heading "Treinamento" [level=2] [ref=e94]
          - generic [ref=e95]:
            - tablist [ref=e96]:
              - tab "Imagens (138)" [ref=e97] [cursor=pointer]
              - tab "Modelo" [ref=e98] [cursor=pointer]
              - tab "Treino ao Vivo" [selected] [ref=e99] [cursor=pointer]
            - tabpanel "Treino ao Vivo" [ref=e100]:
              - generic [ref=e101]:
                - generic [ref=e102]:
                  - heading "Job Atual" [level=3] [ref=e103]
                  - generic [ref=e104]:
                    - button "Novo Treino" [active] [ref=e105] [cursor=pointer]:
                      - img [ref=e106]
                      - text: Novo Treino
                    - button "Atualizar" [ref=e108] [cursor=pointer]:
                      - img [ref=e109]
                - generic [ref=e114]:
                  - generic [ref=e115]:
                    - generic [ref=e116]:
                      - generic [ref=e117]:
                        - text: Módulo
                        - 'button "Mais informações: Módulo: qual produto de monitoramento gerou o evento" [ref=e118]':
                          - img [ref=e119]
                      - combobox [ref=e121]:
                        - option "EPI" [selected]
                        - option "Qualidade"
                    - generic [ref=e122]:
                      - generic [ref=e123]:
                        - text: Modelo Base
                        - 'button "Mais informações: Rede neural de partida. Nano = mais rápido, Medium = mais preciso" [ref=e124]':
                          - img [ref=e125]
                      - combobox [ref=e127]:
                        - option "LGKV26n (nano)" [selected]
                        - option "LGKV26s (small)"
                        - option "LGKV26m (medium)"
                    - generic [ref=e128]:
                      - generic [ref=e129]:
                        - text: Épocas
                        - 'button "Mais informações: Quantas vezes o modelo revê o dataset inteiro durante o treino. Mais épocas = mais aprendizado, porém mais tempo" [ref=e130]':
                          - img [ref=e131]
                      - spinbutton [ref=e133]: "50"
                    - generic [ref=e134]:
                      - generic [ref=e135]:
                        - text: Tamanho do lote
                        - 'button "Mais informações: Quantas imagens o modelo processa por vez. Valores maiores exigem mais memória de GPU" [ref=e136]':
                          - img [ref=e137]
                      - spinbutton [ref=e139]: "16"
                    - generic [ref=e140]:
                      - generic [ref=e141]:
                        - text: Taxa de aprendizado
                        - 'button "Mais informações: Velocidade com que o modelo ajusta seus pesos. Valores altos aprendem rápido mas podem desestabilizar" [ref=e142]':
                          - img [ref=e143]
                      - spinbutton [ref=e145]: "0.01"
                  - generic [ref=e146]:
                    - button "Iniciar Treinamento" [ref=e147] [cursor=pointer]:
                      - img [ref=e148]
                      - text: Iniciar Treinamento
                    - button "Cancelar" [ref=e150] [cursor=pointer]
                - generic [ref=e151]:
                  - generic [ref=e152]:
                    - generic "completed" [ref=e153]:
                      - generic [ref=e154]: Concluído
                    - generic [ref=e155]: LGKV26s · Balanceado
                    - generic [ref=e156]: 02/07/2026, 10:08
                  - generic [ref=e157]:
                    - generic [ref=e158]:
                      - generic [ref=e159]: mAP@50
                      - generic [ref=e160]: 91.3%
                    - generic [ref=e161]:
                      - generic [ref=e162]: Precisão
                      - generic [ref=e163]: 89.7%
                    - generic [ref=e164]:
                      - generic [ref=e165]: Cobertura
                      - generic [ref=e166]: 87.4%
              - generic [ref=e167]:
                - generic [ref=e168]:
                  - generic [ref=e169]: Log de Eventos
                  - button "limpar" [ref=e170] [cursor=pointer]
                - generic [ref=e171]: Aguardando eventos de treinamento...
              - heading "Histórico de Treinos" [level=3] [ref=e172]
              - table [ref=e174]:
                - rowgroup [ref=e175]:
                  - 'row "Modelo Preset Status Épocas Mais informações: Quantas vezes o modelo revê o dataset inteiro durante o treino. Mais épocas = mais aprendizado, porém mais tempo mAP@50 Mais informações: Precisão média das detecções considerando acerto de posição de 50% (métrica padrão YOLO). Quanto maior, melhor Precisão Mais informações: Das detecções feitas, quantas estavam certas Cobertura Mais informações: Dos objetos reais, quantos o modelo encontrou Data" [ref=e176]':
                    - columnheader "Modelo" [ref=e177]
                    - columnheader "Preset" [ref=e178]
                    - columnheader "Status" [ref=e179]
                    - 'columnheader "Épocas Mais informações: Quantas vezes o modelo revê o dataset inteiro durante o treino. Mais épocas = mais aprendizado, porém mais tempo" [ref=e180]':
                      - text: Épocas
                      - 'button "Mais informações: Quantas vezes o modelo revê o dataset inteiro durante o treino. Mais épocas = mais aprendizado, porém mais tempo" [ref=e181]':
                        - img [ref=e182]
                    - 'columnheader "mAP@50 Mais informações: Precisão média das detecções considerando acerto de posição de 50% (métrica padrão YOLO). Quanto maior, melhor" [ref=e184]':
                      - text: mAP@50
                      - 'button "Mais informações: Precisão média das detecções considerando acerto de posição de 50% (métrica padrão YOLO). Quanto maior, melhor" [ref=e185]':
                        - img [ref=e186]
                    - 'columnheader "Precisão Mais informações: Das detecções feitas, quantas estavam certas" [ref=e188]':
                      - text: Precisão
                      - 'button "Mais informações: Das detecções feitas, quantas estavam certas" [ref=e189]':
                        - img [ref=e190]
                    - 'columnheader "Cobertura Mais informações: Dos objetos reais, quantos o modelo encontrou" [ref=e192]':
                      - text: Cobertura
                      - 'button "Mais informações: Dos objetos reais, quantos o modelo encontrou" [ref=e193]':
                        - img [ref=e194]
                    - columnheader "Data" [ref=e196]
                - rowgroup [ref=e197]:
                  - row "LGKV26s Balanceado Treinando 32/50 — — — 07/07/2026, 08:57" [ref=e198]:
                    - cell "LGKV26s" [ref=e199]
                    - cell "Balanceado" [ref=e200]
                    - cell "Treinando" [ref=e201]:
                      - generic "running" [ref=e202]:
                        - generic [ref=e203]: Treinando
                    - cell "32/50" [ref=e204]
                    - cell "—" [ref=e205]
                    - cell "—" [ref=e206]
                    - cell "—" [ref=e207]
                    - cell "07/07/2026, 08:57" [ref=e208]
                  - row "LGKV26s Balanceado Concluído 50/50 91.3% 89.7% 87.4% 02/07/2026, 10:08" [ref=e209]:
                    - cell "LGKV26s" [ref=e210]
                    - cell "Balanceado" [ref=e211]
                    - cell "Concluído" [ref=e212]:
                      - generic "completed" [ref=e213]:
                        - generic [ref=e214]: Concluído
                    - cell "50/50" [ref=e215]
                    - cell "91.3%" [ref=e216]
                    - cell "89.7%" [ref=e217]
                    - cell "87.4%" [ref=e218]
                    - cell "02/07/2026, 10:08" [ref=e219]
                  - row "LGKV26n Accurate Falhou 21/50 — — — 28/06/2026, 15:22" [ref=e220]:
                    - cell "LGKV26n" [ref=e221]
                    - cell "Accurate" [ref=e222]
                    - cell "Falhou" [ref=e223]:
                      - generic "failed" [ref=e224]:
                        - generic [ref=e225]: Falhou
                    - cell "21/50" [ref=e226]
                    - cell "—" [ref=e227]
                    - cell "—" [ref=e228]
                    - cell "—" [ref=e229]
                    - cell "28/06/2026, 15:22" [ref=e230]
                  - row "LGKV26n Rápido Parado 15/50 — — — 24/06/2026, 05:50" [ref=e231]:
                    - cell "LGKV26n" [ref=e232]
                    - cell "Rápido" [ref=e233]
                    - cell "Parado" [ref=e234]:
                      - generic "stopped" [ref=e235]:
                        - generic [ref=e236]: Parado
                    - cell "15/50" [ref=e237]
                    - cell "—" [ref=e238]
                    - cell "—" [ref=e239]
                    - cell "—" [ref=e240]
                    - cell "24/06/2026, 05:50" [ref=e241]
                  - row "LGKV26n Balanceado Concluído 80/80 88.1% 86.2% 84.5% 24/06/2026, 03:00" [ref=e242]:
                    - cell "LGKV26n" [ref=e243]
                    - cell "Balanceado" [ref=e244]
                    - cell "Concluído" [ref=e245]:
                      - generic "completed" [ref=e246]:
                        - generic [ref=e247]: Concluído
                    - cell "80/80" [ref=e248]
                    - cell "88.1%" [ref=e249]
                    - cell "86.2%" [ref=e250]
                    - cell "84.5%" [ref=e251]
                    - cell "24/06/2026, 03:00" [ref=e252]
                  - row "LGKV26n Balanceado Concluído 50/50 84.2% 83.0% 79.0% 10/06/2026, 12:20" [ref=e253]:
                    - cell "LGKV26n" [ref=e254]
                    - cell "Balanceado" [ref=e255]
                    - cell "Concluído" [ref=e256]:
                      - generic "completed" [ref=e257]:
                        - generic [ref=e258]: Concluído
                    - cell "50/50" [ref=e259]
                    - cell "84.2%" [ref=e260]
                    - cell "83.0%" [ref=e261]
                    - cell "79.0%" [ref=e262]
                    - cell "10/06/2026, 12:20" [ref=e263]
      - button "Abrir dashboard de observability" [ref=e264] [cursor=pointer]:
        - generic [ref=e265]: Banco de dados
        - generic [ref=e268]: Redis
        - generic [ref=e271]: câmeras ativas
    - button "Abrir chat" [ref=e273] [cursor=pointer]:
      - img [ref=e274]
  - generic "Notificações"
```

# Test source

```ts
  178 | ]
  179 | 
  180 | // VerificationQueuePage
  181 | const QUEUE_ITEMS = [
  182 |   {
  183 |     id: 'vq-001', camera_id: 'cam-0001', camera_name: 'Câmera Pátio Norte', class_name: 'no_helmet',
  184 |     confidence: 0.42, violations: [{ class: 'no_helmet', confidence: 0.42, bbox: [0.2, 0.1, 0.4, 0.6] }],
  185 |     verification_reason: 'Oclusão parcial do capacete pela viga — não foi possível confirmar a violação',
  186 |     created_at: minAgo(4), timestamp: minAgo(4),
  187 |   },
  188 |   {
  189 |     id: 'vq-002', camera_id: 'cam-0002', camera_name: 'Câmera Doca 2', class_name: 'no_vest',
  190 |     confidence: 0.55, violations: [{ class: 'no_vest', confidence: 0.55, bbox: [0.5, 0.2, 0.7, 0.8] }],
  191 |     verification_reason: 'Baixa iluminação na zona de carga; colete pode estar presente',
  192 |     created_at: minAgo(11), timestamp: minAgo(11),
  193 |   },
  194 |   {
  195 |     id: 'vq-003', camera_id: 'cam-0003', camera_name: 'Câmera Almoxarifado', class_name: 'no_gloves',
  196 |     confidence: 0.63, violations: [{ class: 'no_gloves', confidence: 0.63, bbox: [0.3, 0.4, 0.5, 0.7] }],
  197 |     verification_reason: 'Mãos parcialmente fora do quadro durante a detecção',
  198 |     created_at: minAgo(23), timestamp: minAgo(23),
  199 |   },
  200 |   {
  201 |     id: 'vq-004', camera_id: 'cam-0004', camera_name: 'Câmera Portão Leste', class_name: 'no_glasses',
  202 |     confidence: 0.68, violations: [{ class: 'no_glasses', confidence: 0.68, bbox: [0.15, 0.1, 0.3, 0.3] }],
  203 |     verification_reason: 'Reflexo na lente pode ter sido confundido com ausência de óculos',
  204 |     created_at: minAgo(37), timestamp: minAgo(37),
  205 |   },
  206 |   {
  207 |     id: 'vq-005', camera_id: 'cam-0005', camera_name: 'Câmera Linha de Produção A', class_name: 'no_helmet',
  208 |     confidence: 0.74, violations: [{ class: 'no_helmet', confidence: 0.74, bbox: [0.6, 0.05, 0.8, 0.5] }],
  209 |     created_at: minAgo(52), timestamp: minAgo(52),
  210 |   },
  211 |   {
  212 |     id: 'vq-006', camera_id: 'cam-0006', camera_name: 'Câmera Oficina', class_name: 'no_vest',
  213 |     confidence: 0.88, violations: [{ class: 'no_vest', confidence: 0.88, bbox: [0.25, 0.2, 0.55, 0.9] }],
  214 |     verification_reason: 'EPI possivelmente presente, porém fora do padrão de cor do tenant',
  215 |     created_at: minAgo(75), timestamp: minAgo(75),
  216 |   },
  217 | ]
  218 | 
  219 | // ---------------------------------------------------------------------------
  220 | // Helpers de navegação
  221 | // ---------------------------------------------------------------------------
  222 | 
  223 | async function openTraining(page: Page, fixtures: Record<string, unknown> = TRAIN_FIXTURES) {
  224 |   await setupApp(page, { fixtures, raw: FRAME_IMG_RAW })
  225 |   await gotoAudit(page, '/epi/training')
  226 |   await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
  227 | }
  228 | 
  229 | // ===========================================================================
  230 | // PÁGINA 1 — epi-training (/epi/training)
  231 | // ===========================================================================
  232 | 
  233 | test('epi-training — default (tab Imagens, galeria rica)', async ({ page }) => {
  234 |   await openTraining(page)
  235 |   await page.getByText('Página 1 de 6').waitFor({ timeout: 30_000 })
  236 |   await settle(page)
  237 |   await shootBothThemes(page, 'epi-training', 'default', true)
  238 | })
  239 | 
  240 | test('epi-training — tab Modelo', async ({ page }) => {
  241 |   await openTraining(page)
  242 |   await page.getByRole('tab', { name: 'Modelo' }).click()
  243 |   await page.getByText('Modelo Ativo').waitFor({ timeout: 30_000 })
  244 |   await page.getByText('Modelos Treinados').waitFor()
  245 |   await settle(page)
  246 |   await shootBothThemes(page, 'epi-training', 'tab-modelo', true)
  247 | })
  248 | 
  249 | test('epi-training — tab Treino ao Vivo (job rodando)', async ({ page }) => {
  250 |   await openTraining(page)
  251 |   await page.getByRole('tab', { name: 'Treino ao Vivo' }).click()
  252 |   await page.getByText('Job Atual').waitFor({ timeout: 30_000 })
  253 |   await page.getByText('Histórico de Treinos').waitFor()
  254 |   // Espera 2 ciclos do polling de 3s para acumular linhas no Log de Eventos
  255 |   await page.waitForTimeout(3800)
  256 |   await shootBothThemes(page, 'epi-training', 'tab-treino', true)
  257 | })
  258 | 
  259 | test('epi-training — tab Treino sem GPU (banner simulação)', async ({ page }) => {
  260 |   await openTraining(page, {
  261 |     ...TRAIN_FIXTURES,
  262 |     '**/api/training/jobs/current/status**': CURRENT_COMPLETED_SEM_GPU,
  263 |   })
  264 |   await page.getByRole('tab', { name: 'Treino ao Vivo' }).click()
  265 |   await page.getByText('Chave de GPU não configurada').waitFor({ timeout: 30_000 })
  266 |   await settle(page)
  267 |   await shootBothThemes(page, 'epi-training', 'tab-treino-sem-gpu', true)
  268 | })
  269 | 
  270 | test('epi-training — modal novo treino (form de configuração)', async ({ page }) => {
  271 |   await openTraining(page, {
  272 |     ...TRAIN_FIXTURES,
  273 |     '**/api/training/jobs/current/status**': CURRENT_COMPLETED,
  274 |   })
  275 |   await page.getByRole('tab', { name: 'Treino ao Vivo' }).click()
  276 |   await page.getByRole('button', { name: 'Novo Treino' }).click()
  277 |   await page.getByText('Modelo Base').waitFor({ timeout: 30_000 })
> 278 |   await page.getByText('Learning Rate').waitFor()
      |                                         ^ Error: locator.waitFor: Test timeout of 90000ms exceeded.
  279 |   await settle(page, 400)
  280 |   await shootBothThemes(page, 'epi-training', 'modal-novo-treino', true)
  281 | })
  282 | 
  283 | test('epi-training — empty', async ({ page }) => {
  284 |   await openTraining(page, {
  285 |     '**/api/training/images**': { frames: [], total: 0, page: 1, page_size: 24, total_pages: 0 },
  286 |     '**/api/training/models': [],
  287 |     '**/api/classes': [],
  288 |     '**/api/training/jobs': [],
  289 |     '**/api/training/jobs/current/status**': { job: null, gpu_enabled: true, live: null },
  290 |   })
  291 |   await page.getByText('Nenhuma imagem de treino').waitFor({ timeout: 30_000 })
  292 |   await settle(page)
  293 |   await shootBothThemes(page, 'epi-training', 'empty')
  294 | })
  295 | 
  296 | test('epi-training — loading (stall na galeria)', async ({ page }) => {
  297 |   await setupApp(page, {
  298 |     fixtures: {
  299 |       '**/api/training/models': MODELS,
  300 |       '**/api/classes': YOLO_CLASSES,
  301 |       '**/api/training/jobs': JOBS_HISTORY,
  302 |       '**/api/training/jobs/current/status**': CURRENT_RUNNING,
  303 |     },
  304 |     stall: ['**/api/training/images**'],
  305 |   })
  306 |   await gotoAudit(page, '/epi/training')
  307 |   await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
  308 |   await page.waitForTimeout(1200)
  309 |   await shootBothThemes(page, 'epi-training', 'loading')
  310 | })
  311 | 
  312 | test('epi-training — error (500 em todos os endpoints de treino)', async ({ page }) => {
  313 |   await setupApp(page, {
  314 |     raw: {
  315 |       '**/api/training/**': { status: 500, body: { status: 'error', error: 'Erro interno do servidor' } },
  316 |       '**/api/classes': { status: 500, body: { status: 'error', error: 'Erro interno do servidor' } },
  317 |     },
  318 |   })
  319 |   await gotoAudit(page, '/epi/training')
  320 |   await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
  321 |   // Catches silenciosos → cai nos estados vazios (toast do errorTranslator pode aparecer)
  322 |   await page.getByText('Nenhuma imagem de treino').waitFor({ timeout: 30_000 })
  323 |   await settle(page)
  324 |   await shootBothThemes(page, 'epi-training', 'error')
  325 | })
  326 | 
  327 | test('epi-training — annotation full-screen (clique numa imagem)', async ({ page }) => {
  328 |   // AnnotationInterface (JSX legado) espera shape {success:true,...} — vai via raw
  329 |   await setupApp(page, {
  330 |     fixtures: TRAIN_FIXTURES,
  331 |     raw: {
  332 |       ...FRAME_IMG_RAW,
  333 |       '**/api/training/videos/*/frames**': {
  334 |         status: 200,
  335 |         body: { success: true, frames: GALLERY_FRAMES.slice(0, 10) },
  336 |       },
  337 |       '**/api/modules/epi/classes': {
  338 |         status: 200,
  339 |         body: { success: true, data: { classes: MODULE_CLASSES } },
  340 |       },
  341 |       '**/api/training/frames/*/annotations**': {
  342 |         status: 200,
  343 |         body: { success: true, annotations: [] },
  344 |       },
  345 |     },
  346 |   })
  347 |   await gotoAudit(page, '/epi/training')
  348 |   await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
  349 |   await page.getByTitle('Câmera Pátio Norte — turno manhã').first().click()
  350 |   try {
  351 |     await page.getByText('← Voltar').waitFor({ timeout: 15_000 })
  352 |   } catch {
  353 |     // never-stop: captura o que estiver na tela mesmo sem a âncora
  354 |   }
  355 |   await settle(page)
  356 |   await shootBothThemes(page, 'epi-training', 'annotation-fullscreen', true)
  357 | })
  358 | 
  359 | test('epi-training — hovers (dark)', async ({ page }) => {
  360 |   await openTraining(page)
  361 |   await page.getByText('Página 1 de 6').waitFor({ timeout: 30_000 })
  362 |   await settle(page)
  363 | 
  364 |   await page.getByRole('button', { name: 'Anotadas', exact: true }).hover()
  365 |   await page.waitForTimeout(300)
  366 |   await shoot(page, 'epi-training', 'hover-filtro-anotadas')
  367 | 
  368 |   await page.getByRole('tab', { name: 'Modelo' }).click()
  369 |   await page.getByText('Modelos Treinados').waitFor()
  370 |   await page.getByRole('button', { name: 'Ativar', exact: true }).first().hover()
  371 |   await page.waitForTimeout(300)
  372 |   await shoot(page, 'epi-training', 'hover-btn-ativar-modelo')
  373 | })
  374 | 
  375 | // ===========================================================================
  376 | // PÁGINA 2 — training-classes (/epi/training/classes)
  377 | // ===========================================================================
  378 | 
```