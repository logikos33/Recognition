# Relatório de correções — rodada de 25/08/2026

**Branch:** `feat/proposta-proveniencia` · **Ambiente:** DEV · **Modo:** shadow, dashboard-only
**⛔ Nenhum canal de notificação foi ativado.** Nenhum alerta saiu para pessoa nenhuma.

---

## 0 · Sanidade do DEV

`GET /livez` → **200**, `running_jobs: 0`. Migration de polaridade (125) aplicada. Sem regressão do
deploy anterior. Seguiu-se para os defeitos.

---

## 1 · Defeitos de tela

### A) "Todos os alertas como falso"

**Causa provada — e é pior que a hipótese.** A hipótese principal era que a tela mostrava a
POLARIDADE no lugar do VEREDITO. A medição mostrou duas coisas, nenhuma delas isso:

**A1. No EPI, o veredito humano era INGRAVÁVEL por construção.**

| medição | resultado |
|---|---|
| alertas com `verification_verdict` preenchido | **0 de 334** (todos NULL, status `pending`) |
| chamadores de `submit_for_verification` no repositório | **zero** (grep repo-wide) |
| cláusula do `human_review` | `AND verification_status = 'needs_human'` |

A coluna nasce `'pending'` (migration 016), nada nunca a promove a `'needs_human'`, e o WHERE do
review exigia exatamente esse valor. **Toda tentativa de registrar veredito devolvia 404** — não
era dado faltando, era caminho inexistente. A tela `/epi/verification` lista só `needs_human`, ou
seja, está permanentemente em "fila vazia".

**A2. A única palavra "Falso" do produto vem de uma tela que INVENTA o veredito.**

Busca exaustiva em todo `apps/frontend/src` e `apps/landing/src`: existem 3 ocorrências visíveis de
"Falso", **todas do módulo Qualidade, nenhuma do EPI**. E `QualityInspectionsPage` é demonstração:

```ts
const feedbacks = ['pending','pending','pending','confirmed','confirmed','rejected']
feedback_status: feedbacks[Math.floor(Math.random() * feedbacks.length)]
```

1 em cada 3 linhas exibia um julgamento que ninguém deu. Pior: o sorteio era independente do
`result`, então saíam linhas **"OK + Rejeitado"** — rejeitado o quê? E `saveFeedback()` é um
`setTimeout(500)` que escreve em estado local: o veredito do operador nunca saía do browser.

**A3. Achado estrutural que muda o desenho.** `alerts.verification_verdict` é escrita pelos DOIS
lados com o MESMO vocabulário `approve`/`reject`: pela IA (`verified_by='claude-haiku'`) e pelo
humano (`verified_by='user:<id>'`). **A coluna do veredito não sabe dizer se quem julgou foi
gente.** Qualquer tela que leia só o verdict e escreva "veredito humano" passa a mentir no instante
em que a task Celery rodar.

**Correções:**
1. `human_review` deixou de exigir `needs_human` — veredito vale para qualquer alerta do tenant, e
   acontece na tela de detalhe, não numa fila que nunca enche. `tenant_id` continua no WHERE
   (cross-tenant → rowcount 0 → 404, C-01).
2. A demo de Qualidade nasce toda `pending`. Demo pode simular **detecção**; não pode simular
   **julgamento**.
3. **Separação definitiva dos dois conceitos** — componente `VereditoHumano.tsx`:

| | o que é | vocabulário | paleta | onde |
|---|---|---|---|---|
| **Polaridade** | o que o EVENTO é | Violação / Conformidade | verde / vermelho | coluna "Evento" |
| **Veredito** | o que a PESSOA julgou | Procedente / Falso positivo | azul / âmbar | coluna "Veredito humano" |

   Terceiro estado explícito: **"Não revisado"** — *"Ninguém julgou este alerta ainda. Não é o mesmo
   que falso."* A ausência de veredito era exatamente a confusão. A prova de humanidade é o prefixo
   `user:` em `verified_by`: sem ele a tela diz "Não revisado", mesmo com verdict preenchido pela IA.
   Zero migration.

**Teste de mutação:** `AlertsVereditoVsPolaridade.test.tsx` falha se alguém puser `danger` em
falso-positivo (veredito e violação virariam a mesma cor na mesma linha) ou se o prefixo `user:`
deixar de ser exigido.

**Prova ponta a ponta, contra o DEV real, cruzando a fronteira HTTP** (não teste de unidade —
`POST /api/verification/<id>/review` na API do DEV, com a API já deployada desta branch):

| chamada | resposta |
|---|---|
| veredito `approve` num alerta real do RVB | **200** |
| veredito `reject` no mesmo alerta (re-revisão) | **200** |
| mesma rota num alerta de outro tenant | **404** (nunca 403 — C-01) |

E o que ficou no banco:

```
verification_status | verification_verdict | verified_by
human_rejected      | reject               | user:11111111-0000-0000-0000-000000000002
```

O prefixo `user:` está lá — a prova de humanidade funciona, e a re-revisão sobrescreveu o veredito
anterior como projetado. **Antes desta rodada, essa mesma chamada devolvia 404 para 100% dos
alertas.**

⚠️ O alerta `2b78273c…` ficou com um veredito de teste desta prova. É o único; os outros 333
continuam sem veredito.

**Defeito que a prova revelou:** `verification_reason` voltou **vazio**. A rota aceitava `reason` no
corpo e o descartava em silêncio — o UPDATE não tinha a coluna, embora ela exista desde a migration
016. É a informação que alimenta a recalibração de limiar depois ("errou porque a caixa pegou a luva
do colega ao lado"): sem ela, um falso positivo diz QUE errou e nunca POR QUE. Corrigido no mesmo
dia (`9f8e57f9`), com `reason` vazia gravando NULL e não string vazia — "não justificou" e
"justificou com nada" não são a mesma coisa numa consulta.

**Vereditos do Vitor foram corrompidos?** Não. Nunca houve nenhum gravado — os 334 estão NULL. Não
há nada a reprocessar.

**Prova NA TELA** (front local contra a API do DEV, sessão autenticada). Colunas do histórico de
alertas depois do conserto:

`Data | Câmera | Evento | Confiança | Veredito humano | Reconhecimento | Ação`

| coluna | o que mostra | exemplo | cor |
|---|---|---|---|
| **Evento** | polaridade | `▲ Violação — Sem protetor de ouvido` | vermelho |
| **Veredito humano** | julgamento | `PROCEDENTE` / `FALSO POSITIVO` / `NÃO REVISADO` | azul / âmbar / cinza |
| **Reconhecimento** | fluxo de trabalho | `Reconhecido` | verde |

Contagem na página, depois de eu aprovar um alerta **pela própria tela**: **1 PROCEDENTE · 1 FALSO
POSITIVO · 18 NÃO REVISADO**. O clique em "Procedente" gravou no banco com a prova de humanidade
(`verified_by = user:11111111-…`, `human_approved`). Nada aparece como falso a menos que uma pessoa
tenha dito — que era exatamente a queixa.

**Achado de segurança no caminho (corrigido):** `AlertRepository.acknowledge()` fazia
`UPDATE alerts SET acknowledged = TRUE WHERE id = %s`, **sem `tenant_id`** — escrita cross-tenant
(C-01). E era disparável **sem clique**: a lista armava `setTimeout(1000)` no `onMouseEnter`, então
passar o mouse por 1 segundo reconhecia o alerta. As duas coisas saíram.

### B) Zoom na evidência — feito

Lupa em `AlertDetailPage`: roda do mouse, duplo clique e arrasto (Pointer Events, unifica
mouse/toque). A caixa fica **ancorada e escala junto** porque `<img>` + caixas vivem numa única
camada transformada — as caixas já são `%` da imagem, então `boxStyle()` não mudou uma linha, e os
testes de deep-link que afirmam `left === '12.5%'` continuam valendo.

Sem biblioteca nova: `framer-motion` (já instalada) resolve arrasto, não zoom ancorado no cursor.
Reusou-se a fórmula de âncora do `AnnotationStudio` — mas **não** o buraco dele: o estúdio não
limita o pan, e arrastar a 2× joga a imagem para fora do palco. Aqui o limite fecha em fórmula:
`|x| ≤ largura·(escala−1)/2`. Verificado em 50.000 eventos aleatórios: **0 violações de âncora em
23.491 zooms**; ao afastar, o limite vence a âncora em 11.710 de 23.657 casos — reenquadrar é o
comportamento certo (senão abre faixa vazia) e virou teste explícito.

`bbox_unidade` continua sendo o único portão de desenho: a lupa não amplia caixa que a tela não
sabe projetar.

### C) Caixas longe da demarcação do treino

**🔴 Causa raiz encontrada, e não era o modelo — era o dado.**

| | anotações | com área ≥95% do frame | % |
|---|---:|---:|---:|
| `source='manual'` | 4.629 | **1.095** | **23,7%** |
| `source='pre_annotation'` | 2.853 | 3 | 0,11% |

As 1.095 são **exatamente** `cx=0,5 cy=0,5 w=1 h=1` — constante, não mão humana — espalhadas em
**420 frames que não têm nenhuma outra caixa**. Origem: `CropClassifier.tsx:82`,
`FULL_FRAME_BBOX = [0,0,1,1]`, um placeholder que o próprio arquivo documenta ("ainda não existe um
detector de 'pessoa' dedicado no backend"). A aba Classificar responde *"este frame mostra a classe
X?"* — pergunta de **classificação** — mas gravava o veredito em `frame_annotations` com
`source='manual'`, o mesmo endereço de uma caixa desenhada à mão. **Um quarto do dado humano
ensinava que "Protetor auditivo" é a imagem inteira.** Issue #538.

**Correção:** corte na fonte (`_fetch_annotations` / `build_dataset_version_v2`), o único lugar por
onde todo dado de treino passa. Nenhuma linha é apagada — o rótulo continua valendo como
classificação, só não entra no treino de localização.

**Invariante que isso obrigou a generalizar:** um frame que perde todas as caixas por FILTRO sai do
dataset. Mantê-lo com zero caixas ensina o detector a **não ver** o que está ali — pior que
descartá-lo. Frame que nunca teve caixa alguma no banco é negativo legítimo e fica (3 no RVB).

**O que a invariante revelou:**

| dataset | frames |
|---|---:|
| `v14-tudo` (toda anotação humana ou proposta revisada) | 4.977 |
| `v14-so-humano` (só o que a mão desenhou) | **2.362** |

**53% dos frames do dataset carregam apenas geometria desenhada pelo MODELO.** Aceitar uma proposta
com uma tecla confirma a CLASSE e herda a CAIXA — é o auto-envenenamento do #536, agora com número.

#### v12/#536 — estado honesto

O experimento **não fechou nesta rodada**, e a razão é que ele estava sendo montado errado. Três
confundidores foram encontrados e corrigidos antes de valer a pena treinar:

| # | confundidor | como apareceu | correção |
|---|---|---|---|
| 1 | base crescendo durante o experimento | `v12-so-humano` tinha MAIS frames (5.399) que o controle (5.297) — o Vitor estava revisando: 251 revisões e 282 anotações na última hora | exports pareados, disparados juntos |
| 2 | 1.095 caixas de frame inteiro nos DOIS braços | medição acima | corte na fonte |
| 3 | **partições diferentes** | a semente inclui o nome da versão; no v13 os braços caíram em 3.995 e 2.772 frames de treino — a comparação mediria o SORTEIO | parâmetro `split_seed` |

**E aí uma régua rodada sobre o COCO real, antes de gastar GPU, reprovou o v14 e achou mais dois.**
A régua confere cinco coisas no arquivo que o treino vai ler, não no que o código promete.

| verificação | v14-tudo | v14-so-humano |
|---|---|---|
| [1] caixas cobrindo o frame | **0** ✅ | **0** ✅ |
| [2] imagens sem caixa | 3 (os negativos deliberados) ✅ | 3 ✅ |
| [3] vazamento entre splits | nenhum ✅ | nenhum ✅ |
| [4] frames comuns em split IGUAL | 🔴 **1.701 de 2.362 divergiram** | |
| [5] mapa de categorias | 11 classes 🔴 | 12 classes |

| # | confundidor | como apareceu | correção |
|---|---|---|---|
| 4 | **`split_seed` não bastava** | `_split_by_group` decide por POSIÇÃO numa lista embaralhada dos grupos **presentes** — mude a população e a mesma semente dá outra atribuição. Estrago real: `Sem protetor de ouvido` ficou com MAIS caixas de treino no braço **podado** (337) que no completo (294); `Uso incorreto de mascara` 148 contra 112. E o campo duplamente virgem encolheu para **111 frames**, com interseção de apenas **5** entre os dois testes | atribuição por `sha256(seed, chave_do_grupo)` mapeada nas fronteiras de proporção — qualquer subconjunto herda a mesma decisão por construção |
| 5 | **espaços de saída diferentes** | a classe `Capacete` tem **1 caixa no mundo inteiro**; caiu no train de um braço e fora do outro, deixando os modelos com 11 e 12 classes | resolvido pelo #4: com partição estável a classe cai no mesmo split nos dois |

O teste novo prova a propriedade certa: poda 20% da população e exige **zero** divergência de
atribuição. `sha256` e não o `hash()` embutido — este é salgado por processo e daria split diferente
a cada worker.

| 6 | **dois braços não bastam** | o braço só-humano tem 2.362 frames contra 4.977. Se ele perder, foi a geometria herdada do modelo **ou** simplesmente treinar com metade do dado? As duas leituras levam a decisões opostas, e o desenho de dois braços não consegue separá-las | terceiro braço `v15-controle`: os MESMOS frames do só-humano, com TODAS as caixas. `só-humano × controle` isola a geometria com volume constante; `só-humano × tudo` continua sendo a decisão real de embarque. Custa US$ 0,34 |

Os três datasets `v15-*` foram construídos com os seis consertos e **passaram na régua**. Os dois
braços do A/B (`v15-tudo` e `v15-so-humano`) estão **treinando** — RF-DETR base, 50 épocas,
imgsz=560, RTX 4090, com zero pods vivos verificado antes do disparo.

Custo de ter parado seis vezes antes de gastar GPU: **US$ 0**. Treinar em qualquer um dos seis
estados anteriores teria produzido um veredito falso sobre uma regra que vai reger todo o treino do
produto daqui pra frente.

### Auditoria adversarial antes da GPU — 42 agentes, 38 alegações, 7 sobreviveram

O desenho do experimento foi submetido a quatro lentes independentes (partição, espaço de classes,
isolamento do tratamento, protocolo de medição) e cada alegação passou por um refutador cético,
instruído a marcar "não é problema" na dúvida. Das **38 alegações, 31 caíram** — incluindo teses
sedutoras como "o hash troca proporção exata por ruído binomial", "a chave de grupo depende do fuso
do worker" e "o mesmo `category_id` significa classe diferente nos dois braços". Ficaram **7**.

**A mais grave foi refutada por medição minha, não por argumento.** Um auditor concluiu que nem o
v14 nem o v15 rodaram o código corrigido, porque "a branch é local e o DEV deploya da develop".
Está errado neste caso — o deploy foi `railway up` sobre um `git archive` do commit — e a régua
prova: **zero divergência de partição** nos três pares de braços do v15, sobre 2.362 frames comuns
cada. O auditor, aliás, especificou o teste certo ("comparar a atribuição por chave de grupo"), e é
exatamente ele que passou.

**Régua do v15 — aprovada:**

| verificação | v15-tudo | v15-so-humano | v15-controle |
|---|---|---|---|
| caixas cobrindo o frame | 0 | 0 | 0 |
| imagens sem caixa | 3 (negativos deliberados) | 3 | 3 |
| vazamento entre splits | nenhum | nenhum | nenhum |
| partição comum divergente | **0** de 2.362 | **0** | **0** |
| mapa de categorias | 12 | 12 | 12 |
| campo virgem para todos | **717 frames** (era 111 no v14) | | |

**Os 3 achados confirmados que mudaram o que eu ia fazer:**

1. **🔴 A régua de avaliação premiava o tratamento.** 40% da verdade do campo virgem foi desenhada
   pelo MODELO (caixa de proposta aceita). Medir o braço `tudo` ali é medi-lo contra caixas do
   próprio ancestral. **Corrigido:** o campo passou a ser o `test` do braço só-humano — 289 frames,
   403 caixas, todas de mão humana por construção, e (pela partição estável) no `test` dos dois
   braços, portanto virgem para os dois.

2. **🔴 O limiar cravado escolhe o vencedor.** Dois modelos com calibrações diferentes trocam de
   lugar só de mexer no corte, e o arnês antigo usava 0,35 fixo enquanto produção usa 0,25–0,30 por
   classe. **Corrigido:** varredura de limiar, com o melhor de cada modelo reportado.

3. **🔴 O prior de classe muda junto com o braço** — o propositor não propõe classe de ausência,
   então média agregada mistura "melhorou" com "mudou a mistura". **Corrigido:** veredito por
   classe, com o `n` de verdade ao lado. ⛔ Não decidir pelo agregado.

**E um conselho de desenho que foi aceito:** o terceiro braço (volume igualado) virou **condicional**
em vez de obrigatório. O confundidor de volume é assimétrico — se o só-humano vencer **com metade do
dado**, o volume estava contra ele e a direção do veredito sobrevive sem braço nenhum; só se o
`tudo` vencer é que volume vira explicação rival e o braço se paga. Economiza um pod e ~80 min de
relógio sem perder rigor.

**O desenho que responde a pergunta CAUSAL (para a próxima rodada, especificado):** como as
populações são disjuntas, o único par que isola geometria é sintético — rodar o propositor sobre os
mesmos 2.362 frames humanos (um passe de inferência, zero treino) e treinar um braço em que a caixa
do modelo SUBSTITUI a caixa da mão, mesmos frames, mesmo split, mesmas classes. Aí a única variável
é a geometria.

### 🔴 E um 7º achado, confirmado por medição minha: o braço "só-humano" não estava limpo

Um auditor alegou que 403 caixas `source='manual'` são cópia geométrica exata de propostas do
v9/v10. **O refutador dele marcou como não-problema. Eu fui medir e a alegação está certa** — o
primeiro teste meu não casou nada porque comparei como se a proposta guardasse canto superior
esquerdo, e ela guarda `cx,cy,w,h`. Com a convenção certa:

| origem da geometria | caixas `source='manual'` |
|---|---:|
| `v10_base_vencedor.onnx` | 195 |
| `v9_best.onnx` | 187 |
| `propositor_best.onnx` | 17 |
| `propositor.onnx` | 4 |
| **total** | **403** (em 365 frames) |

**Mecanismo:** `save_batch` faz `DELETE` de todas as linhas do frame e reinsere com
`source='manual'` cravado. Abrir o estúdio num frame de proposta aceita e salvar — **sem tocar em
nada** — converte geometria do modelo em "desenhada por humano". O gate de procedência do treino
decide exatamente por esse campo.

**Efeito no experimento em curso:** o braço `só-humano` carrega **11,4%** de geometria do modelo. O
viés aponta **contra** a hipótese (aproxima o braço podado do completo), então:
- **só-humano vencer → veredito conservador e confiável**, o efeito real é maior que o medido;
- **empate ou derrota → ambíguo**, e pede repetição sobre o dado corrigido.

**Corrigido nos dois lados** (`e898817d`): o save fotografa as linhas antes do DELETE e devolve a
proveniência a toda caixa cuja geometria voltou idêntica — a definição de "o humano não tocou".
Caixa movida, redimensionada, de classe trocada ou nova entra como `manual`, que é o certo. E as
colunas da migration 124 (`proposal_batch_id/model_id/confidence`), que existiam e nasciam sempre
vazias, passam a sobreviver ao save. No dado do DEV, as 403 voltaram a `pre_annotation` com
`reviewed_by` preenchido — a caixa é do modelo, mas a aprovação é humana; sem `reviewed_by` elas
sairiam dos DOIS braços em vez de um. Nenhuma linha apagada.

**Número corrigido:** a geometria genuinamente desenhada à mão no RVB são **3.131 caixas**, não
3.534.

### Dois achados durante o próprio treino

**8º confundidor: o job mentiu sobre o próprio esforço.** O braço só-humano fechou com
`current_epoch = 50` e `metrics.epochs_ran = 17`. Ele parou cedo (`early_stopping_patience=8`) e o
50 — o contador cru do framework, que sobe e desce (#420) — chegou num callback anterior e
sobreviveu, porque a guarda existente só recusa `epoch > total` e 50 == 50 passa.

Não é cosmético: o A/B compara dois treinos, e esse campo diria *"um rodou 50 épocas, o outro 17"*
quando na verdade os dois pararam onde a validação empacou, sob a MESMA política. Erro de leitura
com veredito em cima. Corrigido (`0dcab375`): no callback de `completed`, `epochs_ran` passa a ser a
fonte.

**Erro meu de método, pego no ensaio da régua.** Eu havia escrito o critério de "melhor limiar" como
*maior precisão* — e precisão cresce monotonicamente com o corte, porque prever MENOS erra menos.
Medido no ensaio: em 0,60 o v15-so-humano teve precisão de localização 0,65 com **81 predições para
403 caixas reais** — recall de 13%. **A régua elegeria o modelo que se cala.** Trocado para F1, com
precisão e recall lado a lado na curva inteira.

### 🔴 Uma regressão minha, e uma prova que era falsa

Ao consertar a proveniência (`e898817d`), o snapshot que lê a linha antes do `DELETE` indexava por
POSIÇÃO — `r[0]`, `r[5:]`. O pool da API é criado com `cursor_factory=RealDictCursor`
(`connection.py:61`): cada linha é um **dict**, e indexar por posição levanta `KeyError`. **Toda
gravação de anotação passou a devolver 500.**

O teste de unidade não pegou porque o duplê devolvia **tupla**. Duplê que não imita o driver de
verdade testa a si mesmo.

E o pior: a minha própria prova ponta a ponta **deu falso positivo**. Salvei um frame de proposta
aceita sem tocar em nada, li de volta, e os dois boxes ainda estavam `pre_annotation` — o que eu
teria lido como "funcionou". Só não funcionou: o `POST` voltou **500** e a proveniência sobreviveu
porque **o save falhou antes de escrever**. A verificação só valeu porque eu olhei o código de
status, não apenas o estado final.

**Impacto real: nenhum.** Zero anotações foram gravadas na hora e meia anterior — o Vitor havia
parado de anotar. E o 500 é rollback: nada ficou escrito pela metade. Mas a janela existiu, e ela
teria derrubado os saves dele se estivesse trabalhando.

Corrigido nos dois lados (`c5413516`): acesso por NOME de coluna no repositório, e o duplê do teste
devolvendo dicionário como o `RealDictCursor` devolve.

### Dois achados de infraestrutura no caminho

**O 403 da RunPod não era da chave.** A guarda de "zero pods vivos" tomou 403 e a leitura óbvia foi
credencial revogada — a chave do Railway e a local são a mesma, e as duas falhavam. Medido: o
GraphQL fica atrás de Cloudflare, que responde `403 error code: 1010` a requisição **sem
User-Agent** — inclusive **sem autenticação nenhuma**. A REST v1 respondeu 200 com a mesma chave no
mesmo instante. A rotação da chave está adiada por decisão do Vitor e **quase foi mexida por causa
de um erro que não era dela**. `User-Agent` explícito no cliente (`5c89ae85`): hoje `requests` manda
o dele por padrão e produção não estava afetada, mas o caminho que estima o **teto de custo** não
deve depender de um default de biblioteca.

**Redeploy do worker mata export em voo, em silêncio.** `railway up -s celery-worker` com um
`build_dataset_version_v2` rodando derruba a task: nenhuma ativa, nenhuma reservada, e a linha fica
presa em `building` para sempre — sem erro, sem log de falha, sem retry. Aconteceu duas vezes nesta
rodada (custou ~20 min). Antes de subir o worker: conferir `inspect().active()`.

**IoU antes/depois:** a única medição de IoU confiável desta rodada é a anterior (v10-base 0,84 ×
v11 0,67, em 229 frames duplamente virgens). Não há IoU novo porque **não houve treino novo** —
e inventar um número aqui seria exatamente o tipo de promessa mágica que a rodada proíbe.

**Recalibração de limiar por classe com os vereditos do Vitor: BLOQUEADA, e agora se sabe por quê.**
Não existe nenhum veredito gravado (0 de 334) porque o caminho não existia. Com o caminho aberto
nesta rodada, a recalibração passa a ser possível **depois** que o Vitor revisar as 32 violações.

---

## 2 · UI de produto

### a) Escopo por câmera na tela

A aba "Modelos por câmera" já existia e estava acessível (`/epi/training`). Faltavam quatro coisas,
e uma delas era grave:

**🔴 A tela mostrava escopo FALSO nas 14 câmeras.** Os deployments do RVB tinham a chave
`classes_scope` — gravada por script ad-hoc — enquanto o contrato do código (`geometry_validation.py`,
GET/POST, e a própria aba) é `classes`. Com a chave ausente, o fallback marcava **todas** as classes,
visualmente idêntico a um escopo real; e como o `base` usava o mesmo fallback, o botão Salvar ficava
desabilitado. O admin via 6 classes marcadas, acreditava que eram as em vigor, e não tinha como
corrigir.

Medido: **14 de 14** com `classes_scope`, **0** com `classes`. Dado corrigido (move o valor, não
apaga chave nenhuma) e o script do shadow alinhado ao contrato do código.

**Verificado NA TELA** (front local contra a API do DEV): as 14 câmeras com deployment mostram o
escopo real e os números batem com o banco um a um — Qualidade 01 EPI 1 classe, Manutenção 1,
Montagem Artefatos Madeira 3, Entrada Expedição 02 2, Sala de Colagem 3. As 6 sem deployment
aparecem **sem nada marcado**, não "todas as classes".

**E a verificação achou um defeito que nenhum teste pegaria: a aba não abria.** `connection pool
exhausted` — a tela disparava um GET por câmera em `Promise.all` e tomava 28 conexões do pool da API
de uma vez, enquanto o banco estava folgado (5 de 500). O comentário no próprio código já previa
("se doer, criar GET /api/cameras/model-config"). Criado: uma chamada por MÓDULO distinto, com
`DISTINCT ON (camera_id)`, escopada por tenant. A tela passou a carregar.

**Mais dois consertos que só apareceram olhando:**
- **Permissão errada por categoria.** O gate era `training:approve` — "aprovar treinamentos", só
  superadmin — então o admin da RVB via a aba em somente leitura. Editar quais classes uma câmera
  reconhece é `cameras:configure`, que já existe, já inclui admin, e cuja descrição no registry é
  "alterar configurações técnicas da câmera (FPS, modelo, conexão)".
- **O aviso da tela virou mentira por causa de uma mudança minha.** Dizia "o worker da nuvem não
  filtra por classe", o que deixou de valer quando o filtro entrou. Uma tela que se declara honesta
  e afirma **menos** do que faz erra do mesmo jeito. Corrigido, com a ponta do edge (#519) explícita.

**"Salvar já vale" agora é verdade** (item 4 / #519, primeiro elo): `_resolve_camera_model` lia o
deployment **só** para tirar o `model_id` — `grep -n classes inference.py` devolvia uma única linha,
e era comentário. O worker agora filtra as detecções pelo escopo da câmera antes de virar violação.
Ausência não vira silêncio: `classes` faltando = tudo passa (é o estado de quem nunca abriu a aba;
tratar como "nada passa" apagaria 28 câmeras de uma vez); lista vazia é escolha explícita e é
respeitada.

### b) Revisão de alerta completa

| | antes | agora |
|---|---|---|
| abrir o alerta | **reconhecia** (hover de 1s) | abrir não é dar ciência |
| confirmar / errado | rota existia, devolvia 404 sempre | grava veredito humano |
| reposicionar caixa | não existia | arrasto no frame inteiro, pixels + `bbox_unidade` |
| proveniência da correção | não existia | migration 126, ledger append-only |

Migration 126 (`violations_historico`): coluna e não tabela porque o valor anterior só é lido no
contexto do próprio alerta. Guarda o array `violations` **inteiro** de antes, não um diff. Nada é
apagado — descartar uma correção ruim é um novo append.

**Prova ponta a ponta contra o DEV** (`PATCH /api/alerts/<id>/violations`):

| passo | resultado |
|---|---|
| bbox antes | `[1083.1, 203.9, 150.4, 93.8]`, `bbox_unidade: pixels_xywh_frame_original` |
| PATCH com bbox novo | **200** — bbox trocado, unidade carimbada pelo SERVIDOR, classe/confiança/modelo preservados |
| `index` fora do intervalo | **400** |
| alerta de outro tenant | **404** (nunca 403 — C-01) |
| ledger | 1 entrada com `em`, `por`, `tipo: bbox` e o array `violations` INTEIRO de antes |

Restaurei o valor original **pelo mesmo caminho**, que é o que a própria migration manda ("descartar
uma correção ruim = novo append, não remoção"): o bbox voltou ao original e o ledger ficou com
**2 entradas**. Nada foi apagado; o histórico mostra as duas correções.

---

## 3 · Campanha de ausência (#537)

Só **2 de 5** classes de ausência sustentam precisão ≥50% em algum limiar.

**🔴 E o diagnóstico anterior desta campanha estava errado — eu o corrigi publicamente no #537.**
Eu tinha concluído *"não é volume, é separabilidade"*, comparando `Uso incorreto de mascara`
(sustenta com 250 caixas) contra `Sem Luvas` (falha com 361). **Aquelas contagens estavam
contaminadas pelos rótulos `[0,0,1,1]`.** Separando caixa desenhada de rótulo de frame:

| classe | caixas REAIS | rótulos de frame | contaminação | sustenta ≥50%? |
|---|---:|---:|---:|:--:|
| Sem protetor de ouvido | 509 | 27 | **5,0%** | ✅ |
| Uso incorreto de mascara | 222 | 31 | **12,2%** | ✅ |
| Sem Luvas | 180 | 183 | **50,4%** | ❌ |
| Sem mascara | 136 | 158 | **53,7%** | ❌ |
| Sem Óculos | 111 | 95 | **46,1%** | ❌ |

**As duas que funcionam têm 5% e 12% de contaminação. As três que falham têm 46%, 50% e 54%.** A
separação é limpa demais para ser coincidência. E o volume real cai junto: `Sem Luvas` não tem 361
caixas, tem **180**.

As duas hipóteses ficaram confundidas — as três classes ruins têm simultaneamente menos caixas
reais **e** metade do dado envenenado. **⛔ Não minerei frame novo**: mineração dirigida por um
diagnóstico que sei estar contaminado é trabalho no alvo errado. A ordem correta é treinar o v14
(dado limpo pela primeira vez), remedir precisão × limiar das 5 classes, e só então escolher o alvo.

**Tensão estrutural registrada:** ausência é julgamento de pessoa inteira, não objeto com contorno
próprio — "Sem Luvas" não tem borda, quem anota desenha a mão nua (área média 2,33% do frame). É
por isso que a aba Classificar atrai justamente essas classes e produz o rótulo de frame. #537 e
#538 são o mesmo problema visto de dois lados.

### Metas numéricas — e o fato de desenho que a tabela entregou

Inventário depois das duas limpezas desta rodada (fora o rótulo `[0,0,1,1]`, com a proveniência dos
403 restaurada):

| classe | mão humana | propostas aceitas | rótulo de frame (fora) | câmeras |
|---|---:|---:|---:|---:|
| **Sem protetor de ouvido** (régua) | **509** | **0** | 27 | 19 |
| **Uso incorreto de mascara** | **222** | **0** | 31 | 11 |
| Sem Luvas | 180 | 0 | 183 | 14 |
| Sem mascara | 136 | 0 | 158 | 11 |
| Sem Óculos | 111 | 0 | 95 | 13 |

**O propositor NUNCA propõe classe de ausência — zero, em todas as cinco.** Todo o dado delas é
desenhado à mão, uma caixa por vez. É por isso que elas crescem devagar enquanto `Protetor auditivo`
acumulou 3.085 propostas: o volante do propositor não gira para ausência. Fato de desenho, não falta
de esforço de quem anota.

**E o piso de "dado suficiente" é ~222 caixas, não 509** — `Uso incorreto de mascara` sustenta com
44% do volume da régua. Os alvos, então, são pequenos:

| classe | tem | alvo | **faltam** |
|---|---:|---:|---:|
| Sem Luvas | 180 | ~222 | **+42** |
| Sem mascara | 136 | ~222 | **+86** |
| Sem Óculos | 111 | ~222 | **+111** |

Dezenas de caixas, não milhares. ⛔ Mas os alvos saíram de um veredito medido em dado contaminado:
com o v15 no dado limpo, essas classes podem passar **sem caixa nova nenhuma**. Remedir primeiro.

### Escape da âncora de pessoa, por câmera

Medido contra verdade humana: 497 frames anotados, 20 câmeras, 843 caixas. Critério: caixa de EPI
desenhada por gente sem nenhuma pessoa detectada em volta (mesmo portão do shadow, 30% de
contenção).

| canal | câmera | caixas | escaparam | taxa | frames sem pessoa |
|---:|---|---:|---:|---:|---|
| 20 | Galpão Alugado Entrada | 11 | 9 | **81,8%** | 1/4 |
| 19 | Galpão Alugado Saída | 51 | 33 | **64,7%** | 2/20 |
| 8 | Entrada Usinagem Madeira 01 | 45 | 23 | **51,1%** | 8/30 |
| 11 | Entrada WC Usinagem Papelão | 66 | 32 | 48,5% | 4/30 |
| 3 | Qualidade 05 | 48 | 23 | 47,9% | 4/30 |
| 5 | Qualidade 06 | 59 | 28 | 47,5% | 2/30 |
| 4 | Entrada Usinagem Madeira 2 | 48 | 21 | 43,8% | 7/30 |
| 24 | Montagem Artefatos Madeira | 51 | 20 | 39,2% | 3/30 |
| 12 | Sala de Colagem | 46 | 18 | 39,1% | 0/30 |
| 1 | Entrada Expedição | 58 | 22 | 37,9% | 1/30 |
| … | (demais 10 câmeras entre 11,1% e 36,1%) | | | | |
| 29 | Qualidade 01 EPI | 27 | 3 | **11,1%** | 0/13 |
| | **geral** | **843** | **316** | **37,5%** | |

⚠️ **Ressalva honesta:** 37,5% mistura duas causas. A âncora perdendo pessoa **e** EPI que não está
vestido (capacete na prateleira, bota no chão) — para o shadow, descartar o segundo caso é o portão
funcionando. A separação parcial veio da área da caixa: nas classes cuja mediana de caixa que escapa
é **100% do frame** (`Sem mascara`, `Botas`, `Sem Luvas`, `Óculos`, `Sem Óculos`), o "escape" é
artefato do rótulo `[0,0,1,1]` da aba Classificar, não da âncora. Foi assim que o defeito C apareceu.

**Recomendação medida:** ch20, ch19 e ch8 concentram escape com caixa de tamanho normal e alta taxa
de frames sem nenhuma pessoa (ch8: 8 de 30). Ângulo e escala nessas três justificam **grade 3×3** em
vez da 2×2 atual. As demais não justificam o custo.

---

## 4 · Tempo real (#519)

Primeiro elo entregue (ver item 2a): o escopo de classes por câmera passou a valer no worker da
nuvem. **A issue continua aberta** e a razão está registrada nela: o box edge ainda não recebe
classe por câmera — o elo da ponta não existe.

**Latência antes/depois: não medida, e a razão não é preguiça.** A mudança é um filtro em memória
sobre a lista de detecções, DEPOIS da inferência — microssegundos sobre um caminho que gasta
centenas de milissegundos em GPU e rede. Medir e publicar um delta desses seria teatro de rigor.

**O badge continua honesto — verificado na tela.** `ProcedenciaBadge` só renderiza a afirmação
NEGATIVA ("coleta retroativa"); não existe ramo que escreva "AO VIVO". *Ausência de badge é ausência
de afirmação*, que é a única postura correta enquanto `alerts.timestamp` puder nascer igual ao
`created_at`. Na tela do histórico, as 20 linhas visíveis carregam `COLETA RETROATIVA` — correto: o
shadow rodou sobre frames já coletados. **Nada nesta rodada tornou o sistema tempo real, e a tela
não afirma que tornou.**

---

## 5 · Varredura de issues — 44 abertas

**Medição que mudou o plano:** esta árvore está **49 commits atrás de `origin/develop`**. Vários
candidatos a conserto nasceriam sobre base velha e conflitariam. Conferido arquivo a arquivo.

### Corrigidas nesta rodada

| # | título | commit |
|---|---|---|
| **497** | Propagação semeada monta o pool com frame que a curadoria já descartou | `aee54dbf` |
| **515** | Re-tentativa de build mistura dois sorteios e vaza train→val | `70f1b1d1` |
| **530** | Padronizar 403→404 nas 10 rotas irmãs de `/api/v1/videos` (C-01) | `5ff12171` |
| **538** | (aberta e já corrigida na mesma rodada) caixa `[0,0,1,1]` no treino | `28b97525` |

### Tabela completa

| # | estado | motivo | próximo passo |
|---|---|---|---|
| 497, 515, 530 | ✅ corrigida | — | merge |
| 538 | ✅ corrigida (aberta nesta rodada) | detector de pessoa agora existe; falta alimentar o CropClassifier | rodada própria |
| **539** | 🆕 aberta nesta rodada | o gate de procedência decide por `source`, o campo que o save sabe destruir; `proposal_model_id` é imutável e já existe (migration 124) | depois do veredito do #536 |
| 536 | 🔄 em andamento | 3 confundidores corrigidos; datasets v14 prontos | treinar + A/B |
| 537 | ⏳ precisa-de-dado | 3 classes não passam de 50% em limiar nenhum | mineração dirigida |
| 519 | 🔄 parcial | elo da nuvem feito; elo do edge não | rodada própria |
| 517, 510 | ⏳ base velha | `job_handlers.py` diverge +26/−41 | worktree fresco de develop |
| 532 | ⏳ base velha + contrato | `socket_bridge.py` diverge +60/−143 | worktree fresco + decidir contrato |
| 520 | ⏳ espera #536 | contrato FE↔BE no mesmo endpoint em obra | depois do #536 |
| 445 | ⏳ escopo próprio | exige campo `kind` no catálogo (migration) + FE | rodada própria |
| 534 | ⏳ medição | confirmar a regra do CLI Railway antes de renomear | medir |
| 514, 513, 511 | ⏳ métrica de modelo | prova exige treino em GPU | remedir pós-v14 |
| 508 | ⏳ medição | a issue proíbe presumir: falta logar o XFF real | medir em produção |
| 531, 442, 142, 131 | ⏳ hardware/campo | exige o box, o DVR real ou a RVB | sessão no Jetson / campo |
| 429, 427, 423 | ⏳ dado | mínimos saem do volume real, não de regra de bolso | definir com volume |
| **535** | 🔴 gate humano | matriz de EXIGÊNCIA classe×área só o Paulo tem | Vitor + Paulo |
| **472** | 🔴 gate humano | não existe entrega de alerta; exige canal + chave | decisão + chave |
| **495** | 🔴 gate humano | worker de PRODUCTION sem repo conectado | Railway, ação do Vitor |
| **433, 475** | 🔴 gate humano | proteção de branch / `workflow_run` roda a definição de `main` | decisão do Vitor |
| **421** | 🔴 gate humano | astro 4→7 = 3 majors num site em produção | janela + smoke |
| 507, 533, 209, 207 | 🔴 gate humano | processo, produto ou limpeza aguardando decisão | Vitor decidir |
| 483, 482, 481, 480, 225, 224 | 🔴 cliente | condição da luva, câmeras, classe nova, faixa | reunião |
| 223, 222, 220, 219 | 🔴 gate humano | provisionamento, senha, promoção | agenda do Vitor |

**Exceções justificadas:** nenhuma issue "corrigível agora" ficou de fora. As marcadas *base velha*
são corrigíveis mas exigem worktree de `origin/develop` — consertá-las aqui produziria conflito
garantido no merge, o que é pior que adiar.

**Achado extra:** `versioning.py:108` (o v1, em fila de morte no #209) tem o **mesmo** `random.shuffle`
sem semente do #515. Não foi consertado porque o arquivo está marcado para morrer — mas continua
registrado e roteado no Celery, então o defeito ainda é alcançável. Entra na decisão do #209: ou
morre, ou herda a semente.

---

## 6 · Relatório da Semana 1

`docs/reports/SEMANA-2026-08-24.md` — entregue, terminando com as 3 perguntas para o Paulo.

---

## 7 · Custos

| item | valor |
|---|---:|
| GPU nesta missão | US$ 1,62 de US$ 12,00 |
| Pods vivos ao fim | **0** |
| Egresso de frame para fora da nuvem | **zero** (D-72) |

---

## O que NÃO foi resolvido, e por quê

| item | por que não | próximo passo |
|---|---|---|
| **Veredito do A/B (#536)** | os dois braços foram treinados; o `v15-tudo` ainda não convergiu quando este relatório fechou | rodar `ab_536.py` com os dois ONNX e publicar o veredito por classe |
| **IoU antes/depois novo** | depende do veredito acima. ⛔ Não invento número: a única medição de IoU confiável até aqui é a anterior (v10-base 0,84 × v11 0,67, em 229 frames duplamente virgens) | sai junto do A/B |
| **Recalibração de limiar com vereditos** | não havia veredito nenhum gravado (0 de 334) porque o caminho não existia. Agora existe e está provado ponta a ponta — mas os vereditos ainda precisam ser dados | Vitor revisar as 32 violações |
| **Elo edge do #519** | o box não recebe classe por câmera; exige sessão no Jetson. O elo da nuvem foi entregue | rodada própria |
| **Mineração dirigida (#537)** | ⛔ deliberadamente adiada: os alvos saíram de um veredito medido em dado contaminado (46–54% de rótulo de frame nas três classes que falham). Elas podem passar sem caixa nova | remedir no v15, depois minerar (+42, +86, +111 já calculados) |
| **Migração do gate para `proposal_model_id` (#539)** | trocaria o conteúdo dos braços no meio do experimento — seria o sexto confundidor da rodada | depois do veredito do #536 |
| **#517, #510, #532** | árvore 49 commits atrás de `origin/develop`; conserto aqui conflitaria no merge | worktree fresco de `origin/develop` |
| **Recorte de pessoa no CropClassifier (#538)** | o detector já existe; alimentar a aba é mudança de UI com escopo próprio | rodada própria |

## Entradas do Vitor (item 7 — nada aqui bloqueou a rodada)

| pendência | estado |
|---|---|
| **Revisão das 32 violações** | ⏳ o caminho existe e está provado; 2 alertas já têm veredito (os meus, de teste). Faltam as 32 de verdade — e são elas que destravam a recalibração de limiar por classe |
| **Entrada WC** | ⏳ sem decisão sua. Medido nesta rodada: ch11 *Entrada WC Usinagem Papelão* tem 48,5% de escape da âncora de pessoa (66 caixas humanas, 32 sem pessoa detectada) — se ela ficar no escopo, entra na lista de câmeras que merecem grade 3×3 |
| **Matriz de exigência do Paulo (#535)** | 🔴 gate humano. É o que separa CAPACIDADE de EXIGÊNCIA — enquanto não vier, nenhum alerta sai para ninguém. As 3 perguntas para ele estão no fim do relatório da semana |
