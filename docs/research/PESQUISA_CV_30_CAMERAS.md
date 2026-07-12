# Sistemas de visão computacional com 30+ câmeras — o que a comunidade técnica relata

> **Pesquisa em fóruns de praticantes** · 2026-06-05 · contexto: Recognition / RVB (28–30 câmeras, EPI + Qualidade + Contagem, edge/cloud).
> **Fontes:** Frigate GitHub Discussions, fóruns NVIDIA DeepStream, IPVM, IP Cam Talk, Hacker News, retrospectivas de engenharia nomeadas.
> **Nota:** o acesso direto ao Reddit estava bloqueado nas ferramentas desta pesquisa. Pivotei para os fóruns onde a discussão técnica de 30+ câmeras realmente mora — e, como observou um dos agentes, as threads de Reddit (r/frigate_nvr, r/computervision) em geral **redirecionam para essas mesmas fontes**. Cada item está marcado como **[consenso]** (≥2 fontes independentes) ou **[relato único]** (um relato detalhado em primeira mão).

---

## TL;DR — a lição que aparece em TODOS os ângulos

**O gargalo de 30+ câmeras é o DECODE de vídeo (NVDEC), não a inferência.** Quase todo mundo que escala erra o diagnóstico no começo: investe em GPU/modelo quando o limite real é o número de streams que o decodificador de hardware aguenta. As três consequências práticas, repetidas por praticantes independentes:

1. **Detecte na sub-stream de baixa resolução (~720p, ~5 FPS); use a main stream 4K só para gravar.** Como o modelo redimensiona a entrada para um tamanho fixo (ex: 320×320), a resolução da câmera **não muda** a velocidade de inferência — mas muda enormemente o custo de decode/motion.
2. **H.265/HEVC ~dobra** quantos streams um decoder aguenta vs H.264.
3. **GPU de consumidor satura ~20 streams concorrentes de decode**, independente de "sobrar" GPU para inferência.

---

## 1. Arquitetura & quantas câmeras por GPU

A pergunta "quantas câmeras por GPU?" tem como resposta real "quantos streams o NVDEC decodifica", não "quanta GPU sobra".

| Hardware | Streams (decode + detecção) | Fonte |
|---|---|---|
| GPU consumidor (genérico) | **~20 streams concorrentes** (limite de decode) | Frigate docs [consenso] |
| RTX 4090 | **~16–17** H.264 1080p30 (1 núcleo NVDEC satura; detecção nem é o limite) | NVIDIA staff [relato confirmado] |
| RTX 3050 6GB | ~35–40 câmeras H.265 (~109 MB VRAM/câmera) | Frigate disc. #21559 [relato + maintainer] |
| GPU 16GB (ex: 4060Ti/4070) | **~25–30 câmeras** 1080p–2K (decode + detecção juntos) | Frigate disc. #22636 [consenso] |
| RTX 3090 24GB | ~36 câmeras a 1280×720 detecção | Frigate disc. #7491 [relato] |
| Jetson Orin NX 16GB | ~40 câmeras @5 FPS (1 modelo YOLOv8s INT8 compartilhado) **ou** ~11 @15 FPS (modelo por stream) | benchmarks Jetson [consenso] |
| Jetson Orin Nano 8GB | ~4–6 streams | benchmarks Jetson [consenso] |
| **A100 80GB (datacenter)** | **~100 H.264 / ~178 HEVC** 1080p30 | teste DeepStream 9.0 80 câmeras [consenso] |

**Padrões de arquitetura:**

- **Separe os dois gargalos:** iGPU Intel Quick Sync (ou Arc) para **decode**, GPU NVIDIA dedicada para **inferência**. Recomendação recorrente da comunidade Frigate. [consenso]
- **Servidor central puxando todo o RTSP** é mais simples, mas trava em decode + banda de ingresso; **nós de edge distribuídos** processam local e mandam só alertas/metadados pra cima — corta banda e latência. O thread do RTX 4090 mostra até GPU parruda travando na ingestão de RTSP passando de ~36 streams. [consenso]
- **DeepStream `nvstreammux`** junta frames de várias câmeras em **um único batch** de inferência TensorRT (memória GPU zero-copy) — é isso que viabiliza contagens altas de stream em uma GPU. Para 80 streams numa A100, a receita testada foi `batch-size=32, interval=2` (não batch = número de câmeras). [consenso]
- **Frame-skip/interval inference** é o multiplicador-padrão de FPS: inferir em frame sim/frame não e deixar o **tracker** preencher os gaps mantém caixas em todo frame sem inferir em todo frame. [consenso]
- **Modo NVR puro (sem IA)** sobe o teto de câmeras: se a câmera faz IA on-board (ONVIF metadata), a caixa só precisa de folga de decode. [relato + maintainer]

---

## 2. Hardware & custo

**Aceleradores de edge (medido por fornecedor):**

- **Google Coral** (USB/M.2, ~US$25–60, ~2 W): SSD-MobileNet ~10 ms → ~100 inferências/s, "suficiente para a maioria". Frigate hoje recomenda Coral só para baixo consumo, apontando novos installs para **Hailo-8 / NPU Intel / GPU**. [consenso]
- **Jetson Orin**: NX 16GB = US$599 (100 TOPS); NX 8GB = US$399; Orin Nano Super = US$249; AGX Orin kit = US$1.999 (275 TOPS). YOLOv8n-INT8 no Orin NX ≈ 66 FPS a 10–14 W. [consenso]
- **iGPU Intel** como caminho sem GPU dedicada: Iris Xe roda YOLOv9-tiny-320 ~6 ms → um mini-PC N100/Core-Ultra (~US$300–400) atende várias câmeras 1080p sem placa discreta. [consenso]

**Limites escondidos de GPU consumidor (decisivos para muitos streams):**

- NVENC (encode) historicamente limitado a 3 sessões, hoje até 8; placas pro/datacenter = ilimitado. AD102 tem 3 NVDEC mas a **RTX 4090 habilita só 2**. Decode throughput — não detecção — costuma ser o teto. Existe o `keylase/nvidia-patch` que remove o limite de sessão no consumidor. [consenso]
- **NVDEC nem sempre ganha:** há relatos de decode H.264 via NVDEC **mais lento** que multicore CPU (tempo preso em `avcodec_send_packet()`). [relato único]

**Armazenamento (30+ câmeras):** fórmula `GB = câmeras × bitrate(Mbps) × dias × 10.8`. 1080p/30 ≈ 60–100 GB/dia/câmera; 4K H.265 ≈ 8 GB/dia. Gravação só-movimento economiza 60–70%; gravação filtrada por IA (pessoa/veículo) economiza **80–90%**. Ex: 30 câmeras × 4 Mbps × 30 dias contínuo ≈ **35 TB** → cai pra TB de um dígito com smart recording. [consenso]

**Rede/PoE (30 câmeras):** câmera básica 4–7 W, PTZ 12–25 W. 30 básicas ≈ 180 W → orçar ~234 W PoE (+30% folga); build prático = dois switches de 16 portas PoE+/PoE++ **gerenciados** (buffer real + uplink gigabit). [consenso]

**Custo recorrente — o contraste capex vs opex:**

- **VMS gerenciado em nuvem (Verkada):** ~US$15–25 por câmera/mês (licença + storage + analytics). Para 30 câmeras ≈ **US$5.400–9.000/ano recorrente** — vs ~US$300–600 de GPU de edge (3060/Orin NX) + mini-PC, uma vez. [consenso]
- **Inferência GPU em nuvem contínua** é ainda mais difícil de justificar: H100 ≈ US$1.460/mês 24/7; só compensa muito batcheado / abaixo de ~30% de duty cycle. Serverless por inferência casa melhor com detecção disparada por movimento. [consenso]
- Uma análise (vendor-framed, **[relato único]**) cita inferência cloud-only por frame perto de **~US$550/câmera/mês** e estima o híbrido ~15× mais barato no ano 3, com payback do edge em <12 meses acima de ~20 câmeras. Tratar o número como estimativa de fornecedor, mas a direção bate com o consenso de que **quase ninguém roda 30+ câmeras como inferência pura-cloud por frame**.

---

## 3. Stacks de software — onde brilham e onde quebram

**Frigate** (NVR open-source + detecção):
- Escala a 100+ câmeras numa caixa **se** você respeitar decode/VRAM da GPU; mas **CPU-only morre cedo** — um Xeon E-2336 sem GPU saturou com **10 câmeras**. [consenso]
- Reclamação principal: setup é Docker + YAML, sem wizard gráfico. Blue Iris é "muito mais fácil de configurar". [consenso]

**Blue Iris** (NVR Windows, IA via CodeProject.AI):
- **Teto rígido de 64 câmeras**; CPU é o limite documentado. Com sub-streams, "quase qualquer quad-core pós-2012" chega no teto. Parede real: câmeras **sem** sub-stream forçam upgrade de hardware. [consenso]
- A IA (CodeProject.AI) é o gargalo de latência: 400–1200 ms por chamada CPU-bound; empilhar modelos passa o trigger de 20s. GPU NVIDIA estabiliza e acelera (footprint ~300–350 MB VRAM). [consenso]

**NVIDIA DeepStream** (o "porquê os pros usam em escala"):
- Único que **batcheia 80 streams em uma GPU** com eficiência. Teste empírico (A100, 80× 1440p): decoder é o gargalo (não inferência); **batch-32 rodou 168h sem crash vs batch-80 crashou 2× em 72h** (CUDA OOM); sub-stream 1080p baixou decoder de 100%→56%. [relato único, muito detalhado]
- Os próprios mantenedores do Ultralytics **redirecionam** quem tem muitos streams para DeepStream. [consenso]
- Trade-off universal: escala máxima, mas **curva de aprendizado brutal** (plugins GStreamer, C++ async, suporte só por fórum). É por isso que existem wrappers (Savant, Pipeless). [consenso]

**Ultralytics YOLO** (pipeline Python custom): caminho mais rápido para 1 stream ou poucas câmeras; **não paraleliza bem muitos streams numa GPU** (multithreading é concorrência, não paralelismo real). Em escala, a recomendação é passar a bola pro DeepStream. [consenso]

**Comerciais:** **Viso Suite** (no-code gerenciado) — time-to-market rápido, mas custo alto e lock-in. **Milestone XProtect** — líder enterprise multi-site, mas workflows centralizados pesados e governança de config íngreme (oposto do Frigate home-lab). [vendor-adjacent]

---

## 4. Dores em escala

**Confiabilidade de RTSP:**
- **"No frames received in 20 seconds, exiting ffmpeg"** é o modo de falha #1 do Frigate — câmeras congelam aleatoriamente, refresh do browser traz de volta (aponta pra camada de decode/conexão, não a câmera). [consenso]
- **Câmeras travam a conta após poucos logins falhos:** Hikvision bloqueia após **~6 tentativas**; Tapo bloqueia 30 min após 10. Causa raiz documentada: a **mesma câmera puxada por várias sessões** (VMS + app + browser com credencial velha). **Em 30+ câmeras, uma senha errada propagada = lockout da frota inteira.** [consenso]
- **TCP vs UDP importa:** retransmissões TCP congestionam e "tudo piora rápido"; bursts de I-frame (IDR) estouram a banda instantânea e rasgam o stream se cai pacote. [relato expert]

**Decode (de novo) é o limite real, não a IA:** no Blue Iris, re-encode deve ser evitado "a todo custo"; Quick Sync "não é mais recomendado" por instabilidade (às vezes *aumenta* a CPU) → caem pra decode CPU + sub-streams. Quando a inferência do Coral sobe (24 ms vs ~10 ms alvo), ela **entope a fila compartilhada** e *causa* os restarts de ffmpeg — latência de inferência e quedas de stream são acopladas. [consenso]

**Banda (30+ câmeras):** switches entregam ~50% do nominal sob muitos streams CBR simultâneos — a "regra dos 70%" superpromete. ~4 Mbps por stream 1080p/30 → 30 câmeras ≈ 120+ Mbps **antes** de sub-streams/gravação. Switches **gerenciados com buffer real** + uplink gigabit são tratados como obrigatórios; o limite costuma ser exaustão de buffer, não banda bruta. [consenso]

**Acurácia em escala:**
- **Noite + IR é a maior fonte de falso-positivo: insetos e aranhas.** O IR atrai mariposas que estouram brilho e disparam detecção; depois vêm aranhas que tecem na lente. Correção é física (IR separado da câmera) + máscaras de movimento por câmera + dia/noite separados — **tunagem por câmera, que não escala bem pra 30+**. [consenso]
- Tunagem por câmera é inevitável e cara; tunagem adaptativa por câmera mostrou **+42% de verdadeiros-positivos** vs modelo genérico. [consenso acadêmico+comunidade]

**Ops:** **falha silenciosa** (câmera para de detectar sem alerta → precisa de monitor de uptime separado); **config drift** na frota (agendas de reboot colidindo, firmware divergindo → auditar periodicamente); **upgrades regridem** performance (quedas de stream fixadas a uma versão específica). [relatos]

---

## 5. Lições / o que fariam diferente

- **Profile o DECODER no dia 1, não no dia 4.** "Se eu tivesse checado a utilização do decoder no dia um em vez do dia quatro, teria economizado uma semana." [relato profundo]
- **Sub-stream pra detecção desde o início; main stream só pra gravar.** Fix de maior impacto isolado. [consenso]
- **Estabilidade > throughput.** Batch menor que crasha nunca > batch grande que crasha às 3h. Use `drop-on-latency=1` pra descartar frame sob sobrecarga em vez de empilhar backlog. [relato profundo]
- **Migre para H.265** (~dobra streams por decoder); passando disso, espalhe câmeras por várias GPUs (~40/GPU). [consenso]
- **Build vs buy:** quem considera visão "IP central" sempre escolhe **build** — não adianta vender "perception as a service" pra esses times. O nicho comprável é o não-especialista. [relato forte]
- **"Ninguém compra detecção crua — compra solução fim-a-fim."** Em PPE, a parte que fecha negócio é **captura automática de evidência (timestamp + local + foto) + alerta instantâneo**, não a bounding box. [consenso]
- **Realidade de PPE:** demos de fornecedor são footage limpo; chão real tem sombra, blur, oclusão e câmeras de segurança nunca pensadas pra IA. Modelos prontos **não conhecem** EPI real (toucas, protetor facial, luva food-safe) → **fine-tune no equipamento da sua planta**. Acurácia real ~93% (colete/capacete) vs ~99% de paper. **Retreino é cadência, não evento único** (troca de fornecedor de EPI = re-anotar). [consenso]
- **Contagem de pessoas / cruzamento de linha degrada com oclusão:** pipeline DeepSORT afinado deu **92% de detecção mas só 85% de contagem** em cena densa; pedestres são 4–5× menores que veículos → ID-switch do tracker na oclusão é o erro principal. **Contagem robusta precisa de voto majoritário de múltiplas amostras** na linha, não teste de cruzamento em 1 frame. [consenso]
- **Rollout faseado:** piloto de **1–3 câmeras/site com critério de sucesso explícito** antes de escalar; "escala quebra workarounds manuais" (um técnico checa 50 trabalhadores, não 1.600 em turnos). [consenso]
- **"O modelo é a parte fácil."** ~90% do trabalho é manuseio do produto + setup de cena (lente, exposição, iluminação); qualidade dos dados >> quantidade ou arquitetura. Integradores industriais exigem que **funcione 100% do tempo — 99,5% não basta** — e desconfiam de startup que "pode sumir em 2 anos". [consenso]

---

## 6. O que isso significa para o Recognition (RVB)

Vários achados **validam decisões que você já tomou** — e alguns apontam risco:

- ✅ **Câmeras nunca na internet + VPN MikroTik (ADR-0020).** O lockout de Hikvision/Tapo após ~6 logins falhos, agravado por múltiplas sessões puxando a mesma câmera, é exatamente o cenário que sua arquitetura evita. Decisão correta e corroborada por relato de campo.
- ✅ **Edge/DeepStream como default ≥6 câmeras (seu modelo de custo).** A economia híbrida e o fato de "ninguém roda 30+ câmeras como inferência pura-cloud por frame" batem com sua conclusão. RVB com 28 câmeras é claramente território de edge.
- ✅ **`counting_line` "best-effort, contagem real é edge/DeepSORT" (que sinalizei no PR #37).** O dado 92% detecção → 85% contagem e a recomendação de **voto majoritário de múltiplas amostras** confirmam que contagem por cruzamento de 1 frame no cloud é só aproximação — a contagem boa precisa do DeepSORT no edge. Vale embutir o voto-majoritário na config do `counting_line`.
- ✅ **Modelo custom por (tenant×módulo), Qualidade fine-tuned.** "Modelos prontos não conhecem EPI real → fine-tune na planta" e "retreino é cadência" validam sua trilha de modelos + o `model-rollout` (PR #36) com canário/version-pin.
- ✅ **RVB como cliente-âncora (piloto faseado).** Exatamente o "1–3 câmeras/site com critério de sucesso antes de escalar".
- ⚠️ **Sub-stream para detecção é mandatório — confirme que o DeepStream da Fase 5 detecta na sub-stream, não na main.** É o fix de maior impacto e o erro mais comum.
- ⚠️ **Dimensione a GPU do Mini PC pelo DECODE, não pela inferência.** Para 28 câmeras 1080p decode+detecção numa caixa, mire GPU de **16GB+** (ou separe decode no iGPU Intel + inferência na NVIDIA) e use **H.265** nas câmeras. Uma placa de consumidor satura ~20 streams de decode — 28 câmeras já passa disso sem sub-stream/H.265.
- ⚠️ **"Ninguém compra detecção crua."** Seu diferencial de venda é o fim-a-fim que você já tem (alert_rules, frames com evidência, dashboard) — não o detector. Priorize a captura de evidência + alerta instantâneo no go-live.
- ⚠️ **Falha silenciosa + monitor de uptime.** O painel "Sites & Saúde" (O1, já feito) + a regra de "site offline" cobrem isso — mas garanta alerta proativo quando uma *câmera* específica para, não só o site.

---

## Fontes (primárias, fetchadas)

- Frigate — planning/sizing: https://docs.frigate.video/frigate/planning_setup/ · hardware/inference times: https://docs.frigate.video/frigate/hardware · object detectors: https://docs.frigate.video/configuration/object_detectors/
- Frigate GitHub Discussions: #17033 (decode vs detecção, multi-GPU), #7491 (builds 30–36 câmeras), #21559 / #22636 (sizing real), #13172 / #12769 (no frames in 20s), #10524 (restream CPU), #3925 / #17882 (falsos-positivos IR/insetos)
- NVIDIA DeepStream forum: https://forums.developer.nvidia.com/t/the-number-of-cameras-that-deepstream-can-support/275939 · skipping frames: https://forums.developer.nvidia.com/t/deepstream-skipping-frames-for-inference/201533
- Teste 80 câmeras DeepStream 9.0 (decoder/batch): https://dredyson.com/i-tested-every-solution-for-multi-stream-deepstream-9-0-app-heres-what-actually-works...
- Ultralytics → DeepStream (muitos streams): https://github.com/ultralytics/ultralytics/issues/5810
- IP Cam Talk: hardware Blue Iris https://ipcamtalk.com/wiki/choosing-hardware-for-blue-iris/ · otimizar CPU https://ipcamtalk.com/wiki/optimizing-blue-iris-s-cpu-usage/ · "9-year journey for accurate alerts" https://ipcamtalk.com/threads/my-9-year-journey-for-accurate-cctv-alerts.82566/
- IPVM: switch/banda https://ipvm.com/discussions/how-many-ip-cameras-on-a-100mb-s-connection · lockout Hikvision https://ipvm.com/discussions/hikvision-will-be-locked-after-6-failed-login-attempts
- PPE em campo (Agmis): https://agmis.com/what-we-learned-deploying-ai-ppe-detection-in-real-facilities/
- Contagem/tracking real-world (Veroke): https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/
- Build-vs-buy / "ninguém compra analytics cru" (DirectAI): https://www.brooks.team/posts/on-directai/ · integradores industriais (HN): https://news.ycombinator.com/item?id=35083163
- Jetson/DeepStream benchmark: https://medium.com/@MaroJEON/yolov8-jetson-deepstream-benchmark-test-orin-nano-4gb-8gb-nx-tx2-f3993f9c8d2f
- Custo cloud GPU: https://www.gmicloud.ai/en/blog/gpu-cloud-cost-ai-inference-at-scale · NVENC/NVDEC caps (Tom's Hardware): https://www.tomshardware.com/news/nvidia-increases-concurrent-nvenc-sessions-on-consumer-gpus
