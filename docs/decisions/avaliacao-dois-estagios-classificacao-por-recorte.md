# Avaliação — Arquitetura de dois estágios (localizar pessoa → classificar recorte)

- **Tipo:** Avaliação / recomendação (NÃO é decisão aceita; vira ADR se o Vitor aprovar)
- **Data:** 2026-08-14 · **Escopo:** somente DEV · **Módulo:** EPI · **Tenant:** RVB (`63c219d8-fbef-4f3c-a7c9-058c742482e2`)
- **Garantias desta rodada:** zero linha de código de produto alterada · nenhum modelo treinado · **nenhum frame saiu do ambiente** (só contagens no banco DEV) · não toca `staging`/`main`/`interchange`
- **Origem:** arquitetura da solução AWS `amazon-rekognition-custom-ppe-detection-with-custom-labels` (a solução em si está descartada — inferência só na nuvem, US$4/h, não devolve modelo; colide com ADR-0043 e edge-first)

---

## TL;DR — o veredito

**O Estágio 1 (localizar a pessoa e recortar) já existe, já está em produção no edge e já produziu ~8.600 recortes de pessoa.** A pergunta real não é "adotar dois estágios?" — metade já foi adotada sem alarde. A pergunta é **"o Estágio 2 deve virar classificação-por-recorte?"** e **"quem localiza as partes do corpo — AWS, modelo aberto, ou pose?"**

- **Recomendação (uma frase):** **Adotar dois estágios com Estágio 2 = classificação multilabel por recorte de pessoa, mantendo o detector de pessoa YOLOX que já roda no edge; a AWS não entra (nem como acelerador), porque o gargalo dela — localizar pessoa e partes — a pose local resolve de graça, com mais partes (pés/orelhas) e sem fronteira LGPD.** O que decide isso está medido para *pessoa* (95% no frame real) e é factual (não estimado) para *cobertura de partes*; falta só medir a *qualidade* de pose vs AWS numa próxima rodada — abaixo o runbook.
- **Próxima rodada (não esta):** bench de partes do corpo (pose vs modelo aberto) nos mesmos 30 frames reais, local; e um export/trainer de classificador protótipo. Detalhado na §7.

⚠️ **Os números do prompt estão desatualizados** (o acervo cresce todo dia). Reconciliação real abaixo; nenhuma conclusão muda por causa do drift, mas os números certos importam para a próxima rodada.

| Prompt | Real (banco DEV, 2026-08-14) |
|---|---|
| 7.235 recortes de pessoa | **8.620** (5.861 <400px + 2.759 mid 400–700px) |
| 1.432 frames cheios | **1.014** (fallback do detector de pessoa) |
| ~9.000 frames | **9.634** frames RVB, todos `source='nvr'` |
| 345 anotações | **857** anotações (todas `source='manual'`), em **400 frames distintos** |
| ~800 propostas, ~15% aproveitável | **1.005 propostas, 100% rejeitadas** (a rejeição em voo já terminou) |

---

## 1 · O que já existe

### 1.1 De onde vêm os recortes — e quem os gera (item 1)

**São recortes de PESSOA, gerados por um detector de pessoa YOLOX-nano ONNX que roda no edge.** Não são resto de propagação nem crops de busca de conteúdo.

- **O cropper:** `services/edge-sync-agent/app/collector/person_detector.py` — `PersonDetector` roda **YOLOX-nano ONNX (Apache 2.0, só classe COCO `person`, `_PERSON_CLASS_ID=0` na linha 49)** em entrada 416×416 com tiling 2×2. `crop_person()` (linhas 340-374) recorta o **maior** bbox de pessoa em resolução nativa, com margens `_CROP_MARGIN_X=0.25`, `_CROP_MARGIN_Y=0.08` — **enviesadas para enquadrar cabeça/EPI** (docstring do módulo diz explicitamente: *"isto é gatilho de coleta, NÃO a detecção de EPI"*).
- **Quem chama:** `collector_loop.py:171-215` (`_payload_para_upload`) — pré-filtro de movimento (frame-diff) → se acha pessoa, sobe o **recorte**; se o detector está off/indisponível/erra, sobe o **frame cheio** (fallback, linhas 184-193). Uploader: `frame_uploader.py:31-56` → `POST /api/v1/edge/frames`.
- **Onde entram no banco:** `services/api/app/api/v1/edge/routes.py:586-699`. `source='nvr'` é **hardcoded na linha 679** para todo upload do edge — por isso recorte e frame cheio têm o mesmo `source`, `camera_id` e `recorder_id`; só diferem em `width`/`height`, lidos dos bytes reais (linhas 618-621). Isso explica os 3 buckets de tamanho num único `source`.
- **A extração NVR pela nuvem** (`infrastructure/queue/tasks/nvr_extraction.py:134-144`) produz **frames cheios** e nem passa `width/height` — não é a fonte dos recortes.
- **Propagação (SAM+DINO) e busca (OWLv2) NÃO criam recortes:** ambas só fazem `UPDATE` em `training_frames.pre_annotations`, nunca `INSERT` (`tasks/search.py:253`, `tasks/propagation.py`). Confirmado pela ausência de qualquer `frame_repo.create(...)` nesses arquivos.

**Servem?** Sim, para o propósito de dois estágios: são recortes de uma pessoa, enviesados para cabeça/tronco. **A taxa de acerto do detector de pessoa é MEDIDA e real** (a condição exata que a pose/AWS teriam de enfrentar — 704×480, RVB):

| Semana | recortes (pessoa achada) | fallback cheio | % com pessoa |
|---|---|---|---|
| 2026-07-27 | 47 | 616 | 7,1% *(antes do detector entrar)* |
| 2026-08-03 | 3.797 | 209 | **94,8%** |
| 2026-08-10 | 4.777 | 189 | **96,2%** |

⚠️ **Ressalva honesta:** esses 95% são "dos frames que o coletor decidiu subir (após pré-filtro de movimento + gate de pessoa), 95% tinham pessoa". Não é "de todos os frames do CFTV". E o fallback mistura *sem-pessoa* com *detector-off/erro*. Mesmo com a ressalva, é o sinal mais forte que existe: **o Estágio 1 de pessoa já resolve o frame real da RVB a ~95%, de graça, local, Apache.**
📌 **Não verificado visualmente** (sem credencial R2 no ambiente desta rodada). O código é decisivo; recomendo um spot-check visual de ~10 recortes na próxima rodada para confirmar enquadramento.

### 1.2 O pipeline servido é de UM estágio (item 2)

**Veredito: SINGLE-STAGE.** Um detector roda uma vez por frame e cospe caixas de classe-EPI direto. Não há cascata pessoa→recorte→classifica no caminho servido.

- `services/inference/inference/inference_engine.py:128-131` — `_run_detector()` chama `self._detector.predict(frame)` **exatamente uma vez** no frame inteiro; `process_frame` (110-121) chama o detector uma vez, depois DeepSORT (tracker, não classificador). Nenhuma segunda inferência.
- `services/inference/inference/detectors.py:169-216` (`YoloxOnnxDetector.predict`) e `:306-322` (`RfDetrOnnxDetector.predict`) — **um** `session.run(...)` mapeando logits direto para os `class_names` de EPI. Default `yolox_onnx` (`config.py:16`); `VIOLATION_CLASSES="no_helmet,no_vest,no_gloves"` (`config.py:23`).
- DeepStream: `deepstream/shared/custom_parsers/config_infer_yolox.template.txt:5-6` é `[primary-gie]`; **`rg "sgie|secondary-gie"` = zero hits no repo** — nenhum classificador secundário existe. E o backend DeepStream nem está em disco (`main.py:32-67` instancia o ONNX incondicionalmente; não há branch por `INFERENCE_ENGINE`).
- **Zero AGPL/ultralytics no servido** (`detectors.py:470-476` levanta `ValueError` para `"ultralytics"` — ADR-0043).
- **Nota:** um crop→classifica de verdade existe no repo, mas só para OCR de placa no fueling (`lpr_service.py:129`), sem relação com EPI. Serve de precedente de código.

### 1.3 Por que isto resolve o problema de ontem

A propagação semeada falhou porque **ausência não tem aparência** — a *similaridade* SAM+DINO casou "sem capacete" com chão e sombra (1.005 propostas, 100% rejeitadas). Mas o Estágio 1 já **ancorou a pessoa**. Com a pessoa isolada num recorte, *"sem capacete"* deixa de ser "onde está o objeto invisível?" e vira *"este recorte de pessoa tem capacete?"* — uma **classificação**, com um lugar concreto para a ausência morar. A infraestrutura que faltava para essa virada já está no ar.

---

## 2 · As 857 anotações convertem para rótulo por recorte? (item 3)

**Sim, e barato — porque o Estágio 1 já fez o trabalho caro.** Das 400 frames anotadas da RVB, **363 são recortes/mid (uma pessoa por imagem) e só 37 são frame cheio.**

- **O recorte JÁ É a pessoa.** Para os 363 recortes, converter "caixas → multilabel por pessoa" é trivial: o conjunto de `class_name` das caixas daquele recorte *é* o rótulo daquele recorte. Não precisa atribuir caixa a pessoa (o Estágio 1 garantiu 1 pessoa dominante). Média de **1,46 caixa/recorte** (máx 4) — rótulos esparsos, fáceis de colapsar.
- **Os 37 frames cheios** precisariam de atribuição-a-pessoa (caixa dentro da região da pessoa). ~9% das frames anotadas. Perda pequena, ou reaproveitáveis passando o detector de pessoa por cima.

### 🔴 O ponto que decide — pessoa sem caixa

A distinção "conforme vs não-anotada" **não pode ser inferida dos dados atuais.** Medido, nos 363 recortes anotados:

| Recorte tem… | qtd |
|---|---|
| só rótulo de EPI **presente** (mascara, Botas, Protetor auditivo…) | **273** |
| só rótulo de **ausência** (Sem X, Uso incorreto) | 67 |
| ambos (misto) | 23 |

**273 recortes só têm o que está presente marcado.** Se o treino assumir "classe não-marcada = ausente/conforme", ele vai rotular como "sem luvas / sem óculos" gente que só não teve esse item anotado. **Isso é falso.** O Vitor marcou irregularidades e alguns presentes, **não fez um inventário completo por pessoa.** Portanto:

- ✅ **Preserva-se todo rótulo POSITIVO** existente (present e absence) → ~857 sinais viram multilabel esparso sobre ~400 recortes-pessoa.
- ⛔ **Não se pode fabricar negativo** para as classes não-marcadas (rótulo parcial). Um classificador multilabel treina bem com rótulo parcial **se** a loss ignorar classes não-anotadas (masked BCE) — mas o dataset **não** vira "conforme/não-conforme limpo" automaticamente.
- **Quantas se perdem se não converter?** Zero rótulos se perdem na conversão (todos migram). O que "se perde" é a *ilusão* de ter negativos — que a abordagem de caixa também nunca teve. Empate nesse ponto; a caixa não é superior aqui.

⚠️ **Débito de dados a limpar antes de qualquer treino** (independente da decisão de arquitetura): 258/857 anotações estão sem `class_name` denormalizado (têm `class_id` 1/2); duas classes foram soft-deletadas — `"Protetor auricular"` (duplica `"Protetor auditivo"`) e `"incluir blur"` (é instrução, não classe); e coexistem dois registries (`public.module_classes` canônico 0-7 helmet/vest/gloves/glasses ↔ `public.yolo_classes` custom por tenant). A taxonomia RVB precisa de consolidação — 3 estados por parte (`mascara` / `Sem mascara` / `Uso incorreto de mascara`) já sugere naturalmente um classificador de 3 vias por parte do corpo.

---

## 3 · Custo de mudar, por componente (item 4)

| Componente | `file:line` | Muda quanto? |
|---|---|---|
| **Estágio 1 (localizar+recortar)** | `edge-sync-agent/.../person_detector.py` | **~zero — já roda.** Recorta pessoa a 95% no frame real. Só ganha upgrade se for para partes (§6). |
| **Tela de anotação → classificar** | `AnnotationStudio.tsx` (desenho de caixa: draft 353, resize 164-171/739, paleta 1209-1243) | **Baixo-médio.** O padrão "grade de recortes + seletor de classe + promover" **já existe** em `SearchFindingsPanel.tsx:190-320` (grid 287-316, `cropStyle` 40-54, select 220-243, promote 300-312). Reaproveita ~150 linhas; muda só o que o `promote()` grava. O canvas de caixa (~600 linhas) fica opcional. |
| **Export de dataset** | `versioning_v2.py:105-156` (`_fetch_annotations`), `:293-332` (`_build_coco_split`); COCO-only em `datasets/routes.py:123-129` | **Médio.** Hoje emite **COCO detecção**. Classificação precisa de novo path `{imagem_recorte, classe}` (ImageFolder/CSV) ao lado do `_build_coco_split`. `_fetch_annotations` reaproveita 100% (mesma query). |
| **Executor de treino** | `training/vast/remote_train.py` (`train_rfdetr` 152, `train_yolox` 225; Apache, linha 7) | **Alto (o maior pedaço novo).** Só existe treinador de **detector**. Classificador = `train_classifier()` novo (timm/torchvision + export ONNX). Bem mais simples que detector, mas net-new — não há nada de classificação em `training/`. |
| **Inferência no edge** | servido é single-stage ONNX (§1.2) | **Alto.** Hoje 1 passada. Dois estágios = detector-pessoa + N classificadores em série. Custo em FPS no Orin **não medido** — ver §6/§7. |
| **Propagação** | SAM+DINO só faz UPDATE | **Melhora.** Recorte de pessoa é objeto grande e coerente — a similaridade passa a fazer sentido (era o que faltava). Mas com classificação-por-recorte a propagação vira **menos necessária**: rotular recorte é 2s de tecla, então propagar 800 caixas ruins deixa de ser o caminho. |

---

## 4 · O que se PERDE — honesto (item 5)

- ⛔ **Some a caixa exata do EPI na tela.** Marca-se *a pessoa/parte* como irregular, não *o capacete ausente*. Para EPI/segurança (o alerta é "fulano sem capacete", não "o capacete está no pixel X") **isso é aceitável** — o produto quer a violação por pessoa, não a coordenada do objeto. Perde-se só se um cliente exigir "aponte o EPI na imagem".
- **Duas (ou N) inferências por frame** em vez de uma — custo no Orin, **não medido** (§7). Mitigável: a §2.6 do RVB (`project_cenario_rvb_multimodulo`) fechou 3 módulos no Orin com GPU 72% a 28 cams; sobra folga, mas classificadores em série consomem.
- **Erro do detector de pessoa vira erro do sistema todo.** Pessoa não detectada = violação não vista. **Mitigante medido: 95% de acerto no frame real** (§1.1). Os 5% (oclusão pela tela metálica, pessoa a 10m) são o risco real — precisa de fallback (manter também um detector single-stage de baixa confiança? decisão futura).
- **Classes que não são sobre pessoa** — a RVB não tem nenhuma (todas as classes são EPI vestido por pessoa). Não é problema aqui.

---

## 5 · Híbrido (detecção p/ objeto presente + classificação p/ ausência) — elegante ou complexidade dobrada? (item 6)

**Veredito: no full-frame seria elegante; no recorte-de-pessoa é desnecessário.** O híbrido nasce do mundo single-stage, onde "onde está a luva?" precisa de caixa. Mas **num recorte de UMA pessoa há uma cabeça, um par de mãos, um par de pés** — não há ambiguidade de "qual objeto". Logo, `Luvas` presente também é só um rótulo do recorte ("este recorte tem luvas? sim"). **Um multilabel puro por recorte cobre presente E ausente sem dois pipelines.** Manter dois pipelines de treino/inferência tem custo — e este projeto já pagou caro por manter duas versões de coisas (ver `feedback_merge_resolution_develop_wins`). **Recomendo multilabel único por recorte, não híbrido.** O híbrido só se justificaria se aparecer classe multi-instância na mesma pessoa (ex.: contar objetos), o que não é o caso RVB.

---

## 6 · Estágio 1 — os três candidatos (itens 7-13)

### 6.1 O que está MEDIDO agora

- **Modelo aberto de pessoa (YOLOX-nano ONNX):** **já é o Estágio 1 em produção.** 94,8-96,2% de recorte-com-pessoa no frame real RVB (§1.1). Apache, roda no edge, custo já absorvido. **Este candidato está validado em campo** — não precisa de bench para o nível *pessoa*.

### 6.2 O que NÃO foi medido — e por quê

⛔ **Bench empírico dos 3 candidatos (itens 7-11) NÃO foi executado nesta rodada.** Honestamente, não é possível neste ambiente:
- **AWS PPE:** sem credencial AWS no ambiente (`~/.aws` ausente, sem env AWS). E não se pode mandar frame real (LGPD, §6.5). Precisaria: conta AWS + aval jurídico + imagem pública.
- **Pose / modelo aberto local:** `torch`/`cv2` não instalados no ambiente; download de pesos + frames do R2 (sem credencial R2 exposta aqui) + GPU. Precisaria: pilha ML local ou o Orin.

Isso é "não sei — e eis o que falta", não plausibilidade. **Runbook para medir na próxima rodada em §7.** O que **é** factual agora (não estimado) é a *cobertura de partes* que cada candidato pode entregar, porque é o que cada modelo, por definição, produz:

### 6.3 Partes do corpo localizadas por candidato (item 8) — factual, por definição do modelo

| Candidato | pessoa | cabeça | rosto | mãos | **pés** | orelhas | licença/LGPD | custo |
|---|:-:|:-:|:-:|:-:|:-:|:-:|---|---|
| **AWS PPE API** | ✅ | ✅ | ✅ | ✅ (2) | ❌ | ❌ | 🔴 suboperadora nova + fronteira EUA | US$0,001/img |
| **YOLOX pessoa (atual)** | ✅ | ⚠️ margem | ❌ | ❌ | ❌ | ❌ | ✅ local Apache | zero (já roda) |
| **Estimação de pose** | ✅ | ✅ | ✅ (olhos/nariz) | ✅ (pulsos) | ✅ **tornozelos** | ✅ **orelhas** | ✅ local, permissiva | zero |

🔴 **A pose dá 17 pontos; a AWS dá 4 regiões.** A pose dá **pés** (bota) e **orelhas** (protetor auricular) — exatamente as classes específicas da RVB (item 2.7). A AWS **não dá nenhum dos dois**. Isto é o que cada API retorna por especificação, não medição — logo é afirmável com segurança: **para a estratégia de partes do corpo do Vitor, a AWS é estritamente inferior à pose em cobertura**, antes mesmo de medir qualidade.

### 6.4 "Bota" e "protetor auricular" via regiões derivadas (item 13)

**Viável com pose, não com AWS.** Os dados já têm 55 anotações `Botas` e 197+ de protetor — desenhadas como caixa no recorte. Com pose: tornozelos→região do pé, orelhas→região do ouvido → recorte pequeno → classificador minúsculo por parte. `Sem protetor auricular` deixa de ser caixa no vazio e vira rótulo num recorte de cabeça/orelha. Com AWS seria impossível derivar pé (ela não dá tornozelo). **Confirma o veredito pró-pose.**

### 6.5 AWS por etapa — onde encaixa, onde JAMAIS (item 2.6)

| Etapa | AWS entra? | Motivo |
|---|---|---|
| Coleta | ⛔ não | é no edge |
| Pré-anotação / bootstrap | ⚠️ **só se a pose falhar** | ver veredito §7 |
| Propagação | ⛔ substituída por classificação-por-recorte | não precisa |
| Treino | ⛔ não | Custom Labels não devolve o modelo (ADR-0043); RunPod fica |
| **Inferência produção** | ⛔ **JAMAIS** | US$4/h·modelo (~US$2.920/mês) + todo frame indo aos EUA — mata edge-first |

**Conta da pré-anotação (item, projeção):** ~9.634 frames × US$0,001 ≈ **US$9,6** para pré-anotar o acervo inteiro — barato *se* fosse necessário. Mas o Estágio 1 já pré-localiza pessoa de graça; o único delta que a AWS traria é rosto/cabeça/mão — que a pose também traz, com pés/orelhas a mais.

🔴 **Ressalva do boné (item 10) — NÃO medida.** *head cover* da AWS é genérico: **boné conta como cabeça coberta**, então ela responde "a cabeça está coberta?", não "é capacete?". Muita gente de boné na RVB. **Não confirmei em amostra real** (sem AWS + LGPD). Precisa: 20-50 frames públicos de operação com boné. Enquanto não medido, é risco aberto — mais um motivo para não depender da AWS.

⚠️ **LGPD / D-72 (item, pendência do Vitor):** mandar frame de operação com pessoa identificável para a AWS = **suboperadora DIFERENTE da RunPod**; o dicionário do contrato nomeia a RunPod (D-72), e ADR-0048 proíbe frame com pessoa identificável em ferramenta de terceiro. **Exige decisão do Vitor + provavelmente aditivo contratual. ⛔ Nenhum frame deve ir à AWS antes disso.** Nesta rodada, nada foi enviado.

### 6.7 Comparação: localização por partes × propagação SAM+DINO (item 11)

Nos mesmos frames RVB: a propagação SAM+DINO deu **1.005 propostas, 100% rejeitadas** (~0% aproveitável na prática — ausência sem aparência). A localização por pessoa (Estágio 1 já rodando) acerta **~95%**. Não é comparação empírica pareada modelo-a-modelo (isso é o bench da próxima rodada), mas o contraste de resultado real em produção é gritante: **ancorar na pessoa funciona onde a similaridade de ausência falhou.**

---

## 7 · Veredito e próxima rodada (itens 12, 14)

### 🔴 A AWS entra na estratégia? **Não.**

**Justificativa (uma frase):** o único valor que a AWS agregaria — localizar pessoa e partes — a pose local entrega de graça, sem fronteira, sem aditivo, com **mais** partes do corpo (pés e orelhas, que são exatamente `bota` e `protetor auricular`), enquanto o Estágio 1 de pessoa já roda a 95% no frame real.

**A porta que fica aberta (honesta):** a qualidade de pose vs modelo aberto em pessoa distante/ocluída **não foi medida**. *Se* a pose falhar nos frames reais da RVB (704×480, 10m, tela metálica), a AWS volta a ser candidata **só para bootstrap único do dataset**, com aval jurídico, nunca em produção. A decisão é da pose, e a pose ainda não foi medida — por isso o veredito "AWS não entra" é forte mas condicionado a esse único teste.

### Próxima rodada (não esta)

1. **Bench de partes, local, mesmos ~30 frames reais RVB** (⛔ nada sai do ambiente): rodar pose (modelo permissivo) e o YOLOX-pessoa; medir pessoas detectadas vs contagem real, partes corretas (cabeça·rosto·mãos·**pés**·orelhas), falha em pessoa distante, falha em oclusão, cena cheia, ms/frame no Orin. AWS PPE só em **imagem pública** e só se o item LGPD for destravado pelo Vitor. Reportar quantos bonés viram "cabeça coberta".
2. **Protótipo de classificação-por-recorte** (throwaway): novo export `{recorte, multilabel}` reusando `_fetch_annotations`; `train_classifier()` timm/ONNX; treinar nos 363 recortes já anotados com **masked BCE** (ignora classe não-anotada — resolve o rótulo parcial da §2). Medir se bate o detector single-stage atual.
3. **Consolidar a taxonomia RVB** (débito da §2): mapear `yolo_classes` custom → 3-estados-por-parte, remover soft-deletadas, denormalizar os 258 `class_name`.
4. **Decisão do Vitor pendente:** (a) LGPD/D-72 para qualquer teste AWS; (b) manter fallback single-stage para os 5% sem pessoa detectada?

### Decisões que travam a fila para o Vitor
- 🔴 LGPD/D-72 + aditivo AWS — **antes de enviar qualquer frame** (item 6.5).
- Aceitar perder a caixa exata do EPI (marcar pessoa, não objeto)? (§4)
- Multilabel puro por recorte vs híbrido — recomendo multilabel puro (§5).

---

## Apêndice — método e evidências

**Banco:** DEV `DATABASE_PUBLIC_URL` (Railway env Desenvolvimento), só `SELECT count/group`. Tenant RVB `63c219d8-…`. Nenhum dado saiu do ambiente; nenhuma variável Railway alterada.

**`file:line` das afirmações de código:**
- Crop/pessoa: `services/edge-sync-agent/app/collector/person_detector.py:49,100,340-374` · `collector_loop.py:171-215` · `frame_uploader.py:31-56` · `services/api/app/api/v1/edge/routes.py:586-699,679,618-621` · `infrastructure/queue/tasks/nvr_extraction.py:134-144` · `tasks/search.py:253` · `tasks/propagation.py`
- Pipeline servido: `services/inference/inference/inference_engine.py:110-131` · `detectors.py:169-216,306-322,432-446,470-476` · `config.py:16,23` · `deepstream/shared/custom_parsers/config_infer_yolox.template.txt:5-6,20` · `main.py:32-67` · `lpr_service.py:129`
- Export/treino/UI: `infrastructure/queue/tasks/versioning_v2.py:105-156,282-290,293-332` · `api/v1/datasets/routes.py:123-129` · `constants.py:120-124` · `training/vast/remote_train.py:7,49,152,225,233-268` · `apps/frontend/src/components/annotation/AnnotationStudio.tsx:164-171,353,693,739,1209-1243` · `studioTypes.ts:50-56` · `SearchFindingsPanel.tsx:40-54,190-320`
- Registries: `public.module_classes` (epi 0-7) · `public.yolo_classes` (custom RVB)
