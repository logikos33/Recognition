# Flywheel — Volta 1: a volta mais curta possível

> Objetivo desta volta: **anotar ~50 frames → dataset → treino → ONNX → servir → 1 detecção real na tela do DEV.**
> Feia, manual, cheia de cliques — mas real, ponta a ponta. Serve pra provar que a esteira anda, não pra medir
> acurácia. Ver `docs/FLYWHEEL_ANOTACAO_EPI.md` para a escada completa (4 estágios) da qual esta é só o primeiro giro.
>
> Investigação de código desta proposta rodou em `wt-flywheel-anotacao` (branch `claude/flywheel-anotacao`, base
> `9463c03`), read-only — nenhum código foi alterado. Referências `arquivo:linha` abaixo são desse commit.

## Diagnóstico

1. **679 frames coletados, 0 anotados.** O elo quebrado não é coleta nem infra de ML — é o estágio [1] ANOTAÇÃO
   MANUAL da escada do flywheel, que ninguém executou ainda.
2. **`celery-worker` nunca teve deploy no Railway env Desenvolvimento.** Nada assíncrono roda no DEV hoje: build de
   dataset (`build_dataset_version_v2`) e dispatch de treino (`dispatch_training`) ficam enfileirados e nunca
   processados sem esse serviço.
3. **Achado NOVO desta investigação — a ferramenta de anotação própria não abre os 679 frames.** Mesmo com o
   "Bloqueio nº1" do `FLYWHEEL_ANOTACAO_EPI.md` corrigido no backend (a galeria já usa `list_images_filtered`,
   que mostra frames `source='nvr'`), **clicar numa miniatura desses frames não abre o anotador** — o clique só
   dispara se `img.video_id` existir (`TrainingPage.tsx:549`), e frames `nvr` têm `video_id` `NULL` por desenho
   desde a migration 094. `AnnotationInterface.jsx` em si também exige `videoId` (linha 26-41) e busca frames só
   via `/training/videos/{id}/frames` (linha 97) — um endpoint que não existe para frames sem vídeo pai. Isso
   **não** está registrado como bloqueio nem em `FLYWHEEL_ANOTACAO_EPI.md` nem na ADR-0048 — é um segundo bloqueio,
   irmão do primeiro, que ninguém tinha visto ainda.
4. **Achado NOVO nº2 — mesmo destravando os itens 2 e 3, o botão "Novo Treino" da UI hoje produz um modelo FALSO.**
   `POST /training/jobs` (`TrainingService.create_job`, `training_service.py:23-50`) nunca grava
   `training_jobs.dataset_version_id` — o parâmetro já existe na camada de repository
   (`TrainingRepository.create_job`, `training_repository.py:14-27`) mas não é exposto pelo service nem pelo
   handler. O fallback Celery usa `dataset_version_id=job_id` como **placeholder explícito**
   (`job_handlers.py:110`, comentário no código). Resultado: `_get_vast_context` (`training.py:490-526`) nunca
   encontra um `coco_r2_key` real → cai no fluxo legado (bloqueado por flag) → **simulação**
   (`_simulate_training`, `training.py:915-946`: sleep, métricas fabricadas, `model_path` que nunca é escrito).
5. **A cadeia arquitetural existe e está testada em partes — só não está fiada ponta a ponta.** Coleta → anotação →
   dataset → treino real (Vast.ai) → ONNX → servir (`RfDetrOnnxDetector`) → hot-reload via Redis: cada peça
   individualmente funciona e tem teste. O que falta é (a) throughput humano de anotação, (b) infra do worker no
   DEV, e (c) três fios soltos de fiação pequenos, dois deles descobertos só nesta sessão (itens 3 e 4).

## A volta curta — passo a passo

### Passo 0 — consertar a fiação (código, PORTÃO HUMANO — não feito nesta sessão)

Três correções pequenas e aditivas, nenhuma delas altera comportamento existente para quem já usa o sistema hoje.
Ficam registradas aqui como **pré-condição de código** da volta 1; a implementação é uma sessão futura de Claude
Code com revisão humana antes do merge (esta sessão foi documentação apenas).

| # | O quê | Onde | Esforço | Quem |
|---|---|---|---|---|
| 0a | Permitir abrir o anotador para um frame sem `video_id` (frames `source='nvr'`) — ex.: `AnnotationInterface` aceitar uma lista de frames já carregada pela galeria em vez de re-buscar por `videoId`, ou expor um "pool" por câmera/fonte no lugar do vídeo | `apps/frontend/src/pages/TrainingPage.tsx:549`, `apps/frontend/src/components/AnnotationInterface.jsx:26-113` | 3-5h | CC (código) + Vitor (revisão/merge) |
| 0b | Passar `dataset_version_id` de ponta a ponta: `TrainingService.create_job` aceitar o parâmetro e repassar pro repository (que já suporta); handler ler do body; corrigir o fallback Celery pra não usar `job_id` como placeholder | `training_service.py:23-50`, `job_handlers.py:100-183`, `training_repository.py:14-27` | 1-2h | CC (código) + Vitor (revisão/merge) |
| 0c | Deploy do `celery-worker` no ambiente Desenvolvimento do Railway | Railway (infra, sem código) | ~0.5h execução | **Vitor** (decisão de custo, ver Decisão 1) |

**Sem 0a, os 679 frames continuam inanotáveis pela ferramenta própria. Sem 0b, o treino real na Vast.ai nunca
recebe o dataset de verdade — vira simulação silenciosa mesmo com tudo mais certo. Sem 0c, nada assíncrono roda.**

### Passo 1 — anotar ~50 frames (humano, ferramenta própria — ADR-0048)

Com 0a feito: `/epi/training` → aba "Imagens" → filtro Origem = "Câmera/NVR" → clicar num frame → desenhar bbox +
classe (protetor auricular / luvas / óculos, conforme `module_classes` do tenant RVB) → salvar
(`POST /training/frames/{id}/annotations`, já funcional e testado). **Fica dentro da infra da Logikos — nenhuma
imagem sai para SaaS de terceiro** (mesma leitura da ADR-0048: R2 + ferramenta própria satisfazem o requisito
LGPD para este estágio).

- **Quem:** humano designado (Decisão 3 abaixo) — não é tarefa de CC, é trabalho de anotação real.
- **Esforço:** ~1.5-3h para 50 frames com 3 classes (inclui curva de aprendizado da ferramenta na primeira sessão).
  Nota: `FLYWHEEL_ANOTACAO_EPI.md` (regra R2) recomenda 100-150 exemplos/classe como semente **real**; 50 frames
  aqui é só para provar a esteira, não para ter um modelo bom.

### Passo 2 — construir a versão do dataset (disparo humano ou CC, execução no worker)

`POST /datasets/{dataset_id}/versions` → enfileira `build_dataset_version_v2` (`versioning_v2.py:245-259`), que
falha com `ValueError` se 0 frames anotados (linha 274) — por isso o Passo 1 é pré-condição, não em paralelo.
Faz snapshot dos frames rotulados, converte YOLO→COCO absoluto, split 70/20/10, zip pro R2
(`datasets/{tenant_id}/{dataset_id}/{version}/...`).

- **Quem:** humano dispara (1 clique/1 curl) — execução é automática no worker.
- **Esforço:** minutos de disparo + segundos de execução (dataset pequeno). **Depende do Passo 0c** (worker no ar).

### Passo 3 — decidir e disparar o treino real (Vitor decide, humano ou CC dispara)

`POST /training/jobs` com o `dataset_version_id` do Passo 2 (precisa do Passo 0b) → `dispatch_training` roda no
worker → Vast.ai REST real (única opção que produz ONNX de verdade hoje — ver Decisão 2).

- **Quem:** Vitor decide o provider (Decisão 2); humano ou CC dispara o job.
- **Esforço:** minutos de disparo. O treino em si roda em background na GPU alugada — não consome tempo humano,
  mas leva de alguns minutos a ~1h dependendo do preset/épocas (poucas épocas bastam pra provar a cadeia, ex. 20-30).

### Passo 4 — ativar o modelo e confirmar hot-reload (humano, minutos)

Aba "Modelo" em `/epi/training` → botão "Ativar" no modelo recém-treinado
(`POST /training/models/{id}/activate`) → publica `model:reload` no Redis
(`job_handlers.py:120-141`) → `RfDetrOnnxDetector` recarrega (`onnx_rfdetr.py:116-170`).

- **Quem:** humano.
- **Esforço:** minutos.

### Passo 5 — verificar 1 detecção real na tela (humano, verificação)

Abrir a câmera 1 ao vivo (ou um frame gravado) no DEV e confirmar visualmente que o modelo recém-treinado está
desenhando pelo menos uma bounding box real (não é preciso estar correta — é preciso ser o modelo novo rodando,
não o anterior).

- **Quem:** humano.
- **Esforço:** 15-30min de observação/validação.

### Esforço total estimado

**Código (Passo 0a+0b, sessão futura com portão humano):** 4-7h.
**Trabalho ativo humano/CC nesta volta (0c + 1 a 5):** ~4-6h, tipicamente espalhado por 1-3 dias corridos porque
depende de três decisões do Vitor e do tempo de treino real rodando em paralelo (não bloqueia humano).
**Total: ~8-13h de esforço ativo** — a maior fatia é o código de fiação (Passo 0) e a anotação (Passo 1), não o
disparo dos passos automatizados.

## Decisões que são do Vitor

1. **Deploy do `celery-worker` no env Desenvolvimento (Railway).** O serviço já existe no projeto Railway
   (usado em staging/produção), nunca foi deployado no ambiente DEV. É decisão de custo/infra, não técnica — sem
   ela, os Passos 2 e 3 não rodam em lugar nenhum (nem simulados).

2. **Onde roda o PRIMEIRO treino real.**
   - **Vast.ai (recomendado para a volta 1):** único caminho automatizado e testado ponta a ponta hoje
     (`_dispatch_vast_ai` → `_run_vast_remote_training`, WS-A4, já validado em produção). Trade-off: **as imagens
     reais dos frames saem da infra da Logikos/R2 e vão para uma instância GPU alugada de terceiro** durante o
     treino (`storage.generate_presigned_download_url`, `training.py:667`) — frames de câmera podem conter
     pessoas identificáveis (trabalhadores RVB). Nuance importante: esse caminho **não é hoje gateado** pela flag
     de opt-in `training_third_party_cloud_enabled` — essa flag só protege Ultralytics Hub e o fluxo legado
     Vast+Roboflow. A ADR-0047 declara Vast.ai REST como "não é nuvem de terceiro" no sentido da política dela
     (distinção: aluguel de GPU puro vs. plataforma SaaS de ML que indexa dataset) — mas do ponto de vista LGPD a
     imagem física ainda sai do perímetro controlado. **Com o contrato RVB em redação, vale confirmar se essa
     leitura é aceitável para o cliente antes do primeiro treino real, ou se convém exigir opt-in explícito por
     tenant mesmo para o caminho Vast.ai REST** (mudança pequena: aplicar a mesma checagem
     `_third_party_cloud_training_enabled` já usada no fluxo legado).
   - **LocalProvider — não é uma opção real hoje.** O nome sugere "treina numa máquina local", mas o código
     (`training_compute.py:82-93`) é um wrapper fino de `_simulate_training` — sleep, métricas fabricadas, nenhum
     ONNX real gerado. Não existe hoje infraestrutura de treino local de verdade (GPU própria + pipeline).
   - **Colab — não é um caminho automatizado hoje.** Aparece só como rótulo histórico em `ORIGIN_LABELS`
     (frontend); não há provider em `get_training_compute()` que dispare treino em Colab. Usar Colab exigiria
     treino manual fora do sistema + um script de registro em `trained_models` que hoje não existe em forma
     utilizável (`training/vast/upload_and_register.py` é legado e grava numa tabela `models(tenant_id, ...)`
     que não bate com o schema atual — nem `public.models` nem `{schema}.models` por-tenant correspondem).
   - **Recomendação:** Vast.ai para a volta 1, com a ressalva LGPD acima resolvida explicitamente (aceitar a
     leitura da ADR-0047 ou exigir opt-in) antes de disparar o primeiro job com dado real da RVB.

3. **Quem anota os ~50 frames e quando.** Não é tarefa de código — é agenda de pessoa. Precisa de um dono
   designado com ~2-3h disponíveis (Passo 1) e critério de classe alinhado com o Paulo (o que conta como
   violação, zonas da imagem) antes de começar, pra não anotar errado e ter que refazer.

## O que esta volta NÃO resolve

- Pré-anotação assistida (estágio [2]/[3] da escada) continua OFF — toda anotação é manual, do zero, sem ganho de
  velocidade.
- Qualidade do modelo com 50 frames é **prova de que a cadeia anda**, não prova de acurácia — a regra R2 do
  `FLYWHEEL_ANOTACAO_EPI.md` pede 100-150 exemplos/classe como semente real.
- Sem métrica de aceite formal (mAP/precision/recall mínimos) — qualquer número treinado serve pra esta volta.
- Sem pipeline contínuo nem agendado — cada etapa é disparo manual, um de cada vez.
- `celery-worker` no DEV segue deploy manual, sem monitoramento — se cair, ninguém percebe automaticamente.
- Sem gatilho por pessoa no edge (item ainda "em construção" na escada do `FLYWHEEL_ANOTACAO_EPI.md`) — a coleta
  continua no ritmo atual, não prioriza frame útil.
- Sem QA de anotação (segundo revisor) — os campos de proveniência (`created_by`/`reviewed_by`) já existem no
  schema (migration 095) mas não têm fluxo de validação formal exposto na UI (débito já registrado na ADR-0048).
- Sem monitoramento de drift do modelo em produção.
- A decisão LGPD sobre Vast.ai (Decisão 2) fica resolvida só para este primeiro treino, não vira política
  documentada — se a resposta for "exigir opt-in", isso merece uma ADR própria depois.

## Para industrializar depois (ordem sugerida)

1. **Pré-anotação assistida** — ligar a flag (`PreAnnotationControls`, hoje OFF) só quando houver semente mínima
   real (~100-150 exemplos/classe, regra R2).
2. **Fila de anotação com metas diárias** — dono designado + throughput mínimo (ver `docs/ROADMAP_GO_LIVE.md`,
   seção de gargalo de anotação).
3. **Validação/QA de anotação** — expor `reviewed_by`/segundo anotador na UI; hoje o dado existe no banco mas não
   tem fluxo.
4. **Treino agendado** — `check_auto_retraining` (Celery Beat, `auto_training.py`) já existe mas está
   `AUTO_TRAIN_ENABLED=false` por padrão; ligar quando o volume de frames validados justificar.
5. **Promoção de modelo com gate de métrica** — hoje "Ativar" é manual e sem piso de mAP; adicionar checagem antes
   de trocar o modelo em produção (existe `evaluate_challenger_model` como base, `model_evaluation.py`).
6. **Monitoramento de drift** — confiança média caindo, alertas de degradação do modelo ativo.

## Critério de aceite da volta 1

**1 detecção real do modelo treinado nesta volta, visível ao vivo (ou em frame gravado) na tela do DEV, com o
artefato ONNX correspondente versionado** — linha em `trained_models` com `origin='vast_ai'`, chave R2 do `.onnx`
preenchida, `is_active=true`, servindo de fato via `RfDetrOnnxDetector` (não `models/{job_id}/best.pt` fabricado
pela simulação).
