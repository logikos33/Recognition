# Lições de engenharia do repo AWS PPE (dois estágios) — o que ele resolve bem que nós ainda não

- **Tipo:** Análise de referência externa → decisões registradas (NÃO é ADR; alimenta o `REGISTRO_DE_DECISOES.md`)
- **Data:** 2026-08-16 · **Escopo:** somente DEV/documentação · **Módulo:** EPI · **Tenant:** RVB
- **Garantias:** zero linha de código de produto alterada · nenhum frame saiu do ambiente · não toca `staging`/`main`/`interchange`
- **Repo lido:** `github.com/aws-samples/amazon-rekognition-custom-ppe-detection-with-custom-labels`
- **Pergunta desta rodada:** aquele repo é uma implementação de referência de **dois estágios** — a arquitetura que já adotamos. *O que ele resolve bem que nós ainda não?* ⛔ **NÃO** é "adotar AWS" (fechado 2×).

---

## 0 · Divergências entre o prompt e o repo real (segui o repo)

| O prompt dizia | O repo/git diz | Segui |
|---|---|---|
| `docs/decisions/AVALIACAO_REKOGNITION_PPE_NO_FLUXO.md` existe | É arquivo **não-rastreado**, presente só no checkout local `develop`; **ausente de `origin/develop`**. O que está commitado (155a966) é a 2ª avaliação, mais rica: `avaliacao-dois-estagios-classificacao-por-recorte.md` | Baseei em `origin/develop`; li os dois |
| `person_detector.py:340` / `components/annotation/SearchFindingsPanel.tsx` | Caminhos reais: `services/edge-sync-agent/app/collector/person_detector.py:340` e `apps/frontend/src/components/annotation/SearchFindingsPanel.tsx:44` — ambos confirmados | Confirmado |
| (implícito) `develop` está atual | `develop` local está **21 commits atrás** de `origin/develop` (PR #382). Worktree criado de `origin/develop` @ b1e7682 | origin/develop |
| Repo AWS = detector de EPI da AWS | 🔴 O repo nomeado é a variante **Custom Labels (treine o seu classificador vest/novest)**, **não** a API gerenciada `DetectProtectiveEquipment` (3-de-5 classes) que a 1ª avaliação criticou. **São produtos diferentes.** Este repo espelha nossa própria aposta — "cada cliente treina o próprio modelo" — então as lições são de **fluxo**, não de cobertura de classe da API | Reenquadrado |

Checagens dos "fatos conhecidos" do prompt: SAM+DINO = 1005 propostas, 100% rejeitadas ✓ · YOLOX-nano ~96,2% em frame real 704×480 ✓ · taxonomia: `module_classes` do EPI tem 8 (4 pares present/absent), taxonomia **tenant** RVB = 6 ✓.

---

## 1 · Padrões extraídos do repo (o que é transferível vs específico da AWS)

| Eixo | O que o repo faz | Transfere? |
|---|---|---|
| **2 estágios** | Estágio 1 detecta pessoa e devolve bbox → recorta em pixels → Estágio 2 classifica **o recorte inteiro** como `vest`/`novest` + confiança → funde de volta em `HasVest{Value,Confidence}` (`source/api/lib/index.js:397-438`) | ✅ padrão |
| **Preparo do dataset** | Sobe imagem cheia → auto-recorta cada pessoa → humano **arrasta cada recorte** para a zona `vest` ou `novest`. "Estruturado": já sobe recortado. Split: 20% automático | ✅ o fluxo; ⛔ o split random (nós somos melhores) |
| **Ausência** | 🔴 **`novest` é uma CLASSE cheia**, rotulada por-recorte — não "negativo" nem "não-anotado". Mín. **10 imagens/classe**. Viável **porque a UI força um veredito por recorte**: nada entra no treino meio-rotulado | ✅ a lição-chave |
| **Rotulagem** | **Por-recorte (nível-imagem)**: 1 recorte de pessoa = 1 rótulo. Zero anotação de caixa dentro da imagem. UI de 3 zonas (Unlabeled/Vest/NoVest) | ✅ padrão |
| **Avaliação** | F1/precision/recall automáticos do Custom Labels; **limiar não é exposto** (caixa-preta gerenciada); "pronto" = decisão manual | ⛔ nada a aprender (esconde o limiar) |
| **Ciclo de vida** | Versão = ARN com timestamp; retreino = nova versão; **sem detecção de drift** | ⛔ nós já fazemos melhor |
| **Front de revisão** | Overlay de caixas+rótulo+confiança na análise; **nenhum loop de aprovar/rejeitar/corrigir** | ⛔ nós já temos fila de verificação |
| **Infra** | Serverless **síncrono, SEM fila, SEM banco, SEM state-machine**. Lambda recorta e classifica pessoas **em paralelo** (`Promise.all`, `index.js:400-436`); estado só em S3 + ARN | ⚠️ a **minimalidade** transfere; Cognito/API-GW/Custom-Labels não |

**Não-transferível (dependência de serviço AWS):** Rekognition Custom Labels (treino gerenciado, **não exporta o modelo** → colide com ADR-0043), DetectLabels, Cognito, CloudFormation, S3 Transfer Acceleration.

---

## 2 · Comparação com o que JÁ temos (`file:line` do nosso código)

| Padrão | Nós | `file:line` | Melhor/pior que o repo |
|---|---|---|---|
| Estágio 1 (recortar pessoa) | ✅ JÁ, em produção no edge | `services/edge-sync-agent/app/collector/person_detector.py:340-374` | **par** — e temos acurácia medida em campo (95-96%) |
| Estágio 2 servido | 🟡 PARCIAL — dobrado num detector **single-stage**; não há 2º modelo servido | `services/inference/inference/detectors.py:169-216` · `inference_engine.py:110-131` · `config.py:23` | **pior** — o repo separa; recorte→classifica é mais limpo em cena cheia |
| Split do dataset | ✅ JÁ por `video_id` > `camera+dia` > `frame` | `.../queue/tasks/versioning_v2.py:175` | 🟢 **melhor** (repo é random 20% → vaza) |
| Ausência | 🟡 PARCIAL — hoje é **classe de detecção** (`no_helmet`…) + rótulos **parciais** (273/363 recortes só-positivo) | `infra/migrations/009_module_classes.sql:20-28` · doc dois-estágios §2 | **pior** — "caixa da ausência" vs classe-por-recorte da AWS |
| Granularidade do rótulo | 🟡 **por-caixa** | `apps/frontend/src/components/annotation/SearchFindingsPanel.tsx:44-60` | **diverge** — AWS é por-recorte (devíamos migrar) |
| Limiar de confiança | ✅ JÁ por-zona (env `DETECTION_CONFIDENCE_THRESHOLD`=0.5) | `services/inference/inference/config.py:17` · `apps/frontend/.../ZoneTuningForm.tsx:71` | 🟢 **melhor** (AWS esconde); falta per-classe |
| Avaliação entre versões | ✅ JÁ — `evaluate_challenger_model` computa map50/precision/recall em holdout e **gateia o modelo ativo pelo veredito** | `.../queue/tasks/model_evaluation.py:181` · `domain/models/training_job.py:10-63` | 🟢 **melhor** (AWS é manual, sem automação) |
| Loop de revisão/correção | ✅ JÁ — fila `needs_human`, aprovar/rejeitar | `apps/frontend/src/pages/VerificationQueuePage.tsx` · `api/v1/verification/routes.py` | 🟢 **melhor** (AWS não tem) |
| Meta de dados/classe (100×5×≤50%) | ❌ NÃO computada | `docs/PLANO_500_FRAMES.md` (só doc) | par-pior, **mas o repo também não ensina** (só mín-10) |

---

## 3 · As 5 perguntas prioritárias — respondidas ("não achei" é resposta válida)

**Q1 — Como tratam a AUSÊNCIA?** → `novest` é **classe cheia por-recorte** (≥10 exemplos), viável **porque a UI força um veredito completo por recorte** (arrasta pra vest OU novest; nada meio-rotulado entra). 🔴 **É o achado mais valioso:** a cura da ausência não é um modelo de propagação mais esperto (SAM+DINO deu 1005/100%-rejeitadas) — é um **fluxo de anotação que exige um veredito definitivo por recorte**. Bate exatamente na nossa dor medida (273/363 recortes só-positivo → não dá pra fabricar negativo). O doc dois-estágios já aponta pra cá (masked BCE); o repo prova a direção **e** entrega a UX concreta.

**Q2 — Quanto dado por classe?** → Piso duro **10/classe** + auto-F1; **sem base principiada** além disso. Nossa meta 100×5×≤50% (derivada por raciocínio) é **mais rigorosa** que a referência. **Não achei** base melhor lá. O gap real é que **não computamos** cobertura — mas o repo não ensina a computar; fica fora desta rodada.

**Q3 — Como escolhem o limiar?** → **Não expõem** — caixa-preta gerenciada, confiança crua devolvida, decisão a jusante. **Referência não oferece padrão de limiar.** Nós já fazemos melhor (por-zona). Limiar per-classe é melhoria possível, mas **não motivada pela referência** → baixa prioridade.

**Q4 — Rótulo por caixa ou por recorte?** → **Por recorte** (nível-imagem), 1 recorte = 1 rótulo. Confirma independentemente a recomendação do doc dois-estágios. **Lição transferível mais limpa**, e barata: o scaffold grade-de-recortes + seletor + promover já existe em `SearchFindingsPanel`.

**Q5 — Como medem melhora entre versões?** → **Manual**, F1/precision/recall por versão, sem automação, sem drift. **Nós já fazemos melhor** (`evaluate_challenger_model` automatizado gateando o modelo ativo). Nada a aprender aqui.

> Só **Q1** e **Q4** rendem lição adotável. Q2/Q3/Q5: referência silenciosa ou nós à frente. (Filtro honesto — não inflei.)

---

## 4 · Recomendações — só o que ancora numa dor medida (3, não 10)

| # | O quê | Por que importa AQUI (dor medida) | Esforço | Colide? | Veredito |
|---|---|---|---|---|---|
| R1 | **Estágio 2 = classificação multilabel por RECORTE** (valida o doc dois-estágios com a impl. de referência) | Ausência + velocidade de anotação; servido é single-stage (`detectors.py:169`) | G | doc dois-estágios §7 | 🟡 adotar adaptado |
| R2 | **Anotação com veredito por-recorte forçado** para ausência (lição das 3-zonas, adaptada; reusar `SearchFindingsPanel:44`) | 273/363 recortes só-positivo → negativos infabricáveis; propagação 100% rejeitada | M | estúdio de anotação (área ativa) | 🟡 adotar adaptado |
| R3 | **Orquestração do Estágio 2 mínima e síncrona** (loop recorta→classifica em paralelo; **sem fila/state-machine/banco novo**) | O projeto já pagou caro por manter complexidade duplicada; o repo mostra que 2 estágios cabem num loop síncrono | P | — | ✅ adotar (guardrail) |

**Ficaram de fora, de propósito** (não ancoram numa dor que a referência ajude): dashboard de cobertura (Q2 — dor real, mas o repo não ensina), limiar per-classe (Q3 — referência esconde limiar), detecção de drift (Q5 — já à frente). Registrar que **não** entram evita a redescoberta.

---

## 5 · Decisões (registradas em `docs/REGISTRO_DE_DECISOES.md`, D-107..D-111)

- **D-107** 🟡 **adotar adaptado** — Estágio 2 = multilabel por recorte. Protótipo/export **pode começar já** (363 recortes anotados). Servir no edge ⏸️ **adiado até**: FPS do Estágio 2 medido no Orin mantendo 28 cams + folga.
- **D-108** 🟡 **adotar adaptado** — fluxo de anotação com **veredito por-recorte forçado** por classe (present/absent/N-A) antes do recorte contar como rotulado; reusa `SearchFindingsPanel`. É a resposta de ausência. Preferível ao masked-BCE-sobre-parcial (dá negativo limpo); masked BCE fica de fallback.
- **D-109** ✅ **adotar** (guardrail) — quando o Estágio 2 for servido, manter **loop síncrono recorta→classifica**; ⛔ não introduzir fila/state-machine/tabela nova. A lição de infra do repo é minimalidade.
- **D-110** ⛔ **não adotar** — Custom Labels / qualquer inferência ou **treino** servido pela AWS. O repo, apesar de "treine o seu", **não exporta o modelo** (colide ADR-0043) e serve a US$4/h. Reafirma decisão já fechada 2×; o treino por-recorte é local (RunPod/Vast).
- **D-111** ⛔ **não adotar** — o esquema **binário 1-classe-por-recorte** (vest/novest) do repo. Nosso problema é **multilabel multi-parte** (6 classes tenant, até 3 estados por parte); copiar o fluxo binário quebraria o schema de rótulo. **Não-transferível.**

---

## Apêndice — método

Leitura do repo externo e inventário do nosso código em subagentes (síntese, sem despejo de arquivo). Julgamento e vereditos consolidados aqui. Fontes de código citadas por `file:line` acima; nada foi enviado a terceiro; nenhum frame saiu do ambiente.
