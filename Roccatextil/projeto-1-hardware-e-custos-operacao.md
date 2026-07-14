# Projeto 1 — Expedição: Hardware NVIDIA e Custos de Operação

**Documento de dimensionamento** · 10/06/2026 · Base: 16 câmeras · Pré-orçamento (interno, não vai para o cliente)

---

## 1. Escopo desta etapa

**Etapa 1 — Contagem:**
- Contar o que está **disponível** na baia e o que está **entrando no caminhão**
- 16 câmeras no total
- Possibilidades futuras deixadas em aberto (classificação por SKU refinada, recebimento, OCR de notas, integrações)

## 2. Computador de visão computacional (NVIDIA)

### Capacidade necessária

Contagem com YOLO (reuso do recognition) não exige 30 fps — **10~15 fps por stream é suficiente** para contagem confiável de rolos. Benchmarks de mercado com DeepStream:

| Equipamento | Capacidade aproximada | Preço Brasil (ref.) |
|---|---|---|
| Jetson Orin Nano 8GB (67 TOPS) | ~4-6 streams 1080p YOLOv8s INT8 | baixo, mas insuficiente sozinho |
| Jetson Orin NX 16GB (157 TOPS) | ~8-11 streams com modelo por stream; até ~40 streams a 5fps com modelo único | ~R$ 14.400 (devkit c/ SSD) |
| **Jetson AGX Orin 64GB (275 TOPS)** | **12-20 streams 1080p30 YOLOv8s INT8; 16 streams usando os 2 DLAs (8 por DLA)** | ~R$ 31.500 (devkit) |
| Jetson AGX Thor (2070 TFLOPS FP4) | Muito acima do necessário | ~US$ 3.499 (devkit) |

### FPS de trabalho (definição)

| Câmera | FPS | Justificativa |
|---|---|---|
| A — disponível na baia | 1-5 fps | Cena quase estática; snapshot periódico basta |
| B — carregamento | 10-15 fps | Capturar cada rolo cruzando a porta do baú sem perder evento |

Trabalhar nessa faixa (em vez de 30 fps) reduz a computação necessária em mais da metade — viabiliza hardware menor.

### Recomendação

**Opção A (otimizada) — 1× Jetson Orin NX 16GB — RECOMENDADA**
- Com modelo único compartilhado e FPS de trabalho acima, atende as 16 câmeras (benchmark: ~40 câmeras a 5 fps com YOLOv8s INT8)
- **~R$ 14.400** — menos da metade do AGX Orin
- Upgrade futuro simples: se recebimento entrar (+6 câmeras) ou FPS subir, adiciona-se um segundo NX

**Opção B — 1× Jetson AGX Orin 64GB (se quisermos folga grande desde o início)**
- Atende as 16 câmeras a 30 fps usando GPU + 2 DLAs (8 streams por DLA)
- ~R$ 31.500 — justifica-se só se formos rodar múltiplos modelos pesados por stream

**Opção C — Jetson AGX Thor**
- Superdimensionado para contagem. Só entra se a visão de futuro (VLMs, inspeção avançada) for contratada desde já.

> Decisão: **Orin NX 16GB** — alinhado ao FPS de trabalho e ao ajuste de expectativa de custo.

## 2.1 Câmeras e gravador (recomendação — 10/06/2026)

### Conceito de contagem (definido em 10/06/2026)

**Não olhamos para dentro do caminhão.** A contagem de saída é por **zona/linha virtual de cruzamento** (line crossing): o tracker atribui ID a cada rolo e contabiliza quando o ID cruza a zona delimitada no sentido de saída. O que já saiu está contabilizado — o interior do baú é irrelevante para a IA.

Implicações:
- Câmera B aponta para a **zona de cruzamento** (batente da doca), de cima/diagonal alta — visão superior elimina oclusão entre rolos e operadores
- Contagem **bidirecional**: rolo que volta pela zona desconta (devoluções)
- FPS de 10-15 garante que a peça não "pule" a linha entre frames
- DeepStream entrega isso nativo (nvtracker + nvdsanalytics line crossing)
- **Paletização:** paletes têm padrão visual padronizado → modelo treina duas classes (rolo avulso e palete-padrão); palete cruzando a zona conta pelos rolos visíveis no padrão ou pela quantidade-padrão do tipo de palete. Imagens dos formatos de paletização entram no dataset de treino.
- **Enquadramento × ROI:** o frame da câmera B pode enquadrar doca + boca do caminhão (evidência visual completa gravada no NVR), mas a IA processa apenas a ROI da zona de cruzamento — ver o abastecimento é posicionamento de câmera, não custo de IA.

### Requisitos por posição

| Posição | Cenário | Requisito-chave |
|---|---|---|
| Câmera A — disponível na baia | Ambiente interno, luz estável, campo amplo | 4MP fixa, lente 2.8mm |
| Câmera B — zona de cruzamento na doca | Área pequena e próxima, vista de cima; sem contraluz (não enquadra a porta aberta) | **2MP basta**, lente 2.8mm, WDR padrão |

### Câmeras recomendadas

| Posição | Modelo | Faixa de preço |
|---|---|---|
| A (6 un.) | **Hikvision DS-2CD2043G2-I** 4MP WDR 120dB (alt.: Intelbras VIP 3430 B IA) | R$ 800-1.000 |
| B (6+ un.) | **Hikvision DS-2CD1023G2** ou **Intelbras VIP 1230 B** 2MP | R$ 400-600 |

Comprar 1-2 sobressalentes de cada. Economia vs. padronizar tudo em 4MP: ~R$ 3-5 mil.

> Decisão fina (lente 2.8 vs 4mm, bullet vs dome, altura de fixação) sai da visita técnica com as medidas reais da doca.

### Gravador (NVR)

**Hikvision DS-7616NI-Q2/16P** (16 canais, 16 portas PoE, 4K, H.265+) — ~R$ 2.600-2.800. Equivalente nacional: **Intelbras NVD 3116 P** (~R$ 2.760).

**Arquitetura:** as câmeras entregam dois streams — **main stream** (4MP) para o NVR gravar evidência, **sub stream** (720p/1080p no FPS de trabalho) para o Jetson processar. O NVR também alimenta as câmeras via PoE, dispensando switch PoE separado.

**Configuração de codec (definida pela capacidade de decode do Jetson):**
- Decoder dedicado (NVDEC) do Orin NX: **H.265 = 18×1080p30** vs. H.264 = 11×1080p30
- → **Padronizar sub-stream H.265 1080p** nas câmeras: 12 câmeras cabem com folga em H.265; em H.264 ficaria no limite
- Encode do Jetson (12×1080p30 H.265) não é gargalo — quem grava é o NVR
- **JetPack 6.2+**: validar compatibilidade do recognition existente (CUDA/TensorRT/DeepStream) nessa versão antes do deploy

**Atenção:** 16 câmeras = 16 canais, NVR no limite. Se o recebimento (+6 câmeras) for provável no curto prazo, considerar já um **DS-7632NI (32 canais)** + switch PoE, pela diferença pequena de preço.

**Armazenamento:** com gravação por evento (só durante carregamentos) e H.265+, 1× HD 8-10 TB "purple" (24/7) cobre ~30 dias de retenção. Gravação contínua dobraria isso (2 baias de HD).

## 3. Custos de operação estimados (sistema rodando)

Premissas: processamento 100% local (edge), operação em 2 turnos (~12h/dia útil — ajustar se 24/7), tarifa de energia industrial R$ 0,75-0,95/kWh, dashboard/banco em nuvem leve.

### 3.1 Energia

| Item | Potência | Consumo mensal (12h/dia, 26 dias) |
|---|---|---|
| Jetson AGX Orin (modo 50W médio) | ~50 W | ~16 kWh |
| 16 câmeras IP PoE (~8 W cada) | ~128 W | ~40 kWh |
| Switch PoE 16+ portas | ~30 W além das câmeras | ~9 kWh |
| NVR/storage local (retenção de vídeo) | ~40 W | ~12 kWh |
| **Total energia** | **~250 W** | **~77 kWh → R$ 60-75/mês** |

*(Se 24/7: ~180 kWh → R$ 135-170/mês. Energia é custo marginal — não é o driver.)*

### 3.2 Nuvem e software (mensal)

| Item | Estimativa mensal |
|---|---|
| VPS/nuvem para dashboard + banco de eventos (contagens, não vídeo) | R$ 150 - 400 |
| Backup dos eventos/imagens de evidência (object storage, ~50-100 GB) | R$ 30 - 80 |
| Monitoramento remoto (uptime, VPN/acesso) | R$ 0 - 100 |
| **Licença do modelo** — Ultralytics YOLO é AGPL: uso comercial fechado exige licença Enterprise (cotar) **ou** usar alternativa permissiva (YOLOX, RT-DETR, YOLO-NAS) | R$ 0 ou cotação |
| **Subtotal nuvem/software** | **R$ 180 - 580 + licença** |

### 3.3 Operação contínua (mensal, internos nossos)

| Item | Estimativa |
|---|---|
| Suporte/monitoramento (horas de engenharia, ~4-8 h/mês após estabilização) | R$ 800 - 2.000 |
| Re-treino periódico do modelo (novos SKUs/embalagens, trimestral — GPU em nuvem ou local) | R$ 100 - 300/mês amortizado |
| Reserva para manutenção de hardware (limpeza de câmera, troca de disco — % do CAPEX/ano) | R$ 150 - 300/mês |
| **Subtotal operação** | **R$ 1.050 - 2.600** |

### 3.4 Cenário otimizado (ajuste de expectativa — 10/06/2026)

Alavancas aplicadas:
- **Hardware:** Orin NX 16GB em vez de AGX Orin (FPS de trabalho reduzido permite)
- **Nuvem R$ 0:** dashboard + banco rodando no próprio Jetson ou em servidor existente; evidências em disco local
- **Modelo com licença permissiva** (YOLOX ou RT-DETR, Apache 2.0): licença R$ 0
- **Re-treino sob demanda** (só quando entra SKU/embalagem nova), não periódico
- **Suporte diluído:** monitoramento automatizado (watchdog/alertas), intervenção humana só por exceção

| Item | Otimizado (mensal) |
|---|---|
| Energia (~150 W com NX, 12h/dia) | ~R$ 40-55 |
| Nuvem/licenças | R$ 0 - 100 |
| Suporte por exceção + reserva de manutenção | R$ 300 - 700 |
| **Total OPEX otimizado** | **~R$ 350 - 850/mês** |

### Resumo dos cenários

| Cenário | Custo mensal estimado |
|---|---|
| **Otimizado (referência para proposta)** | **~R$ 350 - 850/mês** |
| Conservador (nuvem dedicada, suporte ativo, 24/7) | ~R$ 1.300 - 3.300/mês |

> Este é o NOSSO custo de rodar o sistema — base para precificar a mensalidade do cliente (SaaS/serviço) com margem. Não inclui CAPEX.

### 3.5 CAPEX de referência

> Superado — ver valores reais cotados na seção 3.6.

## 3.6 Custo total da solução (consolidado pós-ajustes — 10/06/2026)

> Custos NOSSOS (base para precificação). Não é o preço ao cliente.

### CAPEX — Infraestrutura (valores reais cotados — 10/06/2026)

| Item | Valor |
|---|---|
| Jetson Orin NX 16GB | R$ 16.000 |
| 6× câmera 4MP (posições A, R$ 700 un.) | R$ 4.200 |
| 6× câmera 2MP (posições B/zona, R$ 429 un.) | R$ 2.574 |
| NVR 16 canais | R$ 1.300 |
| HD | R$ 1.300 |
| Switch | R$ 500 |
| Cabeamento e infraestrutura | R$ 1.338 |
| **Subtotal infraestrutura (12 câmeras)** | **R$ 27.212** |

*Não incluído: nobreak, mão de obra de instalação física e sobressalentes — confirmar se entram.*

### Desenvolvimento (nosso esforço, com reuso do recognition + módulo de carregamento)

| Frente | Estimativa de horas |
|---|---|
| Dataset + treino do modelo (rolos, paletes, zona) | 60 - 100 h |
| Pipeline DeepStream (16 streams, line crossing, tracker) | 60 - 100 h |
| Conciliação pedido × carregado × saldo + tela do operador | 80 - 120 h |
| Dashboard/indicadores + relatórios | 40 - 80 h |
| Instalação, calibração das zonas, testes em campo | 40 - 80 h |
| **Total** | **~280 - 480 h** |

A valor de hora interna de R$ 100-150: **~R$ 28.000 - 72.000** de desenvolvimento.

### Totais

| Componente | Valor |
|---|---|
| CAPEX infra (cotado) | R$ 27.212 |
| Mão de obra física (instalação) | R$ 2.200 |
| Desenvolvimento (definido — reuso pesado) | R$ 7.500 |
| **Custo total do projeto (nosso)** | **R$ 36.912** |
| OPEX mensal (sistema rodando) | R$ 350 - 850/mês |

**Modelo de cobrança sugerido ao cliente:** setup (infra + implantação) + mensalidade (operação + suporte + evolução), com margem sobre os números acima.

## 3.7 Precificação (análise — 10/06/2026)

> Análise interna de apoio à decisão. Alíquotas dependem do regime tributário da empresa — **validar com o contador antes de fechar preço.**

**Base de custo:** R$ 36.324 (infra cotada + instalação + desenvolvimento).

### Impostos — pontos de atenção

- **Serviço (desenvolvimento, implantação, mensalidade) → ISS**, não ICMS. Carga típica sobre receita de serviço: ~6-16% (Simples Anexo III/V) ou ~13-16% (Lucro Presumido: ISS + PIS/COFINS + IRPJ/CSLL).
- **Hardware → ICMS** incide se NÓS revendermos o equipamento (alíquota varia por estado, ~12-20%, + diferença de regime).
- **Alternativa recomendada:** o cliente compra o hardware diretamente em nome dele (nós especificamos, ele adquire, nós instalamos). Elimina ICMS da nossa nota, reduz nossa base tributável e o cliente fica dono do ativo. Nossa receita vira 100% serviço.

### Cenários de preço (assumindo ~15% de imposto sobre receita)

Fórmula: preço = custo × (1 + margem) / (1 − imposto)

| Cenário | Margem | Preço de setup |
|---|---|---|
| Piso (não descer abaixo) | 30% | ~R$ 55.500 |
| Alvo | 45% | ~R$ 62.000 |
| Âncora (abertura de negociação) | 60% | ~R$ 68.500 |

**Mensalidade:** custo R$ 350-850 → cobrar **R$ 1.500 - 2.500/mês** (suporte + evolução + margem). Receita recorrente é onde o contrato fica saudável a longo prazo.

### DECISÃO DE PRECIFICAÇÃO (10/06/2026)

| Item | Decisão |
|---|---|
| Lucro-alvo na implantação | **R$ 15.000 líquidos** |
| Preço de setup correspondente (com ~15% imposto) | (36.324 + 15.000) ÷ 0,85 ≈ **R$ 60.400** — apresentar como R$ 59.900-62.000 e negociar |
| Mensalidade | **R$ 2.900/mês** (custo R$ 350-850 → margem líquida ~R$ 1.600-2.100/mês; folga para negociar até ~R$ 2.000 sem comprometer) |
| Racional estratégico | Margem moderada de propósito: **o Projeto 2 (pátio de contêineres) é o contrato maior** — o Projeto 1 constrói confiança e referência. Não espremer o cliente agora. |

*Recorrência a R$ 2.900: ~R$ 19-25 mil/ano de margem líquida — em 2 anos supera o lucro da implantação.*

### Condições comerciais — cliente sem CAPEX, com OPEX (10/06/2026)

Objetivo: converter o investimento em mensalidade. Referência: setup-alvo R$ 60,4 mil + mensalidade R$ 2.900.

**Opção 1 — Assinatura full-OPEX (HaaS — "solução como serviço")**
- Hardware é NOSSO; cliente paga só mensalidade com fidelidade
- 36 meses: ~R$ 5.200/mês · 24 meses: ~R$ 5.900/mês (já com prêmio de capital ~15%)
- Proteções obrigatórias: fidelidade com multa rescisória decrescente, hardware nosso até o fim, reajuste anual (IPCA/IGP-M), SLA definido
- Bônus: após o prazo, renovação só da mensalidade base (R$ 2.900) — cliente sente "redução"

**Opção 2 — Híbrida: adesão pequena + mensalidade maior — ✅ ESCOLHIDA (10/06/2026)**
- **Condições fechadas para proposta:** entrada R$ 15.000 · 36 meses · 1ª mensalidade 10 dias após a ativação · valores sujeitos a correção anual
- Adesão R$ 15-20 mil (cobre boa parte do hardware — nosso caixa não fica tão exposto)
- Mensalidade R$ 4.200-4.500 por 30-36 meses, depois cai para a base
- Equilibra nosso fluxo de caixa e o CAPEX limitado do cliente

**Opção 3 — Hardware direto no fornecedor, serviço como OPEX**
- Cliente compra os R$ 26,6 mil de equipamento direto (parcelável em 10-12× no fornecedor/cartão — vira quase OPEX pra ele)
- Nós cobramos: implantação R$ 12-15 mil (parcelável 3-4×) + mensalidade R$ 3.400-3.900 (mensalidade base + diluição do desenvolvimento)
- Menor exposição de caixa nossa; sem ICMS na nossa nota

**Atenção (qualquer opção):** nosso desembolso inicial é ~R$ 36 mil. Na Opção 1, o payback chega em ~7-9 meses de mensalidade — precificar a multa rescisória para nunca ficarmos no prejuízo se o cliente sair cedo.

### Divisão interna Lucas × CATH (análise — 10/06/2026)

**Quem investe o quê:**

| Parte | Investimento | Papel contínuo |
|---|---|---|
| Lucas | R$ 7.500 (desenvolvimento) | Software, suporte, monitoramento, re-treino, evolução (OPEX ~R$ 350-850/mês) |
| CATH | R$ 29.412 (hardware R$ 27.212 + instalação R$ 2.200) | Manutenção física do hardware |

**Princípio da divisão:** capital se amortiza uma vez; trabalho é contínuo. A mensalidade não é só retorno de capital — ela paga a operação viva do sistema (que é do Lucas). Por isso a divisão proporcional ao investimento (80/20 para CATH) seria distorcida.

**Proposta de divisão:**

| Fluxo | CATH | Lucas |
|---|---|---|
| Entrada (R$ 15.000) | **100% → R$ 15.000** (recupera metade do hardware no dia 1) | — |
| Mensalidade (R$ 4.500) | **R$ 1.500/mês** (locação do hardware + manutenção física) | **R$ 3.000/mês** (software, suporte, monitoramento, evolução) |

**Resultado em 36 meses:**

| | CATH | Lucas |
|---|---|---|
| Recebe | 15.000 + 54.000 = **R$ 69.000** | **R$ 108.000** |
| Investe/custa | 29.412 + manutenção (~R$ 5-8 mil) | 7.500 + operação (~R$ 15-20 mil) |
| **Lucro estimado** | **~R$ 32-35 mil** (ROI >100% sobre o capital) | **~R$ 80-85 mil** (remunera o trabalho contínuo) |
| Payback | ~Mês 10 | Imediato (dev coberto nos 3 primeiros meses) |

**Sensibilidade:** se a CATH quiser payback mais rápido, sobe a cota para R$ 1.800/mês (payback ~mês 8; Lucas fica com R$ 2.700). Se negociarem a mensalidade do cliente para baixo (até R$ 4.200), o desconto sai proporcionalmente de cada cota.

**A formalizar entre as partes:** propriedade do hardware (sugestão: CATH até o fim do contrato), quem responde pelo SLA de hardware vs. software, e o que acontece com as cotas em caso de rescisão antecipada (multa deve cobrir primeiro o saldo não amortizado da CATH).

### Leitura do "7 de 10" de disposição a investir

7 = o cliente enxerga valor e tem orçamento, mas não compra "a qualquer preço" — sensível a risco e a número cheio. Táticas:

- Manter o setup **abaixo de R$ 70 mil** (barreira psicológica provável para um 7)
- Abrir na âncora (~R$ 68,5 mil) e ceder até o alvo (~R$ 62 mil) trocando concessão por algo (contrato de mensalidade mais longo, sinal maior)
- Se o cliente comprar o hardware direto (~R$ 26,6 mil em nome dele), nossa proposta de serviço cai para ~R$ 28-38 mil — número muito mais leve, mesma margem
- Vender a Etapa 1 como fase de um roadmap (recebimento, SKU, indicadores avançados depois) — o 7 tende a virar 8-9 depois do primeiro resultado visível

## 4. Indicadores (KPIs) que podemos construir

**Disponíveis já na Etapa 1 (contagem):**
- Rolos carregados por dia / por baia / por cliente-pedido
- Saldo disponível por baia em tempo real
- Divergência pedido informado × carregado (un. e %)
- Tempo médio de carregamento por caminhão/baia
- Ocupação das baias (tempo ocioso × em carregamento)
- Produtividade por turno e ranking de baias
- Curva de horário de pico de expedição

**Possíveis no futuro (deixar em aberto na apresentação):**
- Contagem por SKU/tipo de tecido e giro por produto
- Recebimento × expedição (balanço de estoque do galpão)
- Acuracidade de estoque (visão × ERP)
- Evidência fotográfica por carregamento (anti-disputa com cliente)
- Alertas em tempo real de divergência durante o carregamento

## 5. Próximos passos

1. Validar horário real de operação (12h vs. 24/7) — muda pouco o custo, mas muda o SLA
2. Decidir modelo: licença Ultralytics Enterprise vs. migrar para alternativa permissiva
3. Cotar câmeras (modelo específico conforme distância baia-caminhão na visita técnica)
4. Com OPEX fechado → montar apresentação com orçamento (CAPEX + mensalidade)

---

*Fontes: [NVIDIA Jetson Orin](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/), [NVIDIA — Buy Jetson](https://developer.nvidia.com/buy-jetson), [Jetson Thor](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-thor/), [DeepStream Performance](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Performance.html), [Benchmarks YOLOv8 em Jetson — Seeed](https://www.seeedstudio.com/blog/2023/03/30/yolov8-performance-benchmarks-on-nvidia-jetson-devices/), [DeepStream-Yolo #605](https://github.com/marcoslucianops/DeepStream-Yolo/issues/605), [Kabum — AGX Orin 64GB](https://www.kabum.com.br/produto/924837/nvidia-kit-developer-jetson-agx-orin-64gb-275-tops-945-13730-0050-000), [Techno Store — Orin NX 16GB](https://technostorebr.com.br/produto/nvidia-jetson-orin-nx-16gb-developer-kit-modulo-nvidia-jetson-orin-nx-16gb-900-13767-0000-000-128gb-ssd/). Preços de junho/2026, sujeitos a variação.*
