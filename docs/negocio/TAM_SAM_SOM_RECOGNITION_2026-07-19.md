# TAM / SAM / SOM — Recognition (Logikos)

**Data:** 2026-07-19 · **Metodologia:** SEBRAE RS / Sequoia (Market Size → TAM → SAM → SOM)
**Modelo de receita:** Setup + mensalidade · **Alvo de SOM:** Vale do Itajaí / Santa Catarina

> **Regra deste documento:** todo número está marcado como **[FONTE]** (dado primário verificável),
> **[DERIVADO]** (calculado a partir de fonte, com a conta exposta) ou **[PREMISSA]** (arbitrado por nós).
> Um investidor vai atacar exatamente os [PREMISSA] — então eles estão isolados e com sensibilidade calculada.
>
> A metodologia SEBRAE recomenda **top-down** para Market Size e TAM, **bottom-up** para SAM e SOM. É o que segue.

---

## 0. Premissas de preço (a base de tudo)

Modelo escolhido: **taxa de implantação + mensalidade recorrente**.

| Item | Valor | Natureza |
|---|---|---|
| **Setup** (edge Jetson + instalação + treino do modelo inicial) | **R$ 20.000** | [PREMISSA] |
| **Mensalidade** | **R$ 50 / câmera / mês** | [PREMISSA], calibrada pelo benchmark |
| Site médio (indústria média) | 25 câmeras | [PREMISSA] |
| **Receita recorrente / cliente / ano** | **R$ 15.000** | [DERIVADO] 25 × 50 × 12 |
| **Receita ano 1 / cliente (setup + 12 meses)** | **R$ 35.000** | [DERIVADO] |

**Calibragem do benchmark internacional** [FONTE, baixa confiança — nenhum player nomeado publica preço]:
US$ 3–15/câmera/mês entry a mid-tier; **~US$ 18/câmera/mês** para módulos especializados de manufatura
(Wavestore, 2026). A US$ 18 ≈ R$ 100/câmera/mês. **Nossa premissa de R$ 50 é metade do benchmark**, coerente com
(a) modelo híbrido que já captura margem no setup e (b) posicionamento em indústria média regional, não enterprise.

---

## 1. Market Size — R$ 16 bilhões/ano

**Segurança eletrônica no Brasil, faturamento 2025: mais de R$ 16 bilhões** [FONTE: Panorama ABESE 2025/2026,
divulgado na Exposec jun/2026], com crescimento de **+16,2%** sobre 2024 e projeção de **+18,8% para 2026**.

Série: R$ 12 bi (2023) → R$ 14 bi (2024) → R$ 16 bi (2025) [FONTE: ABESE].

Três dados do mesmo Panorama que importam para a tese:

- **IA está presente em 85,7% dos produtos** fabricados pelo setor — era 64% no Panorama anterior. **Salto de 21
  pontos em um ano.** O mercado não está sendo educado sobre IA; ele já assumiu IA como padrão.
- O segmento de **desenvolvedores de software projeta +21%** para 2026 — cresce acima da média do setor.
- **Mercado empresarial é 71%** do destino das prestadoras de serviço.

> Este é o "bolo inteiro" da segurança eletrônica. **Não é nosso TAM** — inclui hardware, alarme, controle de
> acesso, monitoramento humano e instalação, coisas que não vendemos.

---

## 2. TAM — R$ 322 milhões/ano (recorrente), Brasil

O TAM é a fatia do Market Size que corresponde ao **nosso** produto: software de visão computacional sobre CFTV
existente, para indústria brasileira com porte suficiente para justificar a solução.

**Construção [DERIVADO]:**

| Passo | Número | Origem |
|---|---|---|
| Empresas industriais no Brasil | **358,4 mil** | [FONTE: IBGE, PIA-Empresa 2024, pub. 24/06/2026] |
| Filtro de porte: ≥ 50 funcionários | **~6%** | [PREMISSA] — ver justificativa abaixo |
| **Indústrias endereçáveis** | **~21.500** | [DERIVADO] 358.400 × 6% |
| Receita recorrente / cliente / ano | R$ 15.000 | [PREMISSA §0] |
| **TAM recorrente** | **≈ R$ 322 milhões / ano** | [DERIVADO] |
| TAM incluindo setup amortizado em 5 anos | ≈ R$ 408 mi/ano | [DERIVADO] +21.500 × 20k ÷ 5 |

**Justificativa do filtro de 6%** [PREMISSA — o ponto mais frágil do documento]:
O CEMPRE 2024 [FONTE: IBGE, pub. 25/06/2026] mostra que, no total de empresas brasileiras, **0,8% têm 50–249
assalariados e 0,2% têm 250+** — 1% no agregado. Mas esse agregado inclui 71,6% de empresas **sem nenhum
assalariado**, que distorcem para baixo. A indústria tem distribuição de porte estruturalmente maior que serviços:
concentra 15,3% dos assalariados do país em 13,4% do pessoal ocupado, e **empresas industriais de 500+ pessoas
respondem por 67,9% da receita líquida industrial** [FONTE: PIA 2024].
Adotamos **6%** como estimativa conservadora do recorte industrial com 50+ funcionários.

⚠️ **Este número precisa ser fechado com dado primário** — ver §7, Lacuna 1 (tabela SIDRA 2718).

**Por que 50 funcionários é o corte:** abaixo disso, a planta raramente tem CFTV com densidade suficiente,
equipe de SST dedicada, ou orçamento para R$ 20k de implantação. É o piso de viabilidade econômica, não de
utilidade técnica.

> **Nota de sanidade:** R$ 322 mi é ~2% do Market Size de R$ 16 bi. É uma proporção plausível para "software de
> analytics de vídeo para indústria" dentro de "toda a segurança eletrônica do país" — e é um TAM *honesto*.
> Apresentar os R$ 16 bi como TAM seria o erro clássico que o próprio artigo do SEBRAE alerta.

---

## 3. SAM — R$ 45 milhões/ano, Santa Catarina

O SAM é o que conseguimos servir **com o produto e o modelo atuais**, na geografia de foco.

**Construção [DERIVADO]:**

| Passo | Número | Origem |
|---|---|---|
| Indústrias em Santa Catarina | **~50 mil** | [FONTE: FIESC] ⚠️ ver ressalva |
| Filtro ≥ 50 funcionários | ~6% | [PREMISSA, mesma do TAM] |
| **Indústrias endereçáveis em SC** | **~3.000** | [DERIVADO] |
| Receita recorrente / cliente / ano | R$ 15.000 | [PREMISSA §0] |
| **SAM recorrente** | **≈ R$ 45 milhões / ano** | [DERIVADO] |

⚠️ **Ressalva de fonte:** a FIESC publica **"mais de 63 mil indústrias"** em uma página e **"mais de 50 mil"** em
outra, **nenhuma das duas datada**. Adotamos 50 mil (o menor) por conservadorismo. Confirmar com o Observatório
FIESC antes de usar externamente — ver §7, Lacuna 2.

**Por que Santa Catarina é um SAM legítimo, e não apenas conveniente:**

- **Indústria é 34% do emprego formal de SC** — a maior taxa do país, contra média nacional de 21% [FONTE: FIESC]
- Indústria = 28,5% do PIB estadual, 6º maior do país [FONTE: FIESC]
- SC teve o **maior número de estabelecimentos industriais por mil habitantes do Brasil** (~7/mil) [FONTE:
  Observatório FIESC — ⚠️ dado de 2019, antigo]

Ou seja: SC não é só "onde estamos". É, por densidade industrial, um dos melhores territórios do país para este
produto especificamente.

**Recorte do Vale do Itajaí** [FONTE: FIESC, release sobre polos industriais do Vale]:

| Recorte | Indústrias | Empregados industriais | Endereçáveis (6%) [DERIVADO] |
|---|---|---|---|
| **Vale do Itajaí** | **21,5 mil** | 276,6 mil | **~1.290** |
| Blumenau | 3,2 mil | 50,2 mil | ~192 |
| Brusque | 2,0 mil | 28,6 mil | ~120 |
| Itajaí | 1,9 mil | 27,4 mil | ~114 |

O Vale do Itajaí foi a **2ª região do país em geração de empregos industriais** em 2024, com 13.826 postos entre
janeiro e agosto, atrás apenas da Região Metropolitana de São Paulo [FONTE: FACISC/FIESC].

**SAM do Vale do Itajaí isolado:** ~1.290 × R$ 15.000 = **≈ R$ 19,4 milhões/ano** [DERIVADO].

---

## 4. SOM — R$ 600 mil de ARR em 3 anos (cenário base)

O SOM é o que **realisticamente capturamos**, considerando concorrência, capacidade de entrega e canal. É o
número que vai no plano de negócio — e o único que precisa ser matematicamente defensável.

### Cenários

| | Ano 1 | Ano 2 | Ano 3 | ARR ano 3 | Receita ano 3 | % do SAM Vale |
|---|---|---|---|---|---|---|
| **Conservador** | 3 | 10 | 20 clientes | R$ 300 mil | R$ 500 mil | 1,6% |
| **Base** | 4 | 16 | **40 clientes** | **R$ 600 mil** | **R$ 1,08 mi** | **3,1%** |
| **Otimista** | 6 | 25 | 65 clientes | R$ 975 mil | R$ 1,78 mi | 5,0% |

*Receita ano 3 = ARR + (novos clientes do ano × R$ 20.000 de setup). Cenário base: R$ 600k + 24 × R$ 20k = R$ 1,08 mi.*

### Por que o cenário base é defensável

**Capacidade de entrega, não demanda, é o limitante.** Cada cliente exige instalação física do edge, treino de
modelo próprio (é a tese do produto — cada cliente treina o seu) e configuração de cenário. No ritmo do cenário
base, o ano 3 pede **2 implantações por mês** — que é o teto realista de uma equipe pequena sem canal de parceiros.

**3,1% do SAM do Vale em 3 anos é penetração modesta.** Se o número parecesse alto, seria sinal de premissa
errada. Aqui ele é conservador de propósito: significa que **97% do mercado-alvo imediato continua aberto** ao
fim do horizonte — o que é exatamente o que um investidor quer ver.

**Referência de mercado:** a **Pix Force** (Porto Alegre), concorrente direta com os mesmos três módulos, faturou
**R$ 12 milhões em 2023** com meta de R$ 16 mi em 2024 [FONTE: Exame], atendendo Petrobras, Shell, CPFL e Cemig.
Nosso cenário base no ano 3 é **menos de 10% do faturamento dela** — e num segmento (indústria média regional)
que ela não ataca. A comparação sustenta que o número não é fantasioso nem em excesso nem por baixo.

### Sensibilidade ao preço (o número mais volátil)

| Mensalidade | Receita recorrente/cliente/ano | ARR ano 3 (40 clientes) |
|---|---|---|
| R$ 30/câmera | R$ 9.000 | R$ 360 mil |
| **R$ 50/câmera** | **R$ 15.000** | **R$ 600 mil** |
| R$ 80/câmera | R$ 24.000 | R$ 960 mil |
| R$ 100/câmera (benchmark internacional) | R$ 30.000 | R$ 1,2 milhão |

> **Leitura:** dobrar o preço dobra o ARR sem mudar o esforço de entrega. **A alavanca mais forte do negócio não
> é vender mais rápido — é provar valor que sustente ticket maior.** Ver §6.

---

## 5. Resumo visual

```
MARKET SIZE  ─ Segurança eletrônica Brasil ......... R$ 16.000.000.000 / ano   [ABESE 2025]
    │
    ├── TAM  ─ Indústria BR 50+ func., SaaS de CV .. R$    322.000.000 / ano   (~21.500 empresas)
    │         ~2% do Market Size
    │
    ├── SAM  ─ Santa Catarina ...................... R$     45.000.000 / ano   (~3.000 empresas)
    │         14% do TAM
    │         └── Vale do Itajaí .................. R$     19.400.000 / ano   (~1.290 empresas)
    │
    └── SOM  ─ 3 anos, cenário base ................ R$        600.000 ARR     (40 clientes)
              3,1% do SAM do Vale · 1,3% do SAM SC
```

---

## 6. Leitura estratégica — o que os números dizem

### 6.1 A obrigação legal já existe. Não estamos criando categoria.

A **NR-6** obriga o empregador a *"exigir o uso"* e *"fiscalizar a utilização correta"* do EPI [FONTE: MTE, texto
da norma]. Hoje isso é cumprido com ronda humana e assinatura em papel. **Não vendemos uma inovação opcional —
automatizamos uma obrigação normativa mal cumprida.** Isso muda a conversa de "por que eu preciso disso?" para
"como você prova que cumpre isso hoje?".

### 6.2 O relógio regulatório está tocando agora

- **NR-1 (GRO/PGR):** a atualização de mai/2025 incorporou riscos psicossociais; a fase educativa foi até
  25/05/2026 e **a fiscalização punitiva plena começou em 26/05/2026** [FONTE: MTE]. Já está valendo.
- **Portaria MTE nº 104/2026 (30/01/2026)** alterou o Anexo II da NR-28, atualizou códigos de infração, reajustou
  penalidades e — o item mais relevante — criou o **item 28.3.3, que institui reajuste anual automático das
  multas** [FONTE: informe técnico FIERGS, fev/2026].

A demanda por **evidência documentada de conformidade** está subindo estruturalmente **agora**, não num futuro
hipotético. É uma janela, não uma tendência de longo prazo.

### 6.3 O FAP é o argumento de ROI que ninguém está usando

Este é, na minha leitura, **o achado comercial mais valioso da pesquisa**.

O **RAT** é 1%, 2% ou 3% da folha conforme o risco da atividade. O **FAP** multiplica isso por um fator de
**0,5 a 2,0**, conforme o desempenho acidentário da empresa comparado à média do seu setor [FONTE: Receita
Federal]. A alíquota efetiva varia, portanto, de **0,5% a 6% da folha** — uma amplitude de **12 vezes**.

**Exemplo [DERIVADO, premissas explícitas]:** indústria com 300 funcionários, folha média R$ 3.000/mês →
folha anual ≈ R$ 10,8 milhões. Atividade de risco grave (RAT 3%):

| Cenário | Alíquota efetiva | Custo anual |
|---|---|---|
| FAP 2,0 (pior que a média do setor) | 6,0% | **R$ 648.000** |
| FAP 0,5 (melhor que a média) | 1,5% | **R$ 162.000** |
| **Diferença** | | **R$ 486.000 / ano** |

Contra um custo de **R$ 20.000 de setup + R$ 15.000/ano**. O sistema se paga com **3% da economia potencial**.

Três razões que tornam esse argumento forte:
1. **É auditável** — o FAP é publicado pelo próprio INSS no DOU, verificável no eSocial. Não é promessa de vendor.
2. **Sai do orçamento de tributos, não do de TI** — muda o interlocutor e o bolso.
3. **Nenhum concorrente pesquisado ancora a proposta de valor nisso.** É espaço aberto de posicionamento.

**É também a resposta para a sensibilidade de preço da §4:** quem consegue conectar o produto a R$ 486 mil/ano
de economia tributária não precisa cobrar R$ 50/câmera.

### 6.4 A dor tem tamanho

- **742,2 mil** notificações de acidente de trabalho projetadas para 2024, com **2,4 mil óbitos** [FONTE:
  Observatório SST — SmartLab, MPT/OIT]. Número concorrente do MTE/eSocial: 724.228 [FONTE: MTE] — metodologias
  diferentes; citar uma e dizer qual.
- **8,8 milhões de acidentes e 32 mil mortes** acumulados de 2012 a 2024 no emprego formal [FONTE: SmartLab].
- **Uma notificação de óbito no trabalho a cada 3,5 horas** [FONTE: INSS via SmartLab].
- Gasto do INSS com benefícios acidentários desde 2012: **R$ 173 bilhões** [FONTE: SmartLab]. Em 2024
  especificamente: ~R$ 914 milhões em B91/B92/B93/B94 [FONTE: SmartLab].
- **Indústria de transformação está entre os setores mais atingidos** [FONTE: SmartLab].

⚠️ **Dois números que circulam e NÃO devem ser usados:** "R$ 468 bi/ano" é uma derivação de terceiro aplicando a
estimativa da OIT (4% do PIB mundial) ao PIB brasileiro — não é medição. E "R$ 100 bi" (Jusbrasil) não tem fonte
confiável. Usar qualquer um deles derruba a credibilidade do resto do dossiê.

### 6.5 O espaço competitivo

| Player | Origem | Capital / porte | Alvo |
|---|---|---|---|
| **Intenseye** | Global | **US$ 64 mi** Series B (fev/2024), Lightspeed + Insight | Enterprise global |
| **Protex AI** | Global | **US$ 36 mi** Series B (jan/2025) | Enterprise, tese *privacy-first* |
| **Voxel** | Global | US$ 12 mi (2023), liderada pela Rite-Hite | Manufatura/logística |
| **Pix Force** | 🇧🇷 Porto Alegre | R$ 12 mi faturamento (2023) | **Petrobras, Shell, CPFL, Cemig** |
| **Quickium (SafeWatch)** | 🇧🇷 | 1º lugar prêmio ABDI/Finep/Nestlé | Posicionamento idêntico ao nosso |

**Três leituras:**

1. **O espaço aberto é indústria média regional.** A Pix Force, líder brasileira, atende contas de energia e óleo
   e gás. Enterprise players não atendem uma indústria de 300 pessoas em Blumenau **economicamente** — o custo de
   aquisição não fecha. É exatamente onde a RVB está.
2. **A tese edge/privacidade tem validação de mercado.** A Protex AI levantou **US$ 36 milhões** vendendo
   processamento local e residência de dados como diferencial. Nossa arquitetura (Jetson no site, câmeras que
   nunca saem da LAN, WireGuard outbound) **é essa tese** — e no Brasil, sob LGPD e com câmeras Hikvision/Intelbras
   que travam se expostas, o argumento é mais forte, não menos.
3. **A Quickium tem posicionamento idêntico** ("adapta-se às câmeras de vigilância comuns que as empresas já
   possuem") e ganhou o prêmio ABDI/Finep/Nestlé, com a Pix Force em 2º. **É o concorrente a monitorar de perto.**

### 6.6 O módulo que puxa a narrativa é o EPI

| Mercado | CAGR | Leitura |
|---|---|---|
| Video analytics / AI video surveillance | **21% a 31%** | [FONTE: Precedence, Grand View, MarketsandMarkets] |
| Machine vision (inspeção industrial) | **8,3% a 13%** | [FONTE: Grand View, Fortune BI, Mordor] |

O módulo **Qualidade** vive num mercado maduro de crescimento moderado. O módulo **EPI/segurança** vive no mercado
quente, com obrigação legal, relógio regulatório e ROI tributário. **A narrativa comercial deve liderar por EPI**,
com Qualidade e Contagem como expansão de conta (upsell), não como porta de entrada.

Isso tem implicação de produto: reforça priorizar a maturidade do módulo EPI e da evidência de conformidade
acima do refinamento do detector de qualidade — que hoje, aliás, **nem tem dataset rotulado**.

---

## 7. Lacunas de dado — o que fechar antes de usar isso externamente

| # | Lacuna | Como fechar | Impacto |
|---|---|---|---|
| **1** | **Contagem de indústrias brasileiras por faixa de porte** — o filtro de 6% é [PREMISSA] | **Tabela SIDRA 2718** (CEMPRE: nº de empresas por seção CNAE e faixa de pessoal assalariado). Extração manual — a API estava bloqueada na pesquisa | 🔴 **Alto** — é a base do TAM e do SAM |
| **2** | **Nº de indústrias em SC**: FIESC publica 50 mil e 63 mil em páginas distintas, **ambas sem data** | Solicitar ao Observatório FIESC com ano e metodologia | 🔴 **Alto** — base do SAM |
| **3** | Estabelecimentos por setor (têxtil, metalurgia, alimentos) em SC | SIDRA / RAIS | 🟡 Médio — refina o ICP |
| **4** | Valores absolutos das multas por código da NR-28 pós-Portaria 104/2026 | Baixar Anexos I e II da norma em gov.br | 🟡 Médio — reforça o pitch |
| **5** | Base instalada de câmeras CFTV no Brasil **em unidades** | ABESE publica faturamento, não unidades. Talvez não exista | 🟢 Baixo |
| **6** | Preço praticado por concorrente nomeado | Nenhum publica. Só via cliente/proposta perdida | 🟡 Médio — calibra o ticket |

**Nota metodológica importante:** os relatórios globais de EHS software **foram descartados de propósito**. As
estimativas para 2025 variam de **US$ 2,26 bi (Mordor) a US$ 52,2 bi (Market.us)** — fator de 23×. Não é ruído,
são definições de mercado diferentes. Usar qualquer um como TAM seria indefensável numa due diligence. **Por isso
o TAM foi construído bottom-up sobre IBGE**, e não top-down sobre relatório pago.

---

## 8. Como apresentar isto (e o que evitar)

**Faça:**
- Apresente o **TAM de R$ 322 mi**, não o Market Size de R$ 16 bi. O artigo do SEBRAE alerta exatamente para o
  erro de "apresentar números enormes com projeções irreais" — que *assusta* investidores em vez de atraí-los.
- Mostre o **SOM como fatia pequena de um SAM grande** (3,1%). Isso demonstra consciência de execução.
- Ancore no **FAP** e na **NR-6**, não em "IA de ponta". O comprador é gerente de SST ou CFO, não CTO.
- Cite a **Pix Force** você mesmo, antes que perguntem. Mostrar que conhece o concorrente e sabe por que o
  segmento dele é diferente do seu é sinal de maturidade.

**Evite:**
- Os números de custo de acidente sem fonte (R$ 468 bi, R$ 100 bi) — são derivações e blogs. Derrubam o resto.
- Misturar fontes de mercado incompatíveis (IMARC coloca CCTV Brasil em US$ 3,3 bi; Mordor coloca o mercado
  *inteiro* de video surveillance em US$ 1,5 bi — usar as duas juntas é contradição visível).
- Apresentar os 6% de filtro de porte como dado. **É premissa nossa** — e é o primeiro ponto que um analista
  competente vai atacar. Feche a Lacuna 1 antes de qualquer apresentação a investidor.
