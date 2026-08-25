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

#### 🔴 VEREDITO DO #536: a hipótese NÃO se sustenta

Os dois braços treinaram e foram avaliados no **mesmo** campo — o `test` do
braço só-humano: 289 frames, 403 caixas, **todas de mão humana**, virgem para
os dois modelos.

| limiar | só-humano F1 | tudo F1 |
|---:|---:|---:|
| 0,20 | 0,39 | **0,48** |
| 0,25 | 0,44 | **0,53** |
| 0,30 | 0,47 | **0,53** |
| 0,35 | **0,49** | **0,53** |
| 0,40 | 0,49 | **0,53** |
| 0,50 | 0,42 | **0,52** |
| 0,60 | 0,22 | **0,47** |

**`tudo` vence em TODOS os limiares.** Melhor de cada um: `tudo` **F1 0,532**
(limiar 0,30, precisão 0,50 / recall 0,57) contra `só-humano` **0,493** (limiar
0,35). Não é margem estreita e não depende do corte escolhido — domina a curva
inteira, inclusive na faixa de produção (0,25–0,30).

**Por classe** (no melhor limiar de cada), `tudo` é melhor em 8 das 10:

| classe | gt | só-humano prec/rec | tudo prec/rec |
|---|---:|---:|---:|
| Protetor auditivo | 209 | 64,6% / 58,4% | 62,9% / **68,9%** |
| Uso incorreto de mascara | 55 | 61,2% / 54,5% | **61,9%** / 47,3% |
| Luvas | 34 | 38,9% / 41,2% | **45,2%** / 41,2% |
| Sem protetor de ouvido | 32 | 30,0% / 46,9% | **40,0%** / 37,5% |
| mascara | 26 | **42,0%** / 80,8% | 32,8% / 76,9% |
| Óculos | 11 | 14,3% / 54,5% | **20,0%** / **63,6%** |
| Sem Luvas | 11 | 0% / 0% | **25,0%** / **9,1%** |
| Sem Óculos | 9 | 33,3% / 22,2% | **66,7%** / 22,2% |
| Botas | 9 | 10,0% / 33,3% | **20,0%** / **44,4%** |
| Sem mascara | 7 | **16,7%** / 28,6% | 0% / 0% |

**A contaminação reforça o veredito, não o enfraquece.** O braço só-humano
carregava 11,4% de geometria do modelo (as 403 caixas). Se essa geometria
ajuda — e o resultado diz que sim —, então o só-humano foi artificialmente
BENEFICIADO por ela: o valor dele sem contaminação seria ainda menor, e `tudo`
venceria por mais. A direção é segura.

**Épocas (a régua honesta, não o `current_epoch`):** só-humano rodou **17**,
`tudo` rodou **15** — os dois pararam cedo, sob a mesma política
(`early_stopping_patience=8`). O `tudo` fez menos épocas com 2,1× o dado; cada
época dele custou ~4× mais relógio (129 min contra 39). ⚠️ A linha do `tudo`
no banco diz `current_epoch = 50`: é o defeito corrigido em `0dcab375`, ainda
não implantado quando este treino fechou.

### O que isso decide, e o que ainda não decide

**Decide:** ⛔ NÃO promover o filtro só-humano. A regra da rodada era "perdendo
ou empatando → números e mantém", e ele perdeu com folga. O export continua
aceitando caixa de proposta revisada. **Nenhuma ADR de regra nova** — a
hipótese do #536 não passou.

**Não decide:** *por quê*. `tudo` tem 4.977 frames contra 2.362 — pode estar
ganhando pela geometria ou simplesmente por 2× o dado. A auditoria adversarial
pré-registrou exatamente este desfecho como o único em que o terceiro braço se
paga ("se o só-humano vencer com metade do dado, o volume estava contra ele e
a direção sobrevive; só se o TUDO vencer é que volume vira explicação rival").

`v16-volume` — o braço `tudo` cortado a 2.362 frames — está em construção. Ele
separa as duas explicações, e a resposta muda o que fazer DEPOIS: se for volume,
vale investir em anotar mais; se for geometria, a proposta aceita é boa e o
volante do propositor deve girar mais.

##### ⚠️ Correção de pré-registro: o terceiro braço não é o que eu descrevi

Escrevi acima "mesmos 2.362 frames, mesma partição". **Conferi antes de ler o
resultado, e é falso.** Os números:

- `v16-volume` tem 2.362 frames, mas **só 1.118 coincidem com o `só-humano`**.
  Ele é uma *subamostra do `tudo`* (2.362 ∩ tudo = 2.362), não um gêmeo do
  `só-humano` no mesmo campo.
- O corte **não foi proporcional**. As classes de ausência caíram pela metade
  (`Sem protetor de ouvido` 505→240, `Sem Luvas` 178→91, `Sem Óculos` 110→46,
  `Uso incorreto de mascara` 219→104) enquanto `Protetor auditivo` **subiu**
  1.027→1.330 — o limitador determinístico pegou frames densos na classe
  favorita do propositor.

**O que ele ainda responde, e o que não responde.** Volume está igualado
(2.362 = 2.362) e a fonte de anotação difere, então ele continua separando
"fonte" de "volume" — mas **só nas classes cujo corte foi proporcional**. Nas
classes de ausência o resultado fica confundido com a metade que sumiu, e vou
lê-lo como tal. Não é o experimento limpo que eu prometi; é um experimento útil
com um viés medido e declarado.

**E um fato de desenho caiu junto:** `tudo` e `só-humano` têm contagem
**idêntica** nas classes de ausência (178/134/505/110/219 nos dois braços). O
propositor **não desenha uma única caixa de ausência**. A #537 dizia isso; agora
está quantificado, e reforça o veredito — se a geometria do modelo ajuda, ela
ajudou só nas classes de presença, e ainda assim o `tudo` venceu.

**Efeito colateral valioso:** foi ao conferir isto que achei o #542. O `v16` tem
11 categorias e o `v15` tem 12; conferir o alinhamento levou ao mapa
índice→nome, e daí ao caminho servido que não recebia mapa nenhum.

#### 🔴 RESULTADO DOS TRÊS BRAÇOS — e a pergunta continua aberta

`v16-volume` terminou (24 épocas, 71 min, US$ 0,88). Mesmo campo virgem: 289
frames, 403 caixas, verdade 100% humana.

| braço | frames | fonte | melhor F1 | limiar |
|---|---:|---|---:|---:|
| só-humano | 2.362 | só humano | 0,493 | 0,35 |
| v16-volume | 2.362 | humano + proposta | 0,511 | 0,35 |
| **tudo** | 4.977 | humano + proposta | **0,532** | 0,30 |

A ordenação `tudo > v16 > só-humano` se repete nos **7 limiares**, sem exceção.

**Mas 0,02 sobre 403 caixas não se lê a olho.** Bootstrap pareado sobre os 289
frames (2.000 reamostragens; frames e não caixas, porque caixas do mesmo frame
não são independentes — mesma cena, mesma luz, mesmo turno):

| diferença | média | IC 95% | P(>0) |
|---|---:|---|---:|
| `tudo` − `só-humano` | **+0,040** | **[+0,004, +0,077]** | **98,6%** |
| `v16` − `só-humano` (efeito da FONTE) | +0,018 | [−0,022, +0,056] | 81,0% |
| `tudo` − `v16` (efeito do VOLUME) | +0,022 | [−0,012, +0,058] | 88,9% |

**O que isto decide:** o veredito do #536 fica **mais forte**, não mais fraco —
o intervalo da diferença total **exclui zero**. ⛔ Não promover o filtro
só-humano, e agora com intervalo, não só com ponto.

**O que isto NÃO decide, ao contrário do que prometi:** a pergunta "geometria ou
volume?" **continua aberta**. Os dois efeitos são de tamanho parecido (+0,018 e
+0,022, somando os +0,040) e **nenhum dos dois é distinguível de zero
isoladamente** neste campo. Gastei um pod para descobrir que 289 frames não
bastam para separá-los — separar exigiria um campo perto de 4× maior, e não
vale antes de haver mais verdade humana para gastar.

O viés que pré-registrei empurra na mesma direção: as classes de ausência do
`v16` foram cortadas pela metade, o que penaliza o `v16` e faz do +0,018 um
**piso** do efeito da fonte, não uma estimativa centrada.

**A leitura prática, que não depende de separar as duas:** ambas as alavancas
apontam para o mesmo lado e valem cerca do mesmo. Anotar mais paga tanto quanto
aceitar proposta — o volante do propositor **não substitui** anotação humana, e
o inverso também não. E como o propositor não desenha uma única caixa de
ausência (medido acima), para as classes da #537 **só a anotação humana move o
número**.

#### Duas medições, e por que só uma vale como veredito

O AP@50 de treino existe — 35 avaliações no braço só-humano, medidas pelo pod a cada época e
**nunca persistidas** (#541). Extraí do log:

| braço | avaliações | AP@50 melhor | curva |
|---|---:|---:|---|
| só-humano (fechou, 17 épocas) | 35 | 0,330 | 0,13 → 0,33 |
| tudo (em curso) | 20 | 0,355 | 0,23 → 0,35 |

⛔ **Isso NÃO é o veredito.** Cada braço é avaliado no PRÓPRIO split de validação, e são conjuntos
diferentes: o do `tudo` tem 1.268 frames cuja verdade inclui caixas desenhadas pelo modelo — ele
está sendo medido contra a geometria do próprio ancestral, que é o viés nº 1 que a auditoria mandou
eliminar. O `tudo` liderar no próprio campo é o resultado esperado de um campo inclinado a favor
dele, e não diz nada sobre qual modelo é melhor.

O veredito sai da avaliação dos dois ONNX no **mesmo** campo, com verdade 100% humana (289 frames,
403 caixas), virgem para ambos. As duas medições servem a propósitos diferentes: a de treino diz se
cada um convergiu; a comum diz qual é melhor.

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

**Prova refeita contra o DEV, agora conferindo o código de status:**

| passo | HTTP | resultado |
|---|:--:|---|
| estado inicial | — | `Óculos: pre_annotation` · `Protetor auditivo: pre_annotation` |
| salvar **sem tocar em nada** | **200** | os dois seguem `pre_annotation` — a proveniência sobreviveu |
| **mover uma** caixa e salvar | **200** | `Óculos: manual` · `Protetor auditivo: pre_annotation` |

A segunda linha é o conserto; a terceira é a discriminação que ele precisa ter. A caixa que a mão
humana moveu vira `manual` — que é o certo, porque aí a geometria passou por gente — e a que ninguém
tocou continua sendo do modelo. Restaurei a proveniência da caixa que o meu teste mexeu.

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
| **542** | (aberta e corrigida na mesma rodada) modelo servido rotulava em COCO — 61/61 classes trocadas | `32e81d03` + `40d9cd76` |
| **543** | (aberta, correção **parcial** e declarada como tal) mesmo buraco no edge — guarda portado, contrato NÃO mudado | `23aa866d` |
| **544** | (aberta e corrigida na mesma rodada) `has_violation` sempre falso — polaridade vinha de env com nomes COCO | `7f23384d` |
| **545** | ⚠️ `risk:security` — `GET /cameras/<id>/alerts` lia alerta de **qualquer tenant**; corrigido, migration 022 **não** | `ac2d481c` |

**Sobre a #543, para não haver leitura otimista:** o commit **não corrige** o
defeito. Corrigir exige mudar o que o edge precisa para servir um modelo
(sidecar JSON ou payload `model:reload`), e o executor do box está pinado até a
próxima OTA. Mudar isso sem poder rodar contra o Jetson arrisca deixar o RVB
**sem inferência**, que é pior que o rótulo errado. O que foi feito é tornar o
defeito visível — o detector passa a avisar quando o dicionário não bate com o
modelo. **A correção de verdade precisa de uma sessão com o box acessível.**

### Tabela completa

| # | estado | motivo | próximo passo |
|---|---|---|---|
| 497, 515, 530 | ✅ corrigida | — | merge |
| 538 | ✅ corrigida (aberta nesta rodada) | detector de pessoa agora existe; falta alimentar o CropClassifier | rodada própria |
| **539** | 🆕 aberta nesta rodada | o gate de procedência decide por `source`, o campo que o save sabe destruir; `proposal_model_id` é imutável e já existe (migration 124) | depois do veredito do #536 |
| **540** | 🆕 aberta nesta rodada | job terminal sem `completed_at` faz consulta de custo acumular para sempre — 6.037 min fantasma, 11× no total | fechar o estado na hora + consulta que não usa `now()` para terminal |
| **541** | 🆕 aberta nesta rodada | o job fecha sem UMA métrica de qualidade; o dado existe no log do pod e não chega ao registro | descobrir as chaves reais do callback e persistir |
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

## 🔴 O maior achado da rodada: o modelo servido fala outra língua (#542)

Encontrei este por acidente, verificando o terceiro braço do A/B. É o defeito
mais grave desta rodada e o mais bem escondido.

**O que acontece.** O ONNX devolve um **índice**. Quem traduz índice→nome é a
lista `class_names` do detector. `_get_detector_for_camera` — o caminho que
serve modelo treinado por câmera — **não passava essa lista**, então o detector
caía em `COCO_CLASSES_91`.

Medido no modelo v15 contra frames reais do holdout: **61 de 61 rótulos
trocados**, com substituição sistemática.

| servido hoje | o que a caixa realmente é |
|---|---|
| `bus` | Protetor auditivo |
| `train` | mascara |
| `traffic light` | Botas |
| `truck` | **Sem protetor de ouvido** |
| `car` | **Sem Luvas** |
| `airplane` | **Sem Óculos** |

No modelo hoje ativo nas 12 câmeras do DEV (`46a30ed9…`, dataset `v10b-freeze`,
13 classes) a troca é idêntica: o índice 8, que o modelo usa para *Sem protetor
de ouvido*, sai como `truck`.

**Por que ninguém viu — dois silêncios empilhados.**

1. **O filtro de escopo do #519 apaga a evidência, e o filtro é meu.**
   `_no_escopo_da_camera` compara o nome contra as classes da câmera. Com
   dicionário COCO **nada casa** → 100% descartado → **zero alerta, zero erro**,
   um `logger.debug`. Meu código converteu "rótulo errado" em "nenhuma saída",
   que é a falha mais invisível das duas. **Zero alerta lê exatamente igual a
   "não houve violação"** — num produto de segurança, na direção cara.

2. **Os 334 alertas do shadow têm nomes certos porque não saíram desta tarefa.**
   Conferido no banco: zero nomes COCO nos 334. Eles provam que o **modelo**
   funciona; não provam que o **caminho servido** funciona. É o quinto caminho
   que mente desta linhagem: a evidência parecia o produto rodando, e o produto
   nunca tinha rodado ali.

**O detalhe que torna isso permanente.** O exportador **omite categoria com zero
caixas**. Dois exports do mesmo tenant: `v15-so-humano` tem 12 categorias,
`v16-volume` tem 11 — o `Capacete`, com 2 caixas, sumiu — e **as 11 posições
restantes ficam todas deslocadas**. O índice de classe é função da *amostra*,
não da taxonomia. Se eu tivesse copiado o arquivo de classes de um export para
o outro, o terceiro braço teria produzido um número plausível e completamente
falso, e eu teria concluído "volume importa" a partir de puro deslocamento.

**O que já estava certo, e é a lição.** O caminho de **avaliação** passa a lista,
e o docstring de `_class_names_from_coco` descreve este exato perigo com todas
as letras: *"sem esta lista ele cai em COCO_CLASSES_91 (…) e o resultado é um
avaliador que não acerta nada e não diz por quê"*. **O perigo era conhecido,
documentado, e fechado no caminho que mede — não no que roda.**

**Correção** (commit `32e81d03`):
- `_taxonomia_do_modelo()` resolve a ordem via `trained_models.dataset_version_id`
  → COCO do split **train**, que é o diretório que dimensionou a cabeça no treino.
- `_resolve_camera_model` devolve `class_names` e **recusa servir** (log `ERROR`,
  cai para o baseline do env, que é de fato COCO) quando não resolve. Rotular
  com dicionário inventado é pior do que não servir.
- `_no_escopo_da_camera`: descarte de 100% virou `warning` com as classes vistas
  e o escopo. 100% fora quase nunca é turno limpo.

**Prova:** 5 testes falham sem a correção, 7 passam com ela (2 são controle
negativo — descarte parcial e câmera sem detecção seguem silenciosos). Suíte
completa comparada contra a baseline em `HEAD~2`: **as mesmas 8 falhas
pré-existentes, zero regressão**. `quality_inference.py` chama o mesmo helper
(linhas 289 e 579), então herda a correção.

---

## 🔴 E puxando esse fio: quatro camadas falando COCO (#544)

O #542 não era um caso isolado. Puxando o fio a partir dele, o caminho inteiro
que decide o que é violação foi escrito para uma taxonomia de demonstração e
**nunca foi re-apontado para a do cliente**.

| camada | o que fala | o que deveria falar |
|---|---|---|
| detector (#542) | `COCO_CLASSES_91` | taxonomia do modelo |
| `_VIOLATION_CLASSES` | `{no_helmet, no_vest, no_gloves}` | `yolo_classes.is_violation` |
| heurística do bridge (#132) | `class.startswith("no_")` | idem |
| prompt do `verify_alert` | *"classes que começam com `no_`"* | idem |

**O que foi medido.** `VIOLATION_CLASSES` **não está setada** — conferido em
`API-V3` e em `celery-worker`. Vale o default, e esses três nomes não existem
no cadastro do RVB, onde o banco tem a polaridade certa: `Sem botas`,
`Sem mascara`, `Sem protetor de ouvido`, `Uso incorreto de mascara` = TRUE.
Nenhuma começa com `no_`.

**A cadeia inteira, e o que ela explica.** `has_violation` era **sempre falso**
→ `_save_alert` nunca chamado por esse caminho → `submit_for_verification`
nunca chamado → a fila `needs_human` ficava **vazia por construção** → a tela
escrevia *"Nenhum alerta aguardando revisão humana"*.

Esse último item eu já havia registrado nesta rodada, mas **só como sintoma**
(`verification_verdict` NULL em 334 alertas). Este é o **mecanismo**. Vale
anotar a forma: eu tinha o efeito documentado e parei ali. Foi preciso um
acidente — conferir o alinhamento de classes do terceiro braço — para chegar à
causa. Sintoma registrado não é causa encontrada.

**Correção** (commit `7f23384d`): `violation_class_names` no repositório,
resolução única de polaridade para as duas decisões que dependem dela, falha de
leitura devolvendo o último valor bom em vez de "nada é violação", e o prompt
parando de ensinar polaridade por prefixo.

**Não ativa canal de notificação nenhum** — continua dashboard-only — e não
gera custo de API: `ANTHROPIC_API_KEY` não está setada, e sem chave
`_call_claude` devolve `needs_human`, que é o lado seguro. O efeito prático é
que a fila humana **passa a ser populada pela primeira vez**.

### ⚠️ Uma lacuna de cadastro que precisa do Vitor

O modelo servido emite **12–13 classes**; o cadastro do RVB conhece **9**.
Faltam linhas em `yolo_classes` para:

- **`Sem Luvas`**
- **`Sem Óculos`**

São duas classes de **ausência** — justamente duas das que a campanha #537
persegue. Sem linha no cadastro não há polaridade: nem violação nem
conformidade. O código agora **avisa** (`classe_sem_polaridade`) em vez de
ficar mudo, mas **quem cria a classe é o dono do tenant**. Enquanto elas não
existirem, o modelo pode detectar luva ausente a tarde inteira e nada vira
evento.

---

## 🔴 O fio levou a uma leitura cross-tenant ao vivo (#545)

Varrendo o resto da taxonomia de demonstração, cheguei a `infra/migrations/022_demo_mock_alerts.sql`, que insere **13 alertas falsos**. E ao conferir se eles poderiam aparecer para um cliente, encontrei o veículo:

```
GET /api/cameras/<camera_id>/alerts        ← só @jwt_required()
  → get_alerts_handler
  → InferenceService.get_alerts
  → AlertRepository.get_by_camera
  → SELECT * FROM alerts WHERE camera_id = %s
```

**Escopo puro de câmera.** Qualquer usuário autenticado de **qualquer tenant** lia os alertas de qualquer câmera bastando o id.

É a mesma forma do achado #14 (fila de verificação), que foi corrigido lá e ficou aqui. E o detalhe que dói: no mesmo arquivo de teste já existia `test_acknowledge_leva_o_tenant_ao_repositorio`. **A escrita foi fechada; a leitura, não.**

### O agravante, medido

A migration 022 usa `tenant_id` fixo em `'00000000-…-0001'` — o UUID zerado que a constitution proíbe como default — e `camera_id` de `SELECT id FROM cameras LIMIT 1`, isto é, **qualquer câmera de qualquer tenant**. No DEV o tenant "Default" existe (a FK passa) e há **29 câmeras, ~28 do RVB**. Com escopo puro de câmera, um alerta falso `no_helmet` apareceria dentro da visão do RVB.

No DEV não há nenhum (`evidence_key LIKE 'frames/d97cb03e%'` → 0 linhas), porque o DEV usa ledger. **Produção usa o modo legado**, que re-roda tudo a cada boot.

### Corrigido, e o que NÃO foi

Corrigido: `tenant_id` obrigatório e **sem default** em `get_by_camera` — esquecer tem de quebrar na chamada, não devolver os dados de todo mundo em silêncio. O handler pega o tenant do token, nunca da query string. C-01 respeitado: câmera de outro tenant sai **vazia**, não 403.

**NÃO corrigido: a migration 022.** Editá-la é barrado pelo ledger (já testei isto na pele nesta rodada) e `DELETE` é proibido. A saída forward-only seria um sentinela que faz a guarda da própria 022 pular — mas `alerts.camera_id` é `NOT NULL` sem default, então o sentinela também apontaria para uma câmera real, e é **escrita de dado em todo ambiente**, que tem gate humano por bom motivo. Deixei a decisão registrada na #545.

Com a correção de escopo, o impacto prático some — os 13 ficariam invisíveis ao RVB — mas as linhas continuariam existindo.

---

## Varredura sistemática: "o registro afirma mais do que sabe"

Três defeitos da mesma família numa rodada não é coincidência. Varri o
repositório com quatro lentes independentes, cada alegação passando por um
cético: **22 candidatos, 13 confirmados, 9 refutados**.

A forma comum: **no caminho da falha, o sistema devolve o valor que significa
"nada de errado"**. Num produto de segurança, essa é a direção cara do erro.

### Os quatro que decidem errado — todos corrigidos

| # | o que afirmava | quem lia e acreditava | conserto |
|---|---|---|---|
| 1 | **A migration 125 (minha, desta rodada)** converte "ninguém decidiu a polaridade" em "é conformidade" a cada boot **em modo legado (produção)** — no DEV, que usa ledger, não acontece | painel de conformidade, tela de violações, badge de investigação | **migration 127** (editar a 125 foi barrado pelo ledger — ver abaixo) |
| 2 | Detector não carregado publicava `has_violation: false` **a cada frame** | grade ao vivo pintava a câmera de verde | `inferencia_ok` no payload + log alto |
| 3 | `predict()` dos DOIS detectores ONNX engolia exceção e devolvia `[]` | idem — indistinguível de frame limpo | `ultimo_erro` na INTERFACE `Detector` |
| 4 | Falha de consulta virava **"Taxa de Conformidade 100%"**, pintada de verde | KPI do painel do cliente | sentinela `_FALHOU` → `None` → o front já mostrava "—" |

**O nº 1 é o mais desconfortável: é meu, de ontem.** A migration contradizia o
**próprio cabeçalho** ("NULL = ninguém decidiu ainda"; "o prefixo é usado UMA
VEZ, não é regra de runtime") e a ADR-0065 §2, que recusa heurística de nome em
runtime porque *"erraria em silêncio na direção cara"*. Eu escrevi a doc certa e
o SQL errado logo abaixo dela. Uma classe de violação chamada "Fumando" ou
"Área restrita" viraria conformidade no reinício seguinte, sem correção
possível pela UI.

#### 🔴 E aqui eu errei duas vezes — o sistema me corrigiu nas duas

**Primeiro erro: editei a migration 125.** Argumentei que era a única saída,
porque "corrigir na 127" não funcionaria com ela reescrevendo o dado a cada
boot. **O deploy da API morreu:**

> `CRITICAL MIGRATION EDITADA: 125 tem checksum divergente do ledger.`
> `Migrations sao forward-only — nunca edite uma ja aplicada; crie uma nova.`
> `Abortando o boot.`

Existe um ledger com verificação de checksum. **Forward-only aqui é máquina,
não convenção**, e eu passei por cima de um guard que estava certo. Revertí, o
checksum voltou a bater, e o conserto virou a **migration 127** — que é
exatamente o que o guard mandava fazer.

**Segundo erro: a premissa "re-roda a cada boot" não vale em todo lugar.** O DEV
tem `MIGRATIONS_LEDGER_CUTOVER=1` — o log do boot mostra `já aplicada (ledger)
— pulando` nas 124 anteriores. **No DEV a erosão que descrevi não acontece.**

O defeito continua real, mas em **produção**: o docstring de `runner_core.py`
registra o modo legado como *"padrão — produção continua aqui hoje"*, e lá toda
migration reexecuta a cada boot. Eu afirmei "a cada boot" sem qualificar o
ambiente, e isso estava errado para metade dos ambientes.

A **127** resolve nos dois modos: em legado ela roda logo DEPOIS da 125 a cada
boot e desfaz o excesso na mesma passagem; em ledger é aplicada uma vez e vira
no-op. Verificada no DEV com duas execuções seguidas — as 9 classes do RVB
intactas, hash do conjunto inalterado. Aceita pelo ledger (`installed_rank` 116).

O teste agora **trava o checksum da 125** contra o valor registrado: se alguém a
editar de novo, o teste falha antes de o deploy morrer.

⚠️ Pressuposto com prazo, declarado no arquivo: *nenhuma rota grava
`is_violation`*. Quando existir uma — é o que falta para o dono corrigir
polaridade pela tela — a 127 precisa ganhar "e ninguém decidiu explicitamente".

#### O smoke test entregou o argumento da varredura em miniatura

Depois de subir os consertos, `/api/verification/queue/count` passou a devolver
**500**. Fui investigar esperando ter quebrado algo. **A consulta nunca
funcionou.**

O pool usa `RealDictCursor` — toda linha é um dict — e o código fazia `row[0]`,
que levanta `KeyError` sempre. Com o `except: return 0` por perto, o KeyError
virava o fallback: **o badge de revisão humana mostrou 0 desde o primeiro dia.**
Procurei os irmãos e achei mais dois no console de teste, um deles **sem
`except`** (derrubaria a criação de câmeras).

O fallback silencioso não escondeu um erro raro de banco. **Escondeu uma
consulta que nunca funcionou** — que é precisamente o que a varredura existia
para achar.

É a **terceira** vez que o mesmo par aparece na rodada: duplê de teste
devolvendo TUPLA enquanto a produção devolve DICT. As anteriores foram o
`save_batch` (500 em toda gravação de anotação) e este. Há guard para os três.

**E a suíte completa entregou o fecho do argumento.** Depois de corrigir o
serviço, um teste de *segurança* quebrou —
`test_verification_tenant_isolation.py::TestGetQueueCountTenantIsolation`. Ele
mockava `fetchone()` como `(0,)`.

Não era o teste pegando uma regressão: **era o mock compartilhando a premissa
errada do código.** Tupla no duplê + `row[0]` no serviço = os dois concordavam
entre si e discordavam do banco, e o teste passava por isso. Ele só olhava o
SQL, nunca o valor devolvido — então nunca poderia ter pego o defeito que
estava dois centímetros ao lado.

Corrigido: o mock devolve `{"total": 0}` (o que `RealDictCursor` devolve) e o
teste agora **afirma o retorno**, não só a query. É o mesmo princípio do
[teste que cruza a fronteira HTTP](../../CLAUDE.md): um duplê que não se parece
com a coisa real transforma o teste em cúmplice.

### Três que enganam quem lê — corrigidos

**Um módulo inteiro nunca funcionou.** `counting_events` tem `tenant_id NOT
NULL` sem default desde a migration 049, e o único INSERT do sistema não
informava a coluna. Toda gravação levantava, `record_detection` engolia com um
`logger.warning`, e a tabela tem **zero linhas**. Contagens ao vivo, resumo de
sessão e relatório de acurácia liam esse vazio e chamavam de resultado. Provado
contra o schema real, em transação: o INSERT antigo levanta `NotNullViolation`,
o novo grava com o tenant derivado da sessão.

**A fila de verificação mentia "vazia".** Erro de banco virava 200 com lista
vazia; o operador lia "Nenhum alerta aguardando revisão humana" e ia embora. O
caminho honesto já existia nas duas pontas — só o `return []` do meio impedia.

**Overrides de permissão.** Em falha, a tela de admin mostrava "sem overrides"
para um usuário com deny gravado, e a auditoria registrava um estado que nunca
foi lido. ⚠️ **Correção da minha própria leitura:** cheguei a chamar de falha
aberta em autorização. Não é — no login o desfecho continua sendo "os gates
caem no papel", e isso é **anti-lockout deliberado**. Está escrito no código
para ninguém "consertar" achando bug.

### E quatro testes protegiam os defeitos

Um se chamava literalmente `test_record_detection_swallows_exception`. O
silêncio estava codificado como intenção — foi por isso que sobreviveu. Todos
reescritos para afirmar o comportamento honesto, **cada um com o caso feliz ao
lado**: frame limpo continua sendo conformidade, zero violações reais continua
sendo 100%. Sem isso, o conserto viraria alarme permanente — o mesmo defeito na
direção oposta.

### Abertas, não corrigidas (menos graves, mesma família)

`login_count` que nunca é incrementado e a tela mostra "Logins: 0" para todo
mundo · painel superadmin com zeros literais em câmeras online, alertas 24h,
tickets e MRR · alerta de câmera offline comparando o que UM site reporta contra
o total do tenant · erro ao resolver o modelo da câmera indistinguível de "sem
deployment" · detalhe de modelo que falhou no fetch apresentado como "o modelo
prevê o catálogo inteiro".

---

## Limiares por classe — os que estão EM VIGOR hoje

Estes são os limiares que o shadow usa neste momento. ⛔ **Não são o resultado da recalibração que a
rodada pedia** — essa depende dos vereditos do Vitor, que não existiam (0 de 334) porque o caminho
de gravação não existia. Agora existe; os limiares recalibrados saem quando as 32 violações forem
revisadas.

### Conformidade (presença de EPI — telemetria, nunca alerta)

| classe | limiar |
|---|---:|
| Protetor auditivo | 0,25 |
| mascara | 0,25 |
| Óculos | 0,25 |
| Luvas | 0,25 |
| Botas | 0,35 |

### Violação (ausência — evento alertável)

| classe | limiar | por quê |
|---|---:|---|
| Sem protetor de ouvido | 0,25 | sustenta precisão ≥50% |
| Uso incorreto de mascara | 0,30 | sustenta precisão ≥50% |
| **Sem Luvas** | — | ⛔ FORA do gatilho: não sustenta em limiar nenhum |
| **Sem mascara** | — | ⛔ FORA |
| **Sem Óculos** | — | ⛔ FORA |

Três classes de ausência **não têm limiar porque não entram no gatilho**. Isso é deliberado e é a
razão de o relatório da semana dizer que 32 violações não significam fábrica em conformidade.

### Curva de referência do braço só-humano (v15, campo com verdade 100% humana)

Medida em 289 frames / 403 caixas, todas de mão humana, virgens para os dois braços:

| limiar | propostas | precisão | recall | F1 |
|---:|---:|---:|---:|---:|
| 0,20 | 879 | 0,29 | 0,63 | 0,39 |
| 0,25 | 712 | 0,34 | 0,61 | 0,44 |
| 0,30 | 569 | 0,40 | 0,57 | 0,47 |
| **0,35** | **470** | **0,46** | **0,53** | **0,49** |
| 0,40 | 372 | 0,51 | 0,47 | 0,49 |
| 0,50 | 223 | 0,60 | 0,33 | 0,42 |
| 0,60 | 81 | 0,65 | **0,13** | 0,22 |

A última linha é a razão de o critério ser F1: em 0,60 a precisão é a melhor da tabela **e o modelo
só fala 81 vezes para 403 caixas reais**. Escolher por precisão elegeria quem se cala.

---

## 7 · Custos

| item | valor |
|---|---:|
| GPU terminada (relógio × preço) | **US$ 2,88** — 641 min |
| GPU em curso (`v15-tudo`) | **US$ 0,40** — 71 min |
| **total da missão** | **US$ 3,28** de US$ 12,00 |
| Pods vivos | 1 (o `v15-tudo`), a US$ 0,74/h — teto de US$ 5/pod respeitado |
| Egresso de frame para fora da nuvem | **zero** (D-72) |

**Método, porque os três números disponíveis discordam:** `metrics.gpu_cost.estimated_usd` soma
**US$ 9,34** porque projeta as 50 épocas pedidas, e quase todo treino parou cedo;
`actual_usd` soma **US$ 0,35** e é reconhecidamente best-effort e incompleto. O número acima é
relógio × preço/h, que é o que a RunPod cobra.

**🔴 E medir isso achou mais um "o registro mente".** Um job `stopped` de 20/08 nunca recebeu
`completed_at`. Qualquer consulta de custo que faça `coalesce(completed_at, now())` — a forma
natural de escrever — acumula tempo **para sempre**: hoje ele sozinho soma **6.037 minutos
fantasma**, 100 horas que nunca existiram, e levaria o total a US$ 37,48. Mesma família do
`current_epoch` que dizia 50 tendo rodado 17. Registrado na **#540**; ⛔ não inventei um
`completed_at`, porque a hora do fim é desconhecida e chutá-la seria trocar um número errado por um
plausível.

---|---:|
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
