# Pesquisa profunda — Jetson AI Lab: o que aproveitar, o que evitar, para onde a plataforma vai

**Data:** 2026-07-19 · **Fonte:** jetson-ai-lab.com (2.0), jetson-containers, fóruns NVIDIA, model cards HF
**Método:** 4 agentes em paralelo, leitura de código-fonte e licenças. Onde a fonte não afirma, está marcado como
não verificado ou como análise.

> **Regra deste documento:** ele alimenta `REGRAS_PLATAFORMA_JETSON.md` (doc vivo). As landmines da §2 devem ser
> copiadas para lá **hoje** — são as que queimam tempo se descobertas em campo.

---

## 1. O ACHADO QUE MUDA O ROADMAP 🔴

### DeepStream não roda no JetPack 7.2 em Orin. E o DS 8.0 não suporta Orin, ponto.

Nenhuma página do Jetson AI Lab menciona DeepStream — o quadro veio dos fóruns NVIDIA:

| Fato | Fonte | Data |
|---|---|---|
| **DS 8.0 não suporta a série Orin desde o lançamento** (é Thor-only; container traz TRT sem kernels SM 87 → `Target GPU SM 87 is not supported`) | Fiona.Chen, moderadora NVIDIA | 17/06/2026 |
| **DS 7.1 (o nosso) não roda no JP7.2** — quebra de ABI GLib/GStreamer (`undefined symbol: g_once_init_enter_pointer`, `nvstreammux` não registra) | fórum NVIDIA | 2026 |
| **DS 9.0 também não** está validado com JP7.2 | junshengy, NVIDIA | 08/06/2026 |
| **O SDK Manager não oferece DeepStream ao flashar JP7.2** | fórum | 03/06/2026 |
| **A versão que vai suportar é a DeepStream 9.1** — *"It will be DeepStream 9.1"* | yingliu, NVIDIA | 02/07/2026 |

**Consequência direta:** a nossa stack de hoje — **JP6.2 / L4T r36.4.3 / CUDA 12.6 / TRT 10.3 / DS 7.1** — é a
**última combinação Orin + DeepStream plenamente suportada**. Não subir produção para JP7.2 até o DS 9.1 sair e
ser validado em SM87.

**AÇÃO #1 (imediata):** verificar se o DS 9.1 já foi lançado (o dado mais recente encontrado é de 02/07/2026).

**Quando sair, o port JP6.2 → JP7.2 é P0-CRÍTICO de várias semanas**, não um `apt upgrade`:
Ubuntu 22.04→24.04 · kernel 5.15→6.8 · CUDA 12.6→13.2 · TRT 10.3→10.13+ · Python 3.10→3.12 ·
**todos os engines TensorRT reconstruídos** (engine é específico de SM + versão de TRT).

**Lado bom:** um usuário reportou DS 9.0 rodando **nativamente** (não containerizado) em JP7.2 + Orin com boa
performance — quebrou só ao containerizar. E usou parsers de
[quangdungluong/DeepStream-YOLOv11](https://github.com/quangdungluong/DeepStream-YOLOv11), que suporta
**YOLOv11, D-FINE e SCRFD**. Como estamos avaliando D-FINE, isso desrisca a integração — **verificar a licença
do repo antes** (gate ADR-0043).

---

## 2. LANDMINES — copiar para REGRAS_PLATAFORMA_JETSON.md hoje

### L1 — `jetson-containers` instala o DeepStream ERRADO no nosso box 🔴

`packages/cv/deepstream/config.py`:
```python
if L4T_VERSION >= Version('36.4.3'):   # ← nosso box é EXATAMENTE 36.4.3
    DEEPSTREAM_URL = '...deepstream_sdk_v8.0.0_jetson.tbz2'   # DS 8.0 = Thor-only
```
Todo box JP6.2 (36.4.3) e JP6.2.1 (36.4.4) cai nesse branch e recebe uma versão que **não roda em Orin**.
Nosso `REGRAS_PLATAFORMA_JETSON.md` está **certo** (DS 7.1 para JP6.2); o upstream é que está errado.

**Se usar o package, forçar:**
```bash
DEEPSTREAM_URL='https://api.ngc.nvidia.com/v2/resources/org/nvidia/deepstream/7.1/files?redirect=true&path=deepstream_sdk_v7.1.0_jetson.tbz2'
```
(URL inferida do padrão — **validar no box** com `wget -S --spider` antes de confiar.) Vale abrir issue upstream.

### L2 — Não existe imagem DeepStream pré-buildada para r36.4

`dustynv/deepstream` no DockerHub tem 5 tags, a mais nova **r36.2.0, de março/2024** — e `minor=2` é
**rejeitada** pelo gate de compatibilidade num host `minor=4`. Consequência: `autotag deepstream` cai no
"would you like to build it?", e o build arrasta `tritonserver`, `opencv`, `ffmpeg`, `vulkan` → **~10 GB**.
**Isso não é caminho de provisionamento em campo.**

### L3 — Gate de compatibilidade de JP6 tem fronteira dura em `minor == 4`

`l4t_version_compatible()`: em r36, imagens `minor < 4` só rodam em hosts `minor < 4`, e vice-versa. Ou seja
**JP6.2 (r36.4.x) NÃO aceita imagens r36.2/r36.3** (JP6.0/6.1). Diferente de JP5, onde qualquer r35.x servia.
Se atualizarmos o JetPack, **todas** as imagens precisam ser rebuildadas.

### L4 — `/ssd` precisa montar ANTES do docker.service

Se o NVMe montar depois do daemon, o Docker sobe com `data-root` vazio ou falha — **falha silenciosa de reboot**
num box 24/7 na casa do cliente. Blindar:
```bash
sudo systemctl edit docker.service
# [Unit]
# RequiresMountsFor=/ssd
```

### L5 — Migração do data-root: `rsync -axPS`, nunca `cp -r`

Layers do overlay2 usam hardlinks pesadamente; `cp -r` infla drasticamente. (O `setup.md` do repo usa `cp -r`;
o tutorial usa rsync — seguir o tutorial.)

### L6 — JP6: `apt install nvidia-container` NÃO instala mais o Docker

Mudança de JP5 para JP6. Precisa `curl https://get.docker.com | sh` + `nvidia-ctk runtime configure`.
E `"default-runtime": "nvidia"` no `daemon.json` **não é cosmético** — sem ele, `docker build` não tem NVCC.

### L7 — `install.sh` do jetson-containers polui o Python do sistema em 22.04

Em Ubuntu 22.04 faz `pip3 install -r requirements.txt` **system-wide** (só usa venv em 24.04). Rodar em venv manual.

### L8 — Rodar container como não-root: CUDA error 801

`/dev/nvhost-gpu`, `/dev/nvmap`, `/dev/dri/renderD128` são `root:video`/`root:render` modo 0660. Sem os grupos,
`cudaGetDeviceCount()` falha com 801. O `run.sh` resolve passando `--group-add <GID numérico>` — usar **GID
numérico**, porque o GID de `render` no host tipicamente não bate com o do container e `--group-add render`
falha silenciosamente.

---

## 3. RAM: o que ainda não fizemos (ganho fácil)

A página `ram-optimization` tem **três** técnicas. Fizemos uma e meia.

| Técnica | Ganho | Status |
|---|---|---|
| **Desabilitar GUI do desktop** | **~800 MB** | ❌ **não feito** |
| **Desabilitar `nvargus-daemon`** | não quantificado | ❌ **não feito** |
| Swap NVMe + desabilitar ZRAM | 16 GB | ✅ swap feito · ❓ `nvzramconfig` provavelmente ativo |

**(a) GUI — o maior ganho isolado.** `sudo systemctl set-default multi-user.target`
⚠️ **Interação com o nosso setup:** o `REGRAS §1` documenta `DISPLAY=:1` + `XAUTHORITY=.../gdm/Xauthority`
(monitor físico via GDM). Em `multi-user.target` o GDM não sobe e esse DISPLAY morre. Se algum config do
DeepStream ainda usar `nveglglessink`, falha sem X. Confirmar que estamos em RTSP-out antes de aplicar.

**(b) `sudo systemctl disable nvargus-daemon.service`** — nvargus é daemon de câmera **CSI/Argus**. Usamos
Hikvision/Intelbras via RTSP (ADR-0009), zero CSI. **Sem risco.**

**(c) `nvzramconfig`** — conferir com `swapon --show` / `zramctl` se ainda há `/dev/zram0..N`.
⚠️ **Decisão consciente, não por omissão:** ZRAM é swap comprimido em RAM — ordens de magnitude mais rápido que
NVMe e **sem desgaste de célula**. A recomendação da NVIDIA de desabilitar é orientada a *build de container* e
*modelos grandes*, não a inferência em regime permanente 24/7. Manter os dois com prioridades distintas (zram
`pri` alta, NVMe `pri` baixa) é defensável para reduzir escrita no NVMe.

---

## 4. OPORTUNIDADES — ranqueadas por valor real

### O1 — `jetson-device-skills` e `jetson-bsp-skills` (NVIDIA) ⭐ maior ganho de processo

Dois repositórios de *agent skills* que se encaixam **direto** no nosso workflow com Claude Code.

**`NVIDIA-AI-IOT/jetson-device-skills`** — roda **no** Jetson. Skills: `jetson-diagnostic` (snapshot read-only de
identidade/memória/GPU/térmica/power/storage), `jetson-memory-audit`, `jetson-headless-mode` (plano seguro para
desabilitar desktop — literalmente o item 3a), `jetson-package` (qual wheel/container escolher — **endereça
exatamente a landmine do torch SBSA vs jp6/cu126** que já nos queimou), `jetson-inference-mem-tune`,
`jetson-llm-serve`, `jetson-llm-benchmark`.

O racional declarado pela NVIDIA é o mesmo motivo pelo qual criamos o `REGRAS_PLATAFORMA_JETSON.md`:
*"Sem esse contexto, agentes de IA tendem a dar conselho genérico de Linux ou de GPU discreta, que não se aplica
ao Jetson."* → **`jetson-diagnostic` pode virar a coleta automatizada do §1 e do §4 daquele documento.**

**`NVIDIA-AI-IOT/jetson-bsp-skills`** — roda no workstation, customiza o BSP **antes do flash**: pinmux, USB,
PCIe, clocks, **fan**, **nvpmodel**, memory tuning. É a **resposta estrutural** para "provisionamento manual →
reproduzível": hoje aplicamos fan/clocks *pós-flash* via systemd; com BSP skills isso vira parte da imagem.
Um box novo sai da caixa já correto. **Insumo novo para o ADR-0040** (ainda Proposta).

### O2 — NanoOWL para pré-anotação zero-shot ⭐ encaixe direto num slot que já existe

**Detecção de vocabulário aberto** (OWL-ViT + TensorRT): troca a lista de classes em runtime passando **texto**.
Sem dataset, sem rótulo, sem treino, sem redeploy.

**Licenças — passa no gate:** NanoOWL **Apache-2.0** · pesos `google/owlvit-*` **apache-2.0** · torch2trt **MIT**.
Zero AGPL.

⚠️ **Armadilha de licença específica do nosso negócio:** o caminho **"tree prediction"** importa `openai/CLIP`,
cujo model card diz textualmente que *qualquer* uso em deployment está fora de escopo e que **vigilância e
reconhecimento facial são sempre out-of-scope**. Para um SaaS de CFTV isso é tiro no alvo.
**Mitigação:** o CLIP só é necessário no tree predictor. O caminho de detecção simples (`OwlPredictor`) **não
importa `clip` em momento algum**. Ficar no OWL-ViT puro resolve.

**Performance:** a única tabela publicada é **AGX Orin 95 FPS (ViT-B/32, mAP 28)** e **25 FPS (ViT-B/16, mAP 31,7)**.
**O Orin NX 16GB não tem número publicado** e a coluna do Orin Nano está "TBD". Resolução fixa 768×768.

**Onde encaixa (e onde NÃO encaixa):**
- ✅ **Pré-anotação offline** — sem restrição de latência, em lote sobre frames gravados, revisão humana no loop.
  **Já temos o slot: `SERVICE_TYPE=pre-annotation` (DINO+SAM, flag OFF).** NanoOWL é alternativa mais leve e com
  licença mais limpa. O README aponta **NanoSAM** para combinar e obter segmentação zero-shot.
- ✅ **Busca por texto sobre a evidência já gravada** no R2 ("ache clipes com pessoa caída no chão").
- ✅ **EPI para bootstrap** — "capacete", "colete", "luva" estão na distribuição COCO/OpenImages.
- ❌ **Qualidade (defeito milimétrico): encaixe estruturalmente ruim.** Modelos open-vocab são treinados em
  legendas de imagens naturais; "risco de 2mm na solda" não é conceito ancorável em texto. O próprio card do
  CLIP admite dificuldade com classificação fina. **Este módulo exige modelo treinado, ponto.**
- ❌ **Detector servido por frame nas 28 câmeras** — mAP 28–31,7 não substitui YOLOX/RF-DETR fine-tunado.

**Integração com DeepStream: não existe.** É Python/PyTorch puro, `cv2.VideoCapture` + websockets. Não cai no
`nvinfer` porque a engine produz `image_embeds`/`logit_shift`/`logit_scale`/`pred_boxes` — **não** produz
boxes+classes; o decode precisa dos text embeddings em runtime e roda em PyTorch.
**Achado bom:** `export_image_encoder_onnx` (opset 17, batch dinâmico) gera ONNX puro e o build já **shella para
`trtexec`**. Só o *carregamento* usa torch2trt — trivialmente substituível. Dá para **tirar o torch2trt do
caminho** e ficar em ONNX + TensorRT 10.3, que é a nossa stack.

### O3 — VLM como **adjudicador de evento**, nunca como detector ⭐ diferenciação de produto

Os dois agentes convergiram nisto de forma independente. É a leitura correta da tendência.

**Os números que enterram "VLM por frame":**

| Plataforma | Velocidade | Modelo |
|---|---|---|
| Jetson Orin Nano 8GB | **7–8 s/frame** | gemma3:4b |
| Jetson Thor 128GB | 1–2 s/frame | llama3.2-vision:11b |
| RTX 6000 Ada | <1 s/frame | gemma3:4b |

Isso é **0,125 a 1 fps em um único stream**. Rodamos 28 câmeras. VLM-por-frame está **duas a três ordens de
grandeza** de substituir detector — e isso no Thor, que não temos.

**Arquitetura correta (dois estágios):**
- **Estágio 1 (já existe):** DeepStream + YOLOX/RF-DETR + tracker gera *triggers* baratos e determinísticos —
  densidade em ROI, permanência (loitering), pessoa junto a veículo fora de horário. Custo adicional zero.
- **Estágio 2 (sob demanda):** o trigger dispara o VLM sobre **4–8 keyframes do clipe de evidência que já
  gravamos** (ADR-0033, 20–30s). Isso derruba a taxa de chamada de `28 × fps` para **~1–10 por minuto** — aí os
  segundos de latência viram aceitáveis e o modelo cabe no orçamento.

É o mesmo padrão do **NVIDIA VSS** (Video Search and Summarization), que a própria NVIDIA cita como caso de uso.

**O ganho maior talvez seja colateral:** o VLM vira a **justificativa em linguagem natural** do alerta
("3 pessoas próximas ao veículo há 2 minutos, uma manipulando a maçaneta"). Isso é diferencial real sobre
bounding box e **reduz drasticamente o custo de triagem humana de falso-positivo** — que é o que mata sistema de
vigilância em produção.

#### ⚠️ Cosmos Reason2: conflito de licença com o nosso white-label

Cosmos Reason2 é pós-treino sobre Qwen3-VL, e a categoria onde ele mais ganha é exatamente a nossa:

| Categoria | CR2-2B | Qwen3-VL-2B | CR2-8B | Qwen3-VL-8B |
|---|---|---|---|---|
| **Smart Spaces (Warehouse AI)** | **64,14** | 36,63 | **69,96** | 42,66 |
| General Overall | 62,21 | 59,60 | 73,73 | 71,98 |

Em "General" o ganho é marginal (+2,6). O ganho real (**+27,5 pts**) está em **espaço monitorado**.

**Mas a licença é `NVIDIA Open Model License`, não Apache.** Comercial permitido, sem copyleft, e a NVIDIA não
reivindica os outputs — porém:

🔴 **Seção 3.2 — atribuição obrigatória "Built on NVIDIA Cosmos"** para produtos/serviços derivados.
**Colide frontalmente com o white-label por tenant (ADR-0035).** Precisa de parecer jurídico antes de qualquer
commit — não é detalhe de rodapé.

Outros pontos: licença "perpétua **mas revogável**"; terminação automática se "reduzir a eficácia" de guardrails
(zona cinzenta para fine-tune de detecção de furto); terminação por litígio; obrigação de indenizar a NVIDIA;
download gated (conta NGC + aceite no HF).

**Memória:** CR2-**8B pede 18 GB → fora da máquina inteira** (temos 16 GB totais). CR2-**2B pede 8 GB em FP8 →
exatamente todo o nosso headroom, sem margem**. A rota viável é **GGUF Q4_K_M via llama.cpp: ~1,28 GB + mmproj
819 MB ≈ 2,1 GB**.

⚠️ **Footgun:** `--gpu-memory-utilization` do vLLM é fração da memória **TOTAL**, não da livre, e o vLLM
**pré-aloca** o pool. Copiar o comando do AGX Orin (`0.8`) no nosso box reserva ~12,8 GB e **mata o DeepStream**.
Em memória unificada, isso é grave.

**Recomendação de engine:** começar por **llama.cpp + GGUF Q4** (não pré-aloca pool hostil, é a rota que a própria
NVIDIA marca como recomendada para memória restrita, e serve API OpenAI-compatible). vLLM só se sobrar folga — e
note que, no nosso perfil de RAM, o vLLM só roda com `--max-num-seqs 1`, que é justamente **desligar o
continuous batching** que era a razão de escolhê-lo.

**Alternativa Apache:** **Qwen3-VL-8B é Apache 2.0** e a página lista **Orin NX como mínimo** (AWQ 4-bit, 8 GB).
Se o parecer jurídico barrar o Cosmos, este é o plano B sem o problema de atribuição.

⚠️ **Risco de produto, não de licença:** o card de Bias do Cosmos declara *"Participation considerations from
adversely impacted groups: **None**"*. Usar isso para sinalizar "suspeição" sobre pessoas identificáveis, no
Brasil, sob LGPD, é exposição concreta. **O output nunca deve ser "pessoa X é suspeita"** — deve ser descrição
factual de evento ("3+ pessoas paradas junto ao veículo por >2min") com decisão humana no loop.

### O4 — Live VLM WebUI como bancada (Apache 2.0)

Não é blueprint de produção (RTSP em Beta testado só com Reolink; 1 stream, 1 usuário, sem auth, sem
multi-tenancy). **Mas quatro padrões são transferíveis:**

1. **Desacoplamento total via API OpenAI-compatible** — o WebUI não sabe qual engine roda. Estende naturalmente
   o nosso `INFERENCE_ENGINE` (ADR-0001/0015) para um `VLM_BACKEND_URL`.
2. **Processamento assíncrono desacoplado do stream** — o vídeo flui em tempo real, a análise chega quando chega.
   **Nunca bloquear o pipeline de vídeo esperando o VLM.**
3. **"Frame Processing Interval"** — 1 frame a cada N. É o dial de custo.
4. **Monitor de GPU/VRAM (jtop) na mesma tela do resultado** — indispensável para avaliar co-residência.

Já vem com preset "Safety Monitoring": *"Are there any safety hazards visible? Answer with 'ALERT: description'
or 'SAFE'."* — literalmente o formato de output que queremos no estacionamento.

### O5 — Metodologia de benchmark (`vllm bench serve`)

Métricas: **TTFT** (time to first token), **ITL** (inter-token latency), **E2EL** (end-to-end), throughput.
Protocolo: reboot → `nvpmodel -m 0` → `drop_caches=3` → **warm-up de 50 prompts descartados** → medir em C=1 e C=8.

**Onde é insuficiente para nós — o que adicionar:**
- O default `--hf-output-len 128` é irreal para reasoning VLM (a NVIDIA recomenda 4096 para o Cosmos) →
  **subestima a latência real por uma ordem de grandeza**. Medir **E2EL**, não TTFT.
- Falta a métrica que decide o negócio: **frame capturado → alerta emitido**, ponta a ponta.
- Falta **acuracidade** — precisamos de conjunto rotulado das nossas câmeras e taxa de FP/FN.
- Falta **co-residência** — o protocolo assume o Jetson sozinho. Nosso teste tem que ser **com o DeepStream das
  28 câmeras rodando**. Benchmark isolado não diz nada sobre nós.
- Falta **regime térmico sustentado** — MAXN + reboot mede o melhor caso; produção é 24/7.

### O6 — CUDA graphs para overhead de launch

O runtime C++ do Edge-LLM faz **captura de CUDA graphs**. Isso **transfere para detecção**, e o ganho é maior
justamente no nosso perfil: modelos pequenos, FPS alto, muitos streams — onde o overhead de CPU no launch de
kernel é proporcionalmente grande. Vale investigar como otimização real.

---

## 5. TENDÊNCIA — e por que ela não deve mudar nosso produto agora

### O Jetson AI Lab saiu de visão computacional clássica

Evidência estrutural, não impressão:

- **22 tutoriais. Zero sobre detecção clássica, DeepStream ou IVA.** O único item de CV é o NanoOWL, e ele lista
  apenas JetPack 5 e 6 — não foi atualizado para JP7. É conteúdo legado.
- **O catálogo `/models` é 100% generativo** — 46 modelos, todos LLM/VLM (Gemma, Nemotron, Cosmos, Qwen, Llama,
  Mistral). **Busca por "YOLO" retorna zero.** Os campos do schema são `context_length`, `ttftMs`,
  `supported_inference_engines`. **Nada sobre mAP ou bounding box.**
- **Tagline:** *"Experience the latest generative AI models optimized for Jetson."*
- **Todo o material clássico foi para `/archive`** com banner permanente.
- **Sinal organizacional:** **Dustin Franklin (dusty-nv)** — autor do `jetson-inference` e do `jetson-containers`,
  figura central da era CV do Jetson — está listado como **emeritus, "Formerly NVIDIA"**.

**A NVIDIA diz por escrito que enxerga VLM canibalizando detector.** Na página do Live VLM WebUI, seção
"Computer Vision Pipeline Alternatives": *"VLMs podem substituir ou aumentar pipelines de CV tradicionais... o
VSS demonstra essa abordagem em deployments de smart city."*

**Minha leitura:** a tendência é real, mas a aritmética não fechou. 0,125–1 fps por stream contra 28 câmeras em
tempo real não é questão de otimização — é ordem de grandeza. **A leitura correta não é "migre para VLM"; é
"detector continua sendo a camada de tempo real, VLM vira a segunda camada acionada por evento"** — que é
exatamente O3, roda no compute que temos, e usa infraestrutura que já construímos.

### Hardware: não mexer

| Série | Módulo | Memória / BW | Potência |
|---|---|---|---|
| Thor (Blackwell) | T4000 | 64 GB / 273 GB/s | **40–70 W** |
| Orin NX (Ampere) | **16 GB** | 16 GB / **102,4 GB/s** | **10–40 W** |

- **O Orin NX não está sendo substituído.** Ciclo de vida **estendido de Q1 2030 para Q1 2032**, e aparece como
  módulo de produção corrente (157 TOPS Super), não legado.
- **Não existe SKU Thor no envelope do Orin NX.** O Thor mais barato começa em 40 W e 64 GB. São classes de
  produto, térmica e custo diferentes. **Thor é upgrade de AGX Orin, não de Orin NX.**
- **O salto de 2,7× em banda (102→273 GB/s) é decisivo para decode de LLM (bandwidth-bound) e quase irrelevante
  para detecção multi-stream (compute-bound em convolução INT8).** Ou seja: **o ganho do Thor é
  desproporcionalmente generativo.** Para 28 câmeras com detector, o Orin NX não está deixando dinheiro na mesa.
- **Thor = SKU de upsell** para cliente que queira camada VLM/reasoning, não caminho de migração.
- **IGX** está posicionado para edge industrial com *functional safety* — vale ter no radar para cliente que
  exija certificação.

### Quantização: o ganho é INT8, não FP4

| Precisão | Orin (SM87) | Thor (SM110) |
|---|---|---|
| FP16 | ✅ | ✅ |
| **FP8** | ❌ **não existe no silício** | ✅ |
| INT4 AWQ | ✅ (irrelevante p/ detecção) | ✅ |
| **NVFP4** | ❌ **não existe no silício** | ✅ |

FP8 exige SM89+, NVFP4 exige SM110+. **Ampere não tem esses tensor cores — não é software, é silício.** Toda a
narrativa FP4/NVFP4 da NVIDIA é, para nós, conteúdo sobre hardware que não temos.

**O que a tabela omite: INT8** — porque é tabela de LLM. Mas os tensor cores Ampere do Orin **fazem INT8
nativamente**, e INT8 é exatamente a precisão certa para detecção. **É o 2× que existe no nosso silício.**

⚠️ **RF-DETR e D-FINE são família DETR** — têm cabeça transformer com atenção, e INT8 em blocos de atenção
degrada mAP com mais frequência que em CNN pura. A prática usual é **precisão mista** (backbone INT8,
cabeça/atenção FP16); o TensorRT suporta constraints por camada exatamente para isso.
**Tratar como experimento com medição de mAP, não como flag.**

**INT4 AWQ não transfere** para detecção: é weight-only, desenhada para decode autorregressivo memory-bound.
Detecção a 640×640 é compute-bound, com footprint de pesos minúsculo (YOLOX-S ~9M, RF-DETR-B ~29M).

---

## 6. Research Group: dois tópicos que são o nosso problema

A página de comunidade **não tem sinal** para vigilância industrial (tags: robótica, agentes, RAG, ROS2 — nenhuma
de Detection/Surveillance/IVA). **Não investir tempo nela.**

O Research Group, sim:

- ⭐ **"Continuous multi-image VLM streaming and change detection"** — é literalmente o problema de vigilância:
  streaming contínuo com detecção de mudança em vez de VLM-por-frame. **É exatamente a técnica que tornaria a
  camada VLM viável em custo.** O tópico mais relevante da página inteira.
- ⭐ **"Guidance, grammars, and guardrails for constrained output"** — se um VLM entra no pipeline, forçar saída
  JSON estruturada é a diferença entre demo e produto. Precisaríamos disso no dia 1.
- "Controller LLMs for dynamic pipeline code generation" — casa com a nossa tese de modelo por cliente.
- "Fine-tuning onboard Jetson **AGX Orin 64GB**" — note o hardware; **não cabe no Orin NX 16GB**.

**Contatos com aderência industrial:** Doruk Sönmez (ConnectTech, *Intelligent Video Analytics Engineer* — a
**única pessoa com tag IVA** na lista), Michael Grüner (RidgeRun — consultoria de pipeline GStreamer/câmera,
relevante se precisarmos de ajuda externa em DeepStream), Song Han (MIT HAN Lab, autor do AWQ).

⚠️ **Frescor:** "Future Meetings" só até 13/01/2026 e a gravação mais recente é de 09/09/2025. A página está
desatualizada — tratar como **declaração de intenção, não pesquisa ativa comprovada**. O canal vivo é o Discord.

---

## 7. AÇÕES RECOMENDADAS (em ordem)

| # | Ação | Por quê |
|---|---|---|
| 1 | **Verificar se o DeepStream 9.1 saiu** | Define se existe caminho para JP7.2 em Orin. É o item de roadmap |
| 2 | **Copiar as landmines L1–L8 para `REGRAS_PLATAFORMA_JETSON.md`** | É o doc vivo; L1 sozinha economiza dias |
| 3 | **Congelar JP6.2 + DS 7.1 como baseline de produção** e registrar o motivo | Última combinação Orin+DeepStream suportada |
| 4 | **Aplicar as otimizações de RAM que faltam** (GUI headless, nvargus; decidir zram conscientemente) | ~800 MB+ no box, baixo custo, alto retorno |
| 5 | **Avaliar `jetson-device-skills` + `jetson-bsp-skills`** | Resposta estrutural ao provisionamento manual (task-097, ADR-0040) |
| 6 | **Golden image + registry privado** (build no bench, pull no cliente, pinado por digest) | Build de ~10 GB no cliente é inviável; e não há imagem r36.4 pronta |
| 7 | **NanoOWL como pré-anotação offline** (só caminho OWL-ViT puro, sem CLIP; ONNX+TRT próprio, sem torch2trt) | Encaixa no slot `SERVICE_TYPE=pre-annotation` já existente |
| 8 | **Experimento INT8 com precisão mista** em RF-DETR/D-FINE, medindo mAP | É o único ganho de quantização real no Ampere |
| 9 | **Parecer jurídico: "Built on NVIDIA Cosmos" × white-label (ADR-0035)** | Bloqueador de decisão, não de implementação. Alternativa: Qwen3-VL (Apache) |
| 10 | **PoC VLM de dois estágios** sobre clipes de evidência (llama.cpp Q4, com DeepStream rodando junto) | Diferenciação de produto que cabe no compute que temos |

---

## 8. O que NÃO foi possível determinar

- Se o **DeepStream 9.1 já foi lançado** (dado mais recente: 02/07/2026, NVIDIA dizendo "será a 9.1").
- **Número de performance do NanoOWL no Orin NX 16GB** — só existem números para AGX Orin; Orin Nano está "TBD".
- **Nenhum número de performance do Cosmos Reason2 em qualquer Jetson** — o próprio model card diz que a latência
  "will be published shortly", e o hardware de teste declarado é H100/A100.
- Se o **ModelOpt / `tensorrt-edgellm-quantize`** cobre modelos de detecção com o mesmo CLI.
- Licença do repo **quangdungluong/DeepStream-YOLOv11** (parsers D-FINE) — verificar antes de usar.
