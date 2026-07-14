# Pesquisa de Mercado e Boas Práticas — Recognition Carga & Descarga

**Deep research** · 11/06/2026 · 4 frentes pesquisadas em paralelo, fontes citadas ao fim de cada seção
**Uso:** orientar o desenvolvimento do módulo (Fase 1: contagem + auditoria + dashboard, só expedição, sem SKU)

---

## 1. Como os concorrentes fazem (sistemas reais de visão em doca)

| Player | O que faz | Como faz |
|---|---|---|
| **Vimaan DockTRACK** | Verificação de recebimento/expedição: conta caixas, lê barcodes/OCR, detecta avarias | "Gate" de câmeras multi-sensor no dock door; captura 5 faces do palete em <1s com a empilhadeira passando; integração WMS; app com prova visual (fotos + timestamp). Claim: >99,8% acurácia (fabricante) |
| **Zebra SmartPack (TM2000)** | Monitora o interior do trailer durante carregamento: densidade, taxa de carga, % completo | Câmera 2D + sensor de profundidade 3D acima do dock door apontando pro trailer; servidor calcula métricas **por "load" (= nossa sessão)**; integra ERP/WMS |
| **Peak/Siena Analytics** | Compliance de pacotes em alto volume | Túneis de câmeras (6 faces) + scanners fixos na doca; plataforma no-code |
| **Cognex Pallet Scanning** | Leitura de etiquetas de paletes em movimento na doca | Smart camera (edge) com espelho de alta velocidade; lê até 7 km/h; read rate até 99,95% (fabricante) |
| **Voxel** | Segurança na doca (não contagem) | Usa CFTV existente, IA em nuvem, go-live em 48h |
| **Gather AI** | Inventário por drone (referência de contagem por visão) | Drones fotografam posições, IA conta e compara com WMS |

**Padrão de arquitetura consolidado do mercado (validação do nosso desenho):**
- **"Sessão de doca" é o modelo dominante** — abre na chegada do caminhão (detecção de presença), tudo é associado à sessão, fecha na saída. Idêntico ao nosso conceito de `loading_sessions`. ✅
- **Dois paradigmas:** *label scanning* (conta o que lê — exige etiqueta) vs. *object counting* (conta o objeto em si). Para rolos de tecido sem etiqueta legível, **object counting com linha de cruzamento é o caminho certo** — e é menos atacado pelos líderes (oportunidade de nicho).
- Edge processing + integração WMS via API é padrão; prova visual (clipe/foto por evento) é diferencial de venda recorrente em todos os players.

*Fontes: [Vimaan DockTRACK](https://vimaan.ai/inventory-tracking-products/docktrack/), [Zebra SmartPack TM2000](https://www.zebra.com/us/en/products/spec-sheets/smartpack/tm2000.html), [Peak/Siena](https://www.peaktech.com/peak-analytics/), [Cognex Pallet Scanning](https://www.cognex.com/en/products/logistics-solutions/pallet-scanning-system), [Voxel](https://www.voxelai.com/industry-insights/loading-dock-safety-software-3pl), [Gather AI](https://www.gather.ai/), [Kibsi dock optimization](https://www.kibsi.com/solutions/loading-dock-optimization-computer-vision/)*

## 2. Métricas de mercado — o que é verificado vs. marketing

### ⚠️ Correção importante ao CARGA_DESCARGA.md
Os números "−25-35% erro de carregamento, −30-50% furto, +20% dock-to-stock, ROI 200-350% em 12-18 meses" **têm origem rastreada em marketing da Agrex.ai, sem fonte primária independente**. Não usar como fato em proposta — apresentar como "resultados relatados por fornecedores do setor".

### Verificado (fontes credíveis)
| Métrica | Valor | Fonte |
|---|---|---|
| Erro de picking/expedição manual | 1-3% dos pedidos | Consenso setorial (Cisco-Eagle, Canadian Alliance) |
| Acurácia best-in-class de picking | ≥99,68% | **WERC DC Measures 2025** |
| Dock-to-stock best-in-class | ≤3,5 h (típico 2-8h; PMEs 24-72h) | **WERC 2025** |
| Truck turnaround | 30-60 min live load; <2h razoável; ~40% estoura 2h | Loadsmart/Arrivy |
| Custo por erro de expedição | US$ 30-75 direto; US$ 50-300 com indiretos | Estimativa setorial (faixa ampla) |
| **Gartner:** até 2027, 50% das empresas com armazém usarão visão com IA | Press release oficial Gartner (jun/2024); 20% já em dez/2023 | **Verificado** |

**Recomendação comercial:** ancorar o business case da Rocabella em: erro manual de 1-3% × volume dela × custo por erro + a previsão Gartner. Os claims de vendors entram como "setor relata", nunca como promessa nossa.

*Fontes: [WERC 2025](https://werc.org/news/702949/WERC-Releases-2025-DC-Measures-Report-with-a-Focus-on-Combining-Vision-with-Vigilance-.htm), [Gartner](https://www.gartner.com/en/newsroom/press-releases/2024-06-12-gartner-predicts-half-of-companies-with-warehouse-operations-will-leverage-ai-enabled-vision-systems-by-2027), [Cisco-Eagle](https://www.cisco-eagle.com/blog/2014/11/05/order-picking-error-rates-whats-acceptable/), [Loadsmart KPIs](https://blog.loadsmart.com/dock-scheduling-kpis), [Agrex.ai — origem dos claims](https://www.agrexai.com/logistics-video-analytics/)*

## 3. Boas práticas de desenvolvimento (mapeadas ao nosso stack)

### Contagem por linha de cruzamento
- **Tracker:** ByteTrack supera DeepSORT em ID-switches (1193 vs 1751 em benchmark; ~98% acurácia de contagem com oclusão breve). NvDCF (nativo DeepStream, GPU) é o prático no Jetson, mas tem **casos conhecidos de reatribuição de ID gerando contagem falsa** — ajustar `max_age`, `min_hits` e re-associação. **Avaliar ByteTrack vs NvDCF no nosso pipeline cedo.**
- **Anti-dupla contagem:** lista de IDs já contados; track elegível só após N frames (nosso voto multi-amostra 038 ✅); **histerese com duas linhas ou linha+zona** em vez de linha única.
- **nvdsanalytics usa o ponto inferior central da bbox** ("pé" do objeto) — posicionar a linha onde esse ponto cruza estável, perpendicular ao fluxo, longe de onde objetos aparecem/somem no frame.

### Dataset do modelo de rolo (nosso risco nº 1)
- Meta de produção: **≥1.500 imagens / ≥10.000 instâncias** da classe (Ultralytics); começar com 100-500 via transfer learning e iterar.
- Capturar nas condições reais (turnos, iluminação, câmeras definitivas); incluir 5-10% de frames de fundo (sem rolos) contra falsos positivos.
- Rolos empilhados/ocluídos: **definir regra de anotação única** (anotar extensão completa ou só visível) e manter consistência; QA de anotação com IoU entre anotadores.
- **Active learning desde o piloto:** coletar automaticamente frames de baixa confiança da doca real → re-anotar → re-treinar.

### Validação de acurácia (proteger o contrato)
- Validar **eventos**, não só totais — MAE baixo pode mascarar FPs e FNs que se cancelam.
- Protocolo: ground truth por contagem manual de vídeo gravado (dupla checagem); mercado opera em 88-98% vs manual.
- **Definir critério de aceite contratual antes do piloto** (sugestão: erro ≤2-5% por turno + uptime) com go/no-go documentado — isso protege a "ativação assistida" dos dias 21-25.

### MLOps edge
- Versionar modelo+dados+config juntos; deploy em container com rollback automático no Jetson.
- **Shadow mode:** modelo novo roda em paralelo sem afetar a contagem oficial; compara antes de promover.
- Monitorar drift: distribuição de confiança e estatísticas de contagem ao longo do tempo.

### DeepStream produção
- `rtsp-reconnect-interval-sec=30-60`, `latency=1000`, `live-source=1`; watchdog em thread separada; add/remove dinâmico de streams; `batch-size = nº de fontes`; `nvpmodel -m 0 + jetson_clocks`.

*Fontes: [nvdsanalytics docs](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvdsanalytics.html), [NvDCF ID reassignment](https://forums.developer.nvidia.com/t/nvdcf-tracker-id-reassignment-causes-false-line-crossing-counts-in-deepstream-7/363239), [trackers benchmark](https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/), [Ultralytics training tips](https://docs.ultralytics.com/yolov5/tutorials/tips_for_best_training_results), [Roboflow active learning](https://blog.roboflow.com/what-is-active-learning/), [Counting Stacked Objects (ICCV 2025)](https://openaccess.thecvf.com/content/ICCV2025/papers/Dumery_Counting_Stacked_Objects_ICCV_2025_paper.pdf), [validação de contagem](https://arxiv.org/pdf/1909.08522), [DeepStream runtime streams](https://developer.nvidia.com/blog/managing-video-streams-in-runtime-with-the-deepstream-sdk/)*

## 4. Profissionais da operação → Personas de agentes de IA

Papéis que fazem uma expedição funcionar, com a visão de cada um. Usar como **personas em prompts de agentes** durante o desenvolvimento (revisão de features, dashboards, fluxos).

### Persona-prompts prontos para uso

**🧑‍💼 Gerente de Logística (dono do resultado)**
```
Você é gerente de logística de uma indústria têxtil com 6 docas de expedição. Você responde por OTIF,
custo por embarque e multas de estadia. Você NÃO acompanha a doca em tempo real — descobre problemas
quando já viraram custo, e isso te irrita. Ao avaliar qualquer tela/feature, pergunte: "isso me mostra
o desvio ANTES de virar custo? me dá tendência ou só foto? consigo cobrar causa-raiz com isso?"
Rejeite dashboards que exigem mais de 30 segundos para entender o estado da operação.
```

**👷 Supervisor/Líder de Expedição (dono do turno)**
```
Você é o líder de expedição. Decide qual caminhão entra em qual doca, realoca equipe nos picos e libera
o veículo no fim. Suas dores: caminhão sem agendamento, pedido não separado quando o veículo encosta,
pátio congestionado. Ao avaliar features, pergunte: "isso me ajuda AGORA, no meio do turno? mostra o
status de cada doca/carga num relance? me avisa de anomalia (doca parada, sessão muito longa) sem eu
precisar olhar?" Você usa o sistema em pé, no celular ou num telão — interfaces densas não funcionam.
```

**🔍 Conferente de Carga (dono da precisão)**
```
Você é conferente de expedição. Sua função é garantir que o físico bate com o documento — cada rolo a
mais ou a menos é seu nome na divergência. Hoje você conta na pressão, com papel. O sistema de visão
não pode te tratar como obsoleto: ele é sua ferramenta de prova. Pergunte: "a contagem da câmera me
mostra O VÍDEO do momento em caso de dúvida? consigo registrar divergência com 2 toques? o sistema me
protege quando o motorista contesta?" Desconfie de números sem evidência visual.
```

**🚜 Operador de Empilhadeira/Carregador (dono do fluxo físico)**
```
Você carrega caminhões com rolos de tecido, avulsos e paletizados. Não quer parar para apertar botão:
qualquer passo extra no seu fluxo é atrito. Pergunte: "o sistema conta sozinho enquanto eu trabalho?
a câmera me atrapalha? se eu passar rápido ou com 2 paletes, conta certo?" Você é o teste de estresse
da contagem: empilhadeira em velocidade, oclusão, vai-e-volta de rolos devolvidos.
```

**📊 Analista de Logística (dono dos dados)**
```
Você é analista de logística. Monta janelas de doca, analisa desvios e monta relatórios pra gerência.
Sua dor: dados dispersos e sem histórico confiável de tempos de doca. Pergunte: "consigo exportar?
o dado tem grão de sessão (baia+caminhão+horário)? consigo cruzar com transportadora/turno? a API
existe pra quando integrarmos o BI?" Você é quem vai defender a Fase 2 (integração ERP/BI) internamente.
```

**🚛 Motorista (stakeholder externo)**
```
Você é motorista. Quer atracar, carregar e sair — a Lei 13.103/2015 limita carga/descarga a 5h e
estadia gera custo. Pergunte: "o sistema acelera minha liberação? a contagem com vídeo encerra
discussão sobre o que subiu no caminhão (te protege também)? o documento sai junto com o fim do
carregamento?"
```

**🧾 Faturamento/Fiscal (trava legal)**
```
Você emite NF-e/DANFE e não pode faturar errado: NF deve igualar a carga física ANTES da circulação.
Sua dor: faturar antes da conferência e ter que cancelar/corrigir. Pergunte: "o sistema me dá o gatilho
'sessão fechada com contagem X' pra liberar faturamento? divergência bloqueia ou só avisa? o registro
em vídeo serve como evidência em fiscalização/disputa?"
```

### Como usar no desenvolvimento
1. **Review de feature:** rodar a spec por 2-3 personas relevantes ("o que o conferente diria desta tela?")
2. **Priorização:** dor citada por mais personas sobe no backlog
3. **Testes de aceitação:** cada persona vira um roteiro de teste (ex.: cenário do operador = empilhadeira rápida com 2 paletes)
4. **Dashboard:** gerente vê tendência, supervisor vê agora, analista exporta — três visões, não uma

*Fontes: [Conferente — Indeed BR](https://br.indeed.com/conselho-de-carreira/encontrando-emprego/conferente-faz-o-que), [Vagas.com — conferente de expedição](https://www.vagas.com.br/cargo/conferente-de-expedicao), [Supervisor de operações logísticas](https://querobolsa.com.br/carreiras-e-profissoes/supervisor-de-operacoes-logisticas), [Analista de logística — Catho](https://www.catho.com.br/profissoes/analista-de-logistica/), [KPIs logísticos — TOTVS](https://www.totvs.com/blog/gestao-logistica/indicadores-de-desempenho-logistico/), [Docas congestionadas](https://logpyx.com/docas-de-carregamento-congestionadas-causas-e-consequencias/), [Expedição — OpenTech](https://opentechgr.com.br/blog/expedicao-logistica/)*

## 5. Decisões recomendadas para o nosso desenvolvimento

1. **Manter object counting por linha** (nicho certo p/ rolo sem etiqueta) com **histerese linha+zona** e voto multi-amostra
2. **Bench ByteTrack vs NvDCF** na primeira semana de pipeline — ID-switch é o maior risco técnico da contagem
3. **Coleta de dataset começa no dia 1 da instalação** (active learning desde o piloto) — é o caminho crítico dos 25 dias
4. **Critério de aceite contratual definido antes do piloto** (erro ≤2-5%/turno) — protege a ativação assistida
5. **Corrigir materiais de venda**: substituir claims da Agrex por dados WERC/Gartner verificados
6. **Evidência visual por sessão** é o diferencial unânime do mercado — capricho no clipe+timestamp+placa
7. **Personas nos prompts**: usar os 7 blocos da seção 4 em todo review de feature e spec
