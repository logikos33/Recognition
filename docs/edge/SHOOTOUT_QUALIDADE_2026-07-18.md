# Shootout do Modelo de Qualidade — D-FINE × RT-DETRv4 × RF-DETR

**Data:** 2026-07-18 · **Box:** Jetson Orin NX 16GB (`pandora`, JP6.2 / TRT 10.3 / DS 7.1) · **Módulo:** Qualidade (RVB)
**Juiz:** `mAP_small` (objeto pequeno) — a Qualidade inspeciona **detalhe milimétrico por ROI** (2 câmeras 4MP,
disparo por código de barras da monofatura); acurácia em objeto pequeno **vale mais que throughput**.
**Trava de licença:** ADR-0043 (ZERO AGPL no caminho servido) · **Detector plugável:** ADR-0044 · **Cenário:** ADR-0053.

---

## ⚠️ STATUS HONESTO (ler antes da tabela)

Este relatório separa **três níveis de evidência** e **não mistura** — nenhum número é inventado (C-04):

| Nível | O que é | Comparável entre si? |
|---|---|---|
| **A. Medido no NOSSO dataset (Orin)** | RF-DETR Nano, YOLOX-S, YOLOX-Tiny — `cocoeval` na val PPE (reuso, treinos anteriores). D-FINE-S: **treino iniciado nesta sessão, trajetória parcial** | ✅ **Sim** — mesma régua, mesmo `AP_small` |
| **B. Publicado (COCO, papers)** | D-FINE / RT-DETRv4 / RF-DETR AP_S de COCO val2017 | ⚠️ **Só ranqueia arquitetura** — COCO ≠ nosso domínio; **não prevê o número absoluto na RVB** |
| **C. Estimado / pendente** | Latência Orin extrapolada de T4; engines TRT + parsers D-FINE/RT-DETRv4; INT8; stress 2×4MP | ❌ ainda não medido no box |

**Estado do head-to-head nível A:** **D-FINE-S FECHOU** — convergiu em 30 épocas (3h07m) e **bateu o RF-DETR no
juiz** (AP_small 0.626 vs 0.565) no NOSSO dataset. **RT-DETRv4 ainda pendente**, e faltam os gates de nível C
(engines TRT fp16/INT8, 2 parsers DeepStream, stress 2×4MP junto dos outros 2 módulos = trabalho de dias) **e**
uma comparação de **orçamento igual** (D-FINE teve 3× as épocas do RF-DETR). O que fechou: **pesquisa + licenças
+ baseline medido do incumbente + D-FINE-S convergido e vencedor no juiz (régua de treino ainda desigual)**.
**Veredito na seção 8.**

---

## 1. Protocolo justo (mesma régua — senão o bench não vale)

| Eixo | Definição | Estado |
|---|---|---|
| **Dataset** | SiaBar PPE-COCO no box (`~/jetson-experiments/dataset/ppe-coco`): 1126 train / 326 val / 161 test, 9 categorias (efetivas: Boots, Helmet, Person, Vest — as outras 5 têm ≤6 anotações) | ✅ mesmo p/ todos |
| **Split** | train/valid do Roboflow, idêntico ao usado no RF-DETR/YOLOX | ✅ |
| **Métrica** | `cocoeval` `AP_small/medium/large` + `AP@0.5:0.95` na val | ✅ |
| **Orçamento** | fine-tune do checkpoint pré-treinado, épocas equiparáveis ao RF-DETR (~10 ep). D-FINE-S: 30 ep programadas, batch 2 (Orin) | ⚙️ em execução |
| **Resolução** | 640 (entrada por ROI — recorte, não frame 4MP inteiro, como em produção) | ✅ definido |
| **Hardware** | Orin NX, clocks travados (`jetson-clocks` systemd, §7 REGRAS) | ✅ |

> **Proxy honesto:** o dataset de Qualidade real da RVB (vedação/isolamento) **ainda não existe rotulado**. O
> PPE-COCO é o **proxy comum** (mesmo que EPI/Estacionamento usaram) — mede a capacidade de objeto pequeno da
> arquitetura na mesma régua. O número final da Qualidade exige re-rodar no dataset RVB quando ele existir.

## 2. Auditoria de licença (gate ADR-0043 — pesquisa 2026-07-18, fontes primárias)

| Modelo | Licença código | Licença pesos | Servível livre? | Observação |
|---|---|---|---|---|
| **D-FINE** (Peterande, ICLR'25) | **Apache-2.0** | **Apache-2.0** | ✅ **Sim** | pesos mais fortes = pré-treino Objects365 (dataset de licença restrita, mas os *pesos* são Apache) |
| **RT-DETRv4** (PKU/THU, ECCV'26) | **Apache-2.0** | **Apache-2.0** | ✅ **Sim** | **destila DINOv3 só como *teacher* no treino**; grafo servido = CNN HGNetv2 (sem ViT). Risco jurídico DINOv3 **só se re-treinar a distilação do zero** — irrelevante p/ fine-tune do checkpoint liberado. Registrar a flag no parecer ADR-0043 |
| **RF-DETR** Nano–Large (incumbente) | **Apache-2.0** | **Apache-2.0** | ✅ **Sim** | já servido; XL/2XL = PML 1.0 (proibidas — só proposta comercial) |

**Nenhum candidato aciona a trava do ADR-0043.** Os três são permissivos e serviveis. (RT-DETRv2 PyTorch,
fallback conservador, também Apache-2.0 e **sem** entanglement com foundation model.)

Fontes: D-FINE `github.com/Peterande/D-FINE` (LICENSE Apache-2.0) · arXiv 2410.13842 · HF `ustc-community/d-fine` (apache-2.0).
RT-DETRv4 `github.com/RT-DETRs/RT-DETRv4` (Apache-2.0) · arXiv 2510.25257 (ECCV 2026). RT-DETRv2 `github.com/lyuwenyu/RT-DETR/blob/main/LICENSE`.
RF-DETR `github.com/roboflow/rf-detr` (Apache-2.0). DINOv3 license `ai.meta.com/.../dinov3-license`.

## 3. Reuse-first (§6 REGRAS) — REUSADO vs NOVO

| REUSADO (não reconstruído) | NOVO (delta desta sessão) |
|---|---|
| `train-venv` (torch 2.11 Jetson) — **revivido** via `LD_LIBRARY_PATH` (§3.4 REGRAS) | Workspace `~/jetson-experiments/shootout/` |
| Dataset `ppe-coco` (mesmo split) | Clones D-FINE + RT-DETRv4 (Apache) |
| Baselines medidos: RF-DETR Nano, YOLOX-S/Tiny (`train_metrics/*.jsonl` + `sizes.json`) | Config D-FINE-S custom p/ PPE (9 classes, batch Orin) |
| Parser RF-DETR `~/jetson-experiments/rfdetr-parser/` + engines RF-DETR/YOLOX | Fine-tune D-FINE-S em curso (`out_dfine_s/`) |
| Harness de stress/soak (campanha + task-113) | Landmines de treino → REGRAS §3.4 |
| `EXPLORACAO_MODELOS_2026-07-17.md` (pesquisa de arquiteturas — este shootout é a execução do "próximo passo" dela) | — |

## 4. Nível A — MEDIDO no nosso dataset PPE (Orin, `cocoeval` na val, o que decide)

| Modelo | Params | `AP_small` ⬅ **JUIZ** | AP_medium | AP_large | AP@.5:.95 | AP50 | Fonte |
|---|---|---|---|---|---|---|---|
| **RF-DETR Nano** (incumbente) | ~14M | **0.565** | 0.549 | 0.803 | **0.754** | 0.968 | `rfdetr-nano-ppe.sizes.json` (best EMA, n=326) |
| YOLOX-S | ~9M | 0.521 | 0.500 | 0.751 | 0.723 | 0.958 | `yolox-s-ppe.jsonl` ep10 |
| YOLOX-Tiny | ~5M | 0.385 | 0.504 | 0.742 | 0.712 | — | `yolox-tiny-ppe.jsonl` ep10 |
| **D-FINE-S** (Obj365→COCO, fine-tune, **30 ep**) | 10.18M | **0.626** ⬅ **bate o RF-DETR** | ~0.55 | ~0.85 | **0.776** | ~0.97 | `out_dfine_s/train_final.log` — **convergido** (best ep29, 3h07m) |
| **RT-DETRv4-S** | 10M | ⏳ pendente (mesma stack, próximo) | — | — | — | — | — |

**Leitura do nível A:** na régua que importa (`AP_small`), o **RF-DETR Nano lidera o que já foi medido**
(0.565), **+0.044 sobre o YOLOX-S** (modelo maior) e **+0.180 sobre o YOLOX-Tiny**. A tese "transformer domina
objeto pequeno" **se confirma no nosso dado** — é exatamente por isso que a Qualidade é módulo de transformer.
D-FINE-S e RT-DETRv4-S precisam **bater 0.565** aqui para justificar a troca.

> **✅ D-FINE-S CONVERGIU e BATEU o RF-DETR no juiz (atualizado 2026-07-18):** o fine-tune completou **30 épocas
> (3h07m)** no box → **AP_small ≈ 0.626** (best epoch 29; AP@.5:.95 = **0.776**), **+0.061 de AP_small sobre o
> RF-DETR Nano (0.565)** e +0.022 de AP total. Trajetória: 0.160 (ep1) → 0.486 (ep2) → 0.626 (convergido). É um
> resultado **medido no NOSSO dado** — D-FINE-S é candidato **provado**, não só promessa de COCO.
>
> **⚠️ MAS não é apples-to-apples ainda (por isso o veredito não fecha):** o D-FINE-S rodou **30 épocas** vs
> **~10** do RF-DETR Nano — orçamento de treino **desigual**. Para veredito justo falta: **(a) RF-DETR
> budget-matched** (30 ep) OU D-FINE budget-matched (10 ep); **(b) RT-DETRv4-S/M**; **(c) nível C** (engine
> TRT fp16/INT8 + parser DETR + stress 2×4MP). O D-FINE-S superar o RF-DETR **com 3× o orçamento** prova teto
> mais alto, não vitória com régua idêntica. **Sinal forte, decisão pendente.**

## 5. Nível B — PUBLICADO (COCO val2017 AP_S — ranqueia arquitetura, NÃO prevê nosso número)

| Variante | D-FINE (COCO) | D-FINE (Obj365→COCO) | RT-DETRv4 | RF-DETR |
|---|---|---|---|---|
| S | AP_S 29.1 | **32.7** | AP_S **30.2** | (Nano AP 48.4) |
| M | 33.2 | **37.9** | **34.9** | (Small AP 53.0) |
| L | 36.5 | — | **37.1** | (Large AP 56.5) |
| X | 37.3 | — | **39.5** | — |

**Leitura:** a COCO AP_S ranqueia **RT-DETRv4 ≳ D-FINE** em igual tamanho; **D-FINE-M com pré-treino Objects365
(37.9) ≈ RT-DETRv4-X (39.5) a 1/3 dos params** — o melhor AP_S-por-param permissivo. **RT-DETRv4 é a ÚNICA
família que publica AP_S** (v2/v3 não publicam → escolher v2/v3 é voar cego na métrica-juiz). ⚠️ **COCO AP_S é
"small na distribuição COCO inteira" (<32²px) — o número absoluto na RVB será outro; isto só diz quem tende a
ganhar, não por quanto.**

Fontes nível B: D-FINE paper Tab.7 (arXiv 2410.13842) · RT-DETRv4 Tab.1 (arXiv 2510.25257) · RF-DETR repo/ICLR'26.

## 6. Nível C — Custo/edge (estimado + pendente de medição no box)

- **Latência Orin (fp16, estimada de T4 ×~0.4, §EXPLORACAO):** D-FINE-S ~115 inf/s · M ~70 · L ~50 · X ~31.
  RT-DETRv4-S ~110 · M ~68 · X ~31. **RF-DETR Nano = 172 inf/s MEDIDO** (único número real de latência edge).
  Alvo Qualidade: 2–4 cams × 5–15 inf/s/ROI = 10–60 inf/s → **qualquer variante S/M/L fecha** com folga.
- **DLA:** transformer (attention/LayerNorm) **não roda em DLA** — vale p/ D-FINE, RT-DETRv4 e RF-DETR
  (irrelevante: DLA já descartado, exp 103-102). Todos GPU-only fp16.
- **INT8:** DETR quantiza **pior** que CNN (atenção/softmax + head FDR do D-FINE sensíveis; §3.2/§3.4 REGRAS).
  **Servir fp16**; INT8 só com QAT + validação de `AP_small` pós-quant. Não bancar speedup INT8 aqui.
- **Parser DeepStream:** RF-DETR **já tem** (`rfdetr-parser/`). D-FINE e RT-DETRv4 = **parser novo** (saída
  NMS-free `cxcywh` norm + sigmoid; D-FINE preproc **0-1 RGB sem ImageNet-norm**, RT-DETRv2+ idem — DIFERENTE do
  RF-DETR ImageNet-RGB e do YOLOX BGR 0-255). Um parser DETR genérico cobre a família (gap da task-100).
- **Stress 2×4MP + 2 outros módulos:** o soak task-113 **já rodou** `soak-infer-qmain` (2×4MP RF-DETR ROI)
  co-residente com EPI(16)+Park(8)+Qaux(2) por 4.8h, GPU 76% avg, 0 stream morto, sem OOM. **Headroom provado
  para o incumbente**; para D-FINE/RT-DETRv4 é re-rodar o mesmo harness com o engine novo.

## 7. Comportamento de treino no box (nível A — achado desta sessão)

- **`train-venv` estava quebrado** (`libcudss.so.0`); **revivido** só com `LD_LIBRARY_PATH` (torch 2.11, iGPU OK).
- **D-FINE-S treina no Orin:** deps instaladas sem clobberar torch (constraints pinado), checkpoint Obj365→COCO
  carregado (head re-inicializado p/ 9 classes — esperado), 10.18M params / 24.86 GFLOPs confirmados, dataloaders
  batch 2/4, **loop de treino rodando** co-residente com o soak (GPU compartilhada). Landmines → REGRAS §3.4.
- **RT-DETRv4** tem a MESMA stack de deps → mesmo procedimento (próximo item do plano).
- Métricas por época (loss, LR, `AP_small/medium/large`, precision/recall) logadas em `out_dfine_s/` — **base
  para o Training Studio** (item 3 da task-111), no mesmo formato dos `train_metrics/*.jsonl` já persistidos.

## 8. VEREDITO PROVISÓRIO

> **D-FINE-S CONVERGIU e superou o RF-DETR no juiz (AP_small 0.626 vs 0.565) no NOSSO dataset — mas a decisão
> final NÃO está fechada.** O D-FINE-S é agora um **candidato PROVADO**, não promessa de COCO. Porém venceu com
> **orçamento de treino 3× maior** (30 ép vs ~10 do RF-DETR) e **sem os gates de nível C** (engine TRT, parser
> DeepStream, stress 2×4MP no cenário 3-módulos). Portanto: **incumbente RF-DETR permanece em produção AGORA**
> (é o único com parser+engine+soak-2×4MP validados), e **D-FINE-S entra como forte favorito a substituí-lo**
> assim que o head-to-head justo fechar. Não é "RF-DETR continua porque ninguém bateu" — é "D-FINE-S bateu com
> régua desigual; falta a régua igual + integração antes de trocar um detector em produção".

**Ordem de prioridade para FECHAR o head-to-head (nível A) — o que falta:**

1. **D-FINE-M (Obj365→COCO)** — melhor `AP_small`-por-param publicado (37.9), Apache limpo, sem entanglement.
   *Primário a bater.* (D-FINE-S já em treino como prova de viabilidade.)
2. **RT-DETRv4-M** — co-primário: única família que publica AP_S, mesmo custo, flag DINOv3-teacher (só registro).
3. **RF-DETR Small** — upgrade de menor atrito do incumbente (mesmo parser/pipeline), sobe de Nano→Small
   (+AP a ~115 inf/s) — o "bater 0.565" pode vir do próprio RF-DETR sem trocar de família.

**Critério de decisão (quando o nível A fechar):** vence quem tiver **maior `AP_small` na val PPE (e depois no
dataset RVB real)**; empate técnico → menor latência Orin fp16 + menor custo de integração (parser/engine).
Se D-FINE-M ou RT-DETRv4-M superarem 0.565 **de forma clara** (≥ +0.03 AP_small) e couberem no orçamento de GPU
do cenário 3-módulos (ADR-0053), promover; senão, **RF-DETR Small** é o upgrade seguro.

**Plano para fechar (harness pronto, `~/jetson-experiments/shootout/`):** (a) concluir D-FINE-S/M + RT-DETRv4-S/M
fine-tune → `cocoeval AP_small`; (b) export ONNX→TensorRT fp16 (+INT8 calibrado, validar AP_small pós-quant);
(c) parser DETR genérico DeepStream; (d) re-rodar stress 2×4MP no cenário 3-módulos; (e) escrever addendum no
ADR-0043/0044 com o vencedor. **Não promover a staging/main (gate humano).**

## 9. Referências pesquisadas
- D-FINE: https://github.com/Peterande/D-FINE · https://arxiv.org/abs/2410.13842 · https://huggingface.co/collections/ustc-community/d-fine
- RT-DETRv4: https://github.com/RT-DETRs/RT-DETRv4 · https://arxiv.org/abs/2510.25257 (ECCV 2026)
- RT-DETRv2 (fallback Apache, sem foundation-model): https://github.com/lyuwenyu/RT-DETR · https://arxiv.org/abs/2407.17140
- RF-DETR: https://github.com/roboflow/rf-detr · https://rfdetr.roboflow.com/latest/
- DINOv3 license (flag RT-DETRv4/DEIMv2): https://ai.meta.com/resources/models-and-libraries/dinov3-license/
- Contexto interno: `EXPLORACAO_MODELOS_2026-07-17.md` · `CAMPANHA_ESCALA_2026-07-17.md` · `REGRAS_PLATAFORMA_JETSON.md` §3.2/§3.4 · ADR-0043/0044/0053
