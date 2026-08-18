# Auditoria da aba de Treinamento — AS-IS real e TO-BE

**Data:** 2026-08-17 · **Escopo:** análise, zero código de produto alterado
**Árvore auditada:** clone fresco de `origin/develop` em `/Users/vitoremanuel/Logikos-mutirao/audit-training`
**HEAD inicial:** `65c510fb` → **HEAD final:** `98056cf7` (a develop avançou 11 commits durante a auditoria — ver §0.2)
**Migrations:** 111 arquivos, máxima `122_model_scenario_config.sql`
**Banco consultado:** DEV (`DATABASE_PUBLIC_URL`), schemas `public` + `rvb`. Somente `SELECT`.

---

## 0 · Divergências entre o briefing e o repositório

> Regra da rodada: divergência é achado, não obstáculo. Reportada no topo.

### 0.1 · O briefing do Frigate não existe — nunca existiu

O prompt afirma que `docs/decisions/BRIEFING_PADROES_FRIGATE_AWS.md` está no repositório.

**Não está — em lugar nenhum.** Verificado por:

- `git grep -il "frigate"` sobre **as 172 branches remotas** → só `docs/research/PESQUISA_CV_30_CAMERAS.md` e `Roccatextil/arquitetura-plataforma-multitenant.md`
- `git log --all --diff-filter=AD -- '*FRIGATE*'` → vazio (nunca foi adicionado nem removido)
- `find` em `~/Logikos-mutirao` e no checkout do iCloud → vazio

O prompt diz que o briefing do Frigate *"virou documento e sumiu do conjunto de trabalho"*.
**Ele não chegou a virar documento.** Nunca foi commitado. É a demonstração literal do risco que esta rodada existe para evitar.

**Fonte substituta usada:** `docs/research/PESQUISA_CV_30_CAMERAS.md` (seção Frigate) + as referências ao Frigate dentro das lições do AWS PPE.

### 0.2 · A PR #384 foi mergeada no meio da auditoria

O clone foi feito em `65c510fb`. Durante a rodada, `origin/develop` avançou **11 commits**, incluindo
`98056cf7 Merge pull request #384` — a **aba Classificar** e o **minerador de DVR**.

A árvore foi fast-forwarded para `98056cf7` e o AS-IS reflete o HEAD novo.
**Consequência:** a aba de Treinamento tem **5 abas**, não 4.

### 0.3 · A lição do AWS PPE só existe em PR aberta

`docs/decisions/licoes-repo-aws-ppe-dois-estagios.md` **não está em `develop`** — vive em `origin/analysis/aws-ppe-lessons` (PR #385, aberta). Lida de lá, marcada como "ainda não em develop".

### 0.4 · Colisão de numeração `D-` — 8 números duplicados

`develop` e a cadeia de PRs abertas (#385 → #386 → #388) usam os mesmos números para decisões diferentes:

| `D-` | Em `develop` (mergeado) | Nas PRs abertas |
|---|---|---|
| D-107 | Quatro caminhos de treino que mentiam | Estágio 2 = multilabel por recorte |
| D-108 | Volta 1 = modelo de UMA câmera | Ausência = veredito por-recorte forçado |
| D-109 | Export COCO devolvia ZERO anotações custom | Estágio 2 servido = loop síncrono |
| D-113 | Provisionamento de acessos do runner | Lote 1 bloqueado |
| D-114 | Tela de classificação por recorte | Medição da razão de ausência impossível |
| D-115 | Captura de 31/07 foi operação real | Veredito da meta de ausência |
| D-116 | Recon do minerador DVR no Orin | Consolidação das 4 correções |
| D-117 | Runner do lote 1 + corrente DVR | #384 não mergeado |

Além disso, **o D-117 da PR #388 afirma "#384 não mergeado"** — e #384 acabou de ser mergeada.
A cadeia de PRs de documentação já está desatualizada.

**Esta auditoria numera a partir de D-120** para não agravar a colisão.

### 0.5 · Correção de um erro cometido DENTRO desta auditoria

Um subagente concluiu — e eu repassei — que *"toda anotação aponta para classe não definida"*, porque a
query dele juntou `frame_annotations` só contra `module_classes`.

**Estava errado.** O export resolve contra `yolo_classes` com offset de namespacing
(`TENANT_CLASS_ID_OFFSET = 100_000`, `services/api/app/domain/services/class_namespace.py`).
12 das 13 classes resolvem normalmente. O defeito real é outro, mais estreito e mais grave — ver §1.2.

---

## 1 · AS-IS — inventário

### 1.1 · Telas e ações

Rota da aba: `/epi/training` (e `/epi/training/classes`) — `apps/frontend/src/AppRoutes.tsx`.
Página: `apps/frontend/src/pages/TrainingPage.tsx` (952 linhas), 5 abas em `TrainingPage.tsx:415-421`.

#### Aba 1 — Imagens

| O que faz | `file:line` | Endpoint | Estado no banco | ✔ |
|---|---|---|---|---|
| Galeria paginada de frames | `components/training/TrainingGallery.tsx` | `GET /training/images` | lê `public.training_frames` | ✅ |
| Filtros por câmera / status / origem | `components/training/CameraFilterSelector.tsx` | `GET /training/images/facets` | — | ✅ |
| Upload de imagens (lote ≤50, ≤10MB) | `training/image_handlers.py:242-412` | `POST /training/images` | insere `training_frames` (`source='upload'`) | ✅ |
| Curadoria: ativa / em dúvida / excluída | — | `POST /training/frames/curation` | `training_frames.curation_status` | 🟡 ver §3 item 6 |
| Abrir o Estúdio de Anotação | `TrainingPage.tsx:376-392` | — | — | ✅ |
| Busca por conteúdo (OWLv2) | `components/annotation/SearchContentPanel.tsx` | `POST /training/search/jobs` | `public.search_jobs` | ✅ |
| Ver achados e promover a anotação | `components/annotation/SearchFindingsPanel.tsx` | `POST /training/search/findings/promote` | insere `frame_annotations` | ✅ |

#### Aba 2 — Cobertura

| O que faz | `file:line` | Endpoint | Estado | ✔ |
|---|---|---|---|---|
| Matriz classe × câmera com metas | `components/training/CoverageMatrix.tsx` | `GET /training/coverage` | lê `frame_annotations` + `training_frames` | ✅ |
| Metas: ≥100 img/classe, ≥5 câmeras, ≤50% concentração | `domain/services/coverage_service.py:11-38` | — | — | ✅ |
| Atalho para a aba Classificar filtrada | `CoverageMatrix.tsx:47` | — | — | ✅ |

#### Aba 3 — Classificar (nova, mergeada durante a auditoria)

| O que faz | `file:line` | Endpoint | Estado | ✔ |
|---|---|---|---|---|
| Fila de recortes para veredito rápido | `components/annotation/CropClassifier.tsx:243-256` | `GET /training/images?is_annotated=false&curation_status=active` | lê `training_frames` | 🟡 **não filtra recorte vs frame inteiro** |
| Catálogo de classes | `CropClassifier.tsx:224` | `GET /modules/epi/classes` | lê `module_classes` + `yolo_classes` | ✅ |
| Aprovar (grava veredito) | `CropClassifier.tsx:397` | `POST /training/frames/{id}/annotations` | **replace-all** em `frame_annotations` | ✅ |
| "Não sei" / "recorte ruim" | `CropClassifier.tsx:414` | `POST /training/frames/curation` | `curation_status` | ✅ |
| Desfazer | `CropClassifier.tsx:442-461` | idem acima | reverte | ✅ |

#### Aba 4 — Modelo

| O que faz | `file:line` | Endpoint | Estado | ✔ |
|---|---|---|---|---|
| Catálogo de modelos + métricas (mAP@50, precisão, cobertura) | `TrainingPage.tsx:443-619` | `GET /training/models` | lê `trained_models` | ✅ |
| **Ativar modelo** | `TrainingPage.tsx:244` | `POST /training/models/{id}/activate` | `trained_models.is_active` + Redis `model:reload` | ⛔ **chama o caminho SEM gate** — ver §3 item 1 |
| Configurar cenário do modelo | `components/training/modals/ModelScenarioWizard` | `PUT /training/scenarios/{id}/config` | migration 122 | ✅ |
| Comparar campeão × desafiante | — | `POST /api/v1/models/{id}/evaluate` | `model_evaluations` | ⛔ **sem botão na tela** |

#### Aba 5 — Treino ao Vivo

| O que faz | `file:line` | Endpoint | Estado | ✔ |
|---|---|---|---|---|
| Status ao vivo (WS + polling 3s), loss/mAP | `TrainingPage.tsx:622-842` | `GET /training/jobs/current`, WS | lê `training_jobs` | ✅ |
| Formulário "Novo Treino" | `TrainingPage.tsx:697-723` | `POST /training/jobs` | insere `training_jobs` | 🟡 **não envia `dataset_version_id`** |
| Parar treino | — | `POST /training/jobs/{id}/stop` | `training_jobs.status` | ✅ |
| Histórico de jobs | `TrainingPage.tsx:843+` | `GET /training/jobs` | — | ✅ |

#### Estúdio de Anotação (tela cheia, aberto da aba Imagens)

`apps/frontend/src/components/annotation/AnnotationStudio.tsx`

Desenho/edição de caixas (`:600-742`), 20 atalhos de teclado (`useStudioKeyboard.ts`), zoom/pan/brilho
(`:568-620`, `:1162-1198`), autosave com badge e `beforeunload` (`:274-350`), fila de aprovação de propostas
de IA com borda tracejada e V/X (`:501-566`, `:1085-1112`), propagação semeada (`:416-453`), diretrizes (`G`).

**Todos funcionam.** Duas ressalvas medidas:
- autosave é **replace-all** (DELETE+INSERT do lote inteiro do frame a cada save), não diff — `:274-350`
- a imagem é renderizada **inteira**; as caixas são normalizadas 0-1 sobre ela (`studioTypes.ts:50-59`).
  Como o próprio acervo é misto (§1.2), "a imagem inteira" às vezes é um recorte e às vezes é a cena toda.

#### Backend — 45 rotas em `services/api/app/api/v1/training/`

`routes.py` + 11 handlers: `annotation`, `coverage`, `image`, `job`, `propagation`, `scenario`, `search`,
`validation`, `video`, `helpers`. Todas as 45 foram inventariadas e **existem**; nenhuma retorna mock.

**Blueprints adjacentes que a auditoria precisou incluir:**

| Blueprint | Rota-chave | Tem tela? |
|---|---|---|
| `api/v1/datasets/` | `POST /datasets/<id>/versions` — **export COCO** | ⛔ **não** |
| `api/v1/recorders/` | `POST /<id>/extract-frames` — **extração NVR** | ⛔ **não** |
| `api/v1/models/` | `POST /models/<id>/activate` — **ativação COM gate** | ⛔ **não** |
| `api/v1/modules/` | `PATCH /<module_code>/classes/<class_id>` | ✅ (aba Classes) |

### 1.2 · Os dados por trás (banco DEV, tenant `rvb`)

**Acervo — 9.667 frames RVB (100% `source='nvr'`) + 90 de e2e.**

| Recorte da base | Frames | Anotados |
|---|---|---|
| **Recorte de pessoa** (`width` < 640) | **8.413 (87%)** | 350 |
| **Frame inteiro** (`width` ≥ 640) | **1.254 (13%)** | 60 |

🔴 **Não existe coluna que distinga os dois.** Estão na mesma tabela, entram no mesmo dataset, e a aba
Classificar serve os dois indistintamente. Dimensões vão de 33×36 a 1437×934.

> Isto corrige as duas versões anteriores. **Não é "frames inteiros a recortar"** (erro da rodada passada)
> **nem "recortes de pessoa desde sempre"** (correção do briefing). **São os dois, misturados.**

**Estado de curadoria (RVB):** 9.257 não anotados (95,8%) · 410 anotados (4,2%).

| `curation_status` | Frames | Última mudança |
|---|---|---|
| `active` | **7.605** (78,7%) | — |
| `excluida` | **2.026** (21,0%) | **2026-08-17 22:16** |
| `duvida` | 36 (0,4%) | 2026-08-13 21:40 |

⚠️ **O acervo se moveu durante a auditoria.** Uma leitura no início da rodada deu
`active 9.225 / excluida 406`; ao final, `active 7.605 / excluida 2.026` — **~1.620 frames excluídos hoje
às 22:16**, enquanto esta auditoria rodava. Os números acima são os do fim da rodada.
**Um em cada cinco frames do RVB já está fora da curadoria.**

**Anotações — 599 no RVB (857 em todos os tenants), 100% `source='manual'`, ZERO vindas de pré-anotação.**

**Classes, resolvidas com a mesma lógica do export** (`versioning_v2.py:117-142`):

| `class_id` | Resolve para | Boxes | |
|---|---|---|---|
| 100004 / **4** | Protetor auditivo | 197 / **5** | 🔴 duplicado |
| 100006 / **6** | mascara | 114 / **79** | 🔴 duplicado |
| 100007 / **7** | Sem protetor de ouvido | 45 / **26** | 🔴 duplicado |
| 100010 | Botas | 55 | ✅ |
| 100009 | Sem mascara | 35 | ✅ |
| 100011 | Uso incorreto de mascara | 22 | ✅ |
| **5** | Protetor auricular | 18 | ⚠️ sinônimo de "Protetor auditivo" |
| **1** | hardhat | 1 | ⚠️ taxonomia antiga (D-103 tirou capacete) |
| **0** | *(NULL — não resolve)* | 1 | ⛔ |
| 100008 | incluir blur | 1 | ⚠️ não é classe de EPI |

🔴 **O defeito:** o export monta as categorias COCO **chaveando por `class_id`, não por nome**
(`versioning_v2.py:393-398`: `seen.setdefault(ann["class_id"], ...)`). Portanto o dataset sai com **duas
categorias distintas chamadas "mascara"**, duas "Protetor auditivo", duas "Sem protetor de ouvido" — e os
exemplos de cada conceito ficam **partidos entre duas classes que o modelo trata como diferentes**.

**466 dos 599 boxes (78%) estão nesses três conceitos duplicados.**

E a duplicata está **viva**, não é resíduo: os dois espaços de id foram gravados **nos mesmos dias**
(ambos até 13/08). As duas listas eram oferecidas na interface ao mesmo tempo.

**Classes com ZERO:** as classes de `module_classes` cujo `class_id` não aparece em `frame_annotations`
(`no_helmet`, `vest`, `no_vest`, `gloves`, `no_gloves`, `glasses`) têm **zero boxes** — são o catálogo
genérico em inglês, e a RVB anota no catálogo próprio em português. Não é bug; é a taxonomia por tenant
funcionando. Mas convive com o catálogo genérico **na mesma interface** — `ModuleClassesPage` mostra
"Suas classes" (tenant) e "Catálogo do módulo" lado a lado — e é isso que produz a duplicata acima.

**Onde a duplicata nasce:** `apps/frontend/src/pages/ModuleClassesPage.tsx` — as duas listas coexistem na
tela, com nomes equivalentes, e a anotação aceita `class_id` de qualquer uma.

**Observação de tenancy (baixa severidade, registrar):** o espaço de `class_id` pequeno (0–7) é
compartilhado entre tenants — `class_id=1` é usado por `rvb` (1 box) e por `e2e-fase-a-validation`
(189 boxes). Não há vazamento (o join passa por `training_frames.tenant_id`), mas o mesmo inteiro
significa coisas diferentes por tenant. O espaço namespaced (≥100000) não tem esse problema.

**Divergência com D-103:** D-103 (vigente) fixa 6 classes e tira Capacete/Colete. O banco tem `hardhat` (1
box) e `incluir blur` (1 box) vivos, e `Protetor auricular` como sinônimo solto.

**Propagação e busca:**

| | Número |
|---|---|
| Frames com proposta de IA gerada | **974** |
| Propostas **aprovadas** | **0** |
| Propostas **rejeitadas** | **974 (100%)** |
| Pendentes | 0 |
| Jobs de propagação | 8 completados, 5 falhados |

⚠️ **O motivo da rejeição não é gravado em lugar nenhum.** As 974 podem ter sido rejeitadas por qualidade
ruim, por limpeza de fila em lote, ou por terem rodado sobre frames inteiros do acervo misto. **São três
causas com tratamentos opostos, e o produto não distingue.** Reportado como dúvida, não como conclusão.

**Modelos e treino:**

| | Número |
|---|---|
| Modelos treinados | 2 |
| Modelos **ativos** | **0** |
| Training jobs | 12 — **9 `failed`**, 2 `completed`, 1 `stopped` |

---

## 1.3 · O PROCESSO real — AS-IS

> Formato do bloco 4. Ator · entra · sai · onde · dor · tempo.

```
1. Captura automática no edge (motion-triggered)
   ator: sistema
   entra: stream RTSP da câmera no Orin NX
   sai: frame OU recorte de pessoa (depende de o detector estar pronto) → POST /api/v1/edge/frames
   onde: services/edge-sync-agent/app/collector/collector_loop.py:171-213; crop_person em person_detector.py:340
   dor: o recorte só acontece se o detector estiver configurado E pronto; em 3 pontos o código cai para o frame
        inteiro. É a origem do acervo misto (8.413 recortes vs 1.254 frames inteiros) e nada marca qual é qual.
   tempo: contínuo

2. Extração de frames de gravação NVR/DVR
   ator: Vitor
   entra: recorder_id, canal, janela de tempo, intervalo
   sai: 1 frame inteiro por intervalo, via FFmpeg
   onde: POST /api/v1/recorders/<id>/extract-frames → recorders/routes.py:162 → nvr_extraction.py:46-158
   dor: É a origem de 100% do acervo RVB. NÃO TEM NENHUMA TELA — a palavra "recorder" não aparece
        nenhuma vez em apps/frontend/src. Só por curl/script.
   tempo: não sei

3. Upload manual de imagens ou vídeo (fallback)
   ator: Vitor
   entra: .jpg/.png/.webp (lote ≤50, ≤10MB) ou .mp4/.avi/.mov
   sai: frame inteiro em training_frames (source='upload' | 'video')
   onde: training/image_handlers.py:242-412; video_handlers.py
   dor:
   tempo: minutos, proporcional ao lote

4. Triagem/curadoria na galeria (aba Imagens)
   ator: Vitor
   entra: frames dos passos 1-3, filtros por câmera/status/origem
   sai: frame marcado active | duvida | excluida
   onde: TrainingGallery.tsx; POST /training/frames/curation
   dor: 'duvida' NÃO tira o frame do export — só 'excluida' tira (versioning_v2.py:80-83 admite em comentário).
        36 frames em dúvida entram no treino sem decisão humana, e a tela não avisa.
   tempo: não sei

5. Escolha do caminho de anotação  ◆ DECISÃO
   ator: Vitor
   entra: seleção na galeria
   sai: rota escolhida
   onde: TrainingGallery.tsx (barra de ação flutuante)
   saídas: [Anotar no Estúdio] [Classificar por recorte] [Propagação semeada] [Busca por conteúdo]
   dor:
   tempo: instantâneo

6. Anotação manual (Estúdio)
   ator: Vitor
   entra: a imagem armazenada (recorte OU cena inteira — não se sabe qual antes de abrir)
   sai: caixas normalizadas 0-1 → POST /training/frames/{id}/annotations
   onde: components/annotation/AnnotationStudio.tsx; studioTypes.ts:50-59
   dor: autosave é replace-all (DELETE+INSERT do lote inteiro por save), não diff.
        A lista de classes oferece catálogo genérico E custom do tenant com nomes iguais → é aqui que nasce
        a duplicata de class_id (466 de 599 boxes afetados).
   tempo: não sei

7. Classificação rápida por recorte (aba Classificar)
   ator: Vitor
   entra: fila de GET /training/images?is_annotated=false&curation_status=active
   sai: veredito por classe → POST /training/frames/{id}/annotations (replace-all)
   onde: components/annotation/CropClassifier.tsx:243-256
   dor: a fila NÃO filtra recorte vs frame inteiro. ~13% do que a aba apresenta como "um recorte de pessoa"
        é a cena inteira com várias pessoas — e a pergunta "esta pessoa está de máscara?" não tem resposta.
   tempo: não sei

8. Propagação semeada (DINOv2+SAM)
   ator: agente
   entra: sementes anotadas + pool de candidatos, disparado por Vitor
   sai: propostas em training_frames.pre_annotations
   onde: training/propagation_handlers.py:217-583; POST /training/propagation/jobs
   dor: 974 propostas geradas, 974 rejeitadas (100%), 0 aceitas. O motivo da rejeição não é gravado.
   tempo: não sei

9. Busca por conteúdo (OWLv2 zero-shot)
   ator: agente
   entra: termos em inglês (≤12/job) + frames, disparado por Vitor
   sai: achados (frame, termo, bbox, confiança) — não vira anotação sozinho
   onde: training/search_handlers.py; POST /training/search/jobs
   dor:
   tempo: não sei

10. Revisão e aceite das propostas  ◆ DECISÃO
    ator: Vitor
    entra: propostas pendentes / achados
    sai: anotação aceita OU descartada
    onde: POST /training/frames/{id}/pre-annotation-review; .../accept-suggestions; V/X no Estúdio
    saídas: [Aprovar (com ou sem edição)] [Rejeitar (descarta sem persistir)]
    dor: rejeitar não pede nem grava motivo — a informação de POR QUE a IA errou é jogada fora 974 vezes.
    tempo: não sei

11. Export do dataset (snapshot COCO)
    ator: Vitor
    entra: frames com is_annotated=true, curation_status != 'excluida', classe não arquivada
    sai: dataset_version com coco_r2_key em R2, status='ready'
    onde: POST /api/v1/datasets/<id>/versions → datasets/routes.py:104 → versioning_v2.py
    dor: PRÉ-REQUISITO DE TODO TREINO E NÃO TEM NENHUMA TELA. As 14 ocorrências de "dataset" no frontend
         são tooltip, tipo e texto de admin — zero chamadas de API. Só por curl.
         Além disso o COCO sai com categorias homônimas duplicadas (§1.2).
    tempo: não sei

12. Disparo do treino  ◆ DECISÃO
    ator: Vitor | sistema
    entra: dataset_version pronta (passo 11)
    sai: origem do job
    onde: TrainingPage.tsx (botão "Novo Treino") | auto_training.py (celery beat diário)
    saídas: [Manual: Vitor clica] [Automático: beat se crescimento > threshold]
    dor:
    tempo: instantâneo | diário

13. Criação do job — caminho manual
    ator: Vitor
    entra: preset, módulo, tamanho, épocas, batch, learning rate
    sai: training_jobs INSERT status='pending'
    onde: POST /training/jobs → job_handlers.py:178-220
    dor: o formulário não manda dataset_version_id; o backend resolve para a "mais recente". Se o passo 11
         nunca rodou, vai None e o job morre no dispatch.
    tempo: instantâneo

14. Criação do job — caminho automático
    ator: sistema
    entra: crescimento de frames anotados desde o último job completo
    sai: training_jobs INSERT (só se houver dataset_version 'ready')
    onde: auto_training.py:88-175
    dor: sem dataset_version pronta, o beat PULA EM SILÊNCIO — auto_train_skip é log INFO, nada chega à tela.
         O flywheel para todo dia sem ninguém saber.
    tempo: diário

15. Dispatch para GPU (RunPod)
    ator: sistema
    entra: job pending + dataset_version.coco_r2_key
    sai: pod provisionado, runner self-contained baixa o dataset e treina
    onde: queue/tasks/training.py:141-661; training/vast/remote_train.py
    dor: sem coco_r2_key o dispatch levanta erro e marca 'failed' (corretamente — nunca simula).
         É a causa direta dos 9 de 12 jobs falhados.
    tempo: ~1h (teto US$2 observado no Treino 1)

16. Verificação do artefato antes de 'completed'
    ator: sistema
    entra: callback do pod (X-Callback-Token)
    sai: trained_models INSERT só se verify_model_artifact confirmar o ONNX real em R2
    onde: POST /training/jobs/<id>/progress-callback; verify_model_artifact
    dor:
    tempo: não sei

17. Avaliação campeão × desafiante
    ator: sistema
    entra: modelo novo + modelo ativo
    sai: verdict PROMOTE|REJECT em model_evaluations
    onde: training.py:311-316 dispara evaluate_challenger_model automaticamente a cada treino bem-sucedido
    dor: o cálculo roda sozinho e o resultado NÃO APARECE em lugar nenhum da tela.
    tempo: não sei

18. Ativação do modelo  ◆ DECISÃO
    ator: Vitor
    entra: modelo no catálogo (aba Modelo)
    sai: trained_models.is_active=true + Redis 'model:reload'
    onde: TrainingPage.tsx:244 → POST /training/models/{id}/activate → job_handlers.py:265-280
    saídas: [Ativar] — sem alternativa; não há caminho na tela que consulte o veredito
    dor: existem DOIS endpoints de ativação. O com gate (models/registry_handlers.py:244-284: 409
         'eval_rejected', force só admin) NÃO É CHAMADO POR NINGUÉM no frontend. O botão chama o sem gate.
         Um modelo já reprovado pelo próprio sistema é ativado com um clique, em silêncio.
    tempo: instantâneo

19. Hot-reload na inferência
    ator: sistema
    entra: Redis pub/sub 'model:reload'
    sai: inference-service troca o modelo sem restart
    onde: job_handlers.py:_publish_model_reload
    dor:
    tempo: não sei

20. Fechamento do ciclo
    ator: sistema
    entra: modelo ativo detectando; novos frames chegando pelos passos 1-3
    sai: contagem cresce; beat tenta disparar
    onde: auto_training.py; model_drift_metrics
    dor: esbarra no passo 11 toda volta. RESULTADO MEDIDO: 0 modelos ativos. O ciclo nunca deu uma volta.
    tempo: nunca completou
```

**As 6 paradas manuais:**

1. **Extração NVR** (passo 2) — origem de 100% do acervo, só API
2. **Export do dataset** (passo 11) — pré-requisito de todo treino, só API
3. **"Em dúvida" não pausa o frame** (passo 4) — o produto não avisa
4. **Veredito de avaliação invisível** (passo 17) — calculado e descartado
5. **Ativação sem gate** (passo 18) — o gate existe e não é chamado
6. **Motivo de rejeição não gravado** (passo 10) — 974 vezes

---

## 2 · Confronto com os benchmarks

| Padrão | Fonte | Veredito | Onde / o que falta |
|---|---|---|---|
| Modelo custom por cliente, fine-tuned no equipamento real | AWS PPE | ✅ temos | `009_module_classes.sql` + ADR-0004 schema-per-tenant |
| Não usar nuvem gerenciada que não exporta modelo (D-110) | AWS PPE | ✅ temos | `training/vast/remote_train.py` → ONNX baixável + `verify_model_artifact` |
| **Split por vídeo ou câmera+dia (não random 20%)** | AWS PPE | ✅ **melhor** | `versioning_v2.py:175-199` `_group_key` — o repo AWS vaza com random |
| **Fila humana aprovar/rejeitar/corrigir** | AWS PPE | ✅ **melhor** | `VerificationQueuePage.tsx` + V/X no Estúdio — o repo AWS não tem loop |
| **Meta de dados por classe computada em código** | AWS PPE | ✅ **melhor** | `coverage_service.py:11-38` — 100 img, ≥5 câmeras, ≤50%; o benchmark só exige "mín. 10" |
| **Avaliação campeão×desafiante automatizada** | AWS PPE | ✅ **melhor** *(no cálculo)* | `model_evaluation.py:181` dispara sozinho; o repo AWS é 100% manual |
| **Artefato verificado antes de "completed"** | — | ✅ **melhor** | `training.py:33-37` — nenhum benchmark trata disso |
| **Limiar de confiança configurável** | AWS PPE | ✅ **melhor** | `ZoneTuningForm.tsx` por zona; o repo AWS esconde (Custom Labels) |
| Retreino como cadência contínua | Frigate + AWS | 🟡 parcial | `auto_training.py` existe e funciona, mas trava no passo 11 |
| Gate de ativação pelo veredito | AWS PPE | 🟡 parcial | backend pronto (`registry_handlers.py:244`), frontend não chama |
| Limiar por classe individual | AWS PPE | 🟡 parcial | hoje é por zona; a própria fonte marca como baixa prioridade |
| Estágio 2 servido = crop→classify multilabel | AWS PPE (D-107) | ❌ não temos | servido é single-stage (`detectors.py:169-216`); adiado com condição em D-107 |
| Veredito por-recorte FORÇADO (D-108) | AWS PPE | 🟡 parcial | aba Classificar mergeada, **mas serve pool misto** |
| Gate humano no minerador (`CONFIRM_MINE`, D-112) | AWS PPE | ✅ temos | `scripts/ops/mine_lote1.py:95` — mergeado na #384 |
| Ingestão operável por não-engenheiro | implícito nos dois | ❌ não temos | extração NVR e export sem tela |
| Separar decode de gravação (substream vs 4K) | Frigate | ⛔ não se aplica | camada de streaming, não console de ML |
| Esquema binário 1-classe-por-recorte (D-111) | AWS PPE | ⛔ não se aplica | nossa taxonomia já é multilabel multi-parte |

**Onde já fazemos melhor: 7 pontos**, todos confirmados com `file:line`. Os dois que o briefing antecipava
(split por câmera+dia, avaliação automatizada) **se confirmaram** — e apareceram mais cinco.

---

## 3 · TO-BE — 8 itens, ordenados por retorno sobre esforço

> Cada item serve um passo do processo e resolve uma dor medida.
> Nenhum item é justificado por "boa prática".

### 1 · Apontar o botão "Ativar" para o endpoint que já tem o gate — **P** — ✅ construir agora
- **Passo:** 18 (ativação)
- **Dor medida:** o gate campeão×desafiante está implementado e testado (`models/registry_handlers.py:244-284`:
  409 `eval_rejected`, `force` só admin, 404 cross-tenant) e **zero linhas do frontend o chamam**.
  `TrainingPage.tsx:244` chama o caminho sem gate. 2 modelos treinados, 0 avaliados antes de ativar.
- **Depende de:** nada. É trocar a URL e tratar o 409.

### 2 · Painel de Export de Dataset — **M** — ✅ construir agora
- **Passo:** 11 (export COCO)
- **Dor medida:** pré-requisito de todo treino, **zero chamadores no frontend**. Consequência direta:
  **9 de 12 training jobs falharam** e o beat diário pula em silêncio. **0 modelos ativos.**
- **Depende de:** nada. Endpoint pronto em `datasets/routes.py:104`.

### 3 · Deduplicar `class_id` por conceito no export — **P** — ✅ construir agora
- **Passo:** 11 (export) e 6 (anotação)
- **Dor medida:** **466 de 599 boxes (78%)** estão em 3 conceitos com dois `class_id` cada. O export
  chaveia por `class_id` (`versioning_v2.py:393`), então o COCO sai com categorias homônimas e os
  exemplos ficam partidos. Mais: `class_id=0` não resolve para nada.
- **Depende de:** decidir a taxonomia canônica (D-103 diz 6 classes). Duas frentes: consolidar no export
  (chavear por nome) **e** parar de oferecer as duas listas na anotação.

### 4 · Marcar recorte vs frame inteiro, e filtrar a fila da aba Classificar — **P/M** — ✅ construir agora
- **Passo:** 1, 4, 7
- **Dor medida:** **8.413 recortes e 1.254 frames inteiros** na mesma tabela sem coluna que os separe.
  A aba Classificar (`CropClassifier.tsx:243`) serve os dois como se fossem recorte — **~13% das perguntas
  "esta pessoa está de máscara?" são feitas sobre uma cena com várias pessoas.**
- **Depende de:** migration forward-only (coluna nova, `IF NOT EXISTS`) + backfill por `width`/`height`.

### 5 · Alerta visível quando o auto-treino trava — **P** — ✅ construir agora
- **Passo:** 14
- **Dor medida:** `auto_train_skip` é **log INFO** (`auto_training.py:161-163`). O flywheel para todo dia
  em silêncio. Como está, ninguém descobre que parou.
- **Depende de:** item 2 (o alerta só é acionável se houver onde resolver).

### 6 · Tornar "Em dúvida" honesto + mostrar o veredito do modelo — **P** — ✅ construir agora
- **Passo:** 4 e 17
- **Dor medida:** (a) `duvida` **não tira o frame do export** — só `excluida` tira
  (`versioning_v2.py:80-83`); são **36 frames** entrando sem decisão. (b) o veredito PROMOTE/REJECT é
  calculado a cada treino e **não aparece em lugar nenhum**.
- **Depende de:** nada.

### 7 · Gravar o motivo da rejeição de proposta — **P** — 🟡 construir adaptado
- **Passo:** 10
- **Dor medida:** **974 propostas rejeitadas, 0 aceitas, e nenhum motivo registrado.** Sem isso não dá
  para saber se a propagação é ruim, se foi limpeza de fila, ou se rodou sobre o acervo misto — **três
  causas com tratamentos opostos**.
- **Adaptação:** não construir taxonomia de motivos ainda. Três botões (`caixa errada` / `classe errada` /
  `imagem imprestável`) + campo livre opcional. Refina depois de 100 rejeições classificadas.
- **Depende de:** item 4 (para poder separar "rodou sobre frame inteiro" das outras causas).

### 8 · Estágio 2 servido (recorte → classificação multilabel) — **G** — ⏸️ adiar
- **Passo:** novo, entre 6/7 e a inferência servida
- **Dor:** é a lição central do AWS PPE (D-107/D-108 na PR #385), mas **a dor ainda não é medível**:
  o veredito por-recorte só começou a existir agora e não há lote classificado para dimensionar o ganho.
- **⏸️ Condição objetiva de reabertura:** *quando houver ≥500 recortes com veredito humano completo
  (present/absent/N-A por classe) E o FPS do Estágio 2 medido no Orin mantiver as 28 câmeras com folga.*
- **⛔ E quando for construído, NÃO construir fila/tabela/state-machine dedicada** — loop síncrono
  recorta→classifica (guardrail já registrado em D-109 da PR #385). Motivo: os padrões assíncronos do repo
  (`propagation_jobs`, `search_jobs`) vão ser reaproveitados por inércia, e aqui não há dor de orquestração
  para resolver — o Estágio 2 nem está servido.

---

## 3.1 · O PROCESSO TO-BE

```
 1. [igual] Captura automática no edge                                    (sistema)
 1.5 [novo] Marcação de origem: recorte OU frame inteiro                  (sistema)
            onde: migration nova + backfill por width/height + collector grava o tipo
            resolve: acervo misto indistinguível (8.413 vs 1.254)
 2. [muda]  Extração NVR — agora pelo Painel de Gravadores                (Vitor)
            onde: recorders/routes.py:162 (pronto) + NOVA tela
            resolve: origem de 100% do acervo deixa de exigir curl
 3. [igual] Upload manual (fallback)                                      (Vitor)
 4. [muda]  Triagem — "em dúvida" avisa que NÃO pausa o treino            (Vitor)
 5. [igual] Escolha do caminho de anotação                        ◆       (Vitor)
 6. [muda]  Anotação manual — UMA lista de classes, sem duplicata         (Vitor)
            resolve: 466 de 599 boxes em conceitos partidos
 7. [muda]  Classificação por recorte — fila filtrada a recortes de verdade (Vitor)
            resolve: ~13% de perguntas sem resposta possível
 8. [igual] Propagação semeada                                           (agente)
 9. [igual] Busca por conteúdo                                           (agente)
10. [muda]  Revisão — rejeitar pede motivo (3 botões)             ◆      (Vitor)
            resolve: 974 rejeições sem causa conhecida
11. [muda]  Export do dataset — agora pelo Painel de Datasets            (Vitor)
            onde: datasets/routes.py:104 (pronto) + NOVA tela
            resolve: o gargalo que zerou o flywheel
11.5 [novo] Export deduplica categorias por NOME, não por class_id       (sistema)
            onde: versioning_v2.py:393
12. [igual] Disparo do treino                                     ◆      (Vitor|sistema)
13. [muda]  Job manual — dataset_version escolhido explicitamente        (Vitor)
14. [muda]  Job automático — alerta visível quando pula                  (sistema)
            resolve: auto_train_skip deixa de ser log INFO mudo
15. [igual] Dispatch para GPU                                           (sistema)
16. [igual] Verificação do artefato                                     (sistema)
17. [muda]  Avaliação campeão×desafiante — veredito VISÍVEL na aba Modelo (sistema)
18. [muda]  Ativação — pelo endpoint COM gate; REJECT bloqueia    ◆      (Vitor)
            onde: models/registry_handlers.py:244 (pronto) — só redirecionar a chamada
            saídas: [Ativar (verdict=PROMOTE)] [Bloqueado 409 (REJECT)] [Forçar (só admin)]
19. [igual] Hot-reload na inferência                                    (sistema)
20. [muda]  Fechamento do ciclo — flywheel dá a primeira volta           (sistema)
(--) [sai]  Nenhum passo sai. O processo AS-IS não tem passo supérfluo — tem passo sem tela.
```

**A leitura do diagrama:** o AS-IS e o TO-BE têm **o mesmo esqueleto**. Não há passo a remover e quase nada
a inventar. Dos 8 itens, **4 são ligar frontend a backend que já existe e está testado** (1, 2, 5, 17/18).
O motor está inteiro; faltam correias.

---

## 4 · O que NÃO deu para determinar

1. **Por que as 974 propostas foram rejeitadas** — o banco não guarda motivo. Três causas possíveis com
   tratamentos opostos. É o item 7 do TO-BE, não uma conclusão.
2. **Se `training_third_party_cloud_enabled` está ligada hoje para o RVB** — a flag existe no código
   (`search_handlers.py`, `propagation_handlers.py`); não consultei o valor.
3. **Tempo real de um ciclo completo frame→modelo ativado** — nunca completou (0 modelos ativos).
   A única referência é pontual (Treino 1: teto US$2, timeout 1h).
4. **Esforço em dias dos itens 2 e 4** — classificados P/M por analogia com telas equivalentes, sem base
   histórica de velocidade.
5. **Se `model_deployments` (migration 100) é escrito por algum fluxo** — a ativação não a toca.
6. **Se existe tela fora de `apps/frontend/src`** que chame `/recorders` ou `/datasets` — busquei só ali.
7. **O conteúdo do briefing do Frigate** — o arquivo nunca existiu; o confronto com o Frigate usou a
   pesquisa `PESQUISA_CV_30_CAMERAS.md`, que é menos específica sobre console de ML.
8. **Se a duplicata de `class_id` já corrompeu o modelo `8e8fedf7`** — exigiria abrir o COCO exportado
   daquela volta; não fiz.
9. **A terceira verificação adversarial (números/restrições) não retornou** dentro da janela; as contagens
   foram conferidas manualmente contra o banco, mas sem a segunda opinião independente.
