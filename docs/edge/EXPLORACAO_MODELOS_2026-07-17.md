# Exploração de Modelos de Detecção — Alternativas a YOLOX e RF-DETR

**Data:** 2026-07-17 · **Alvo de deploy:** NVIDIA Jetson Orin NX 16GB (TensorRT 10.3, DeepStream 7.1)
**Trava de licença:** ADR-0043 — ZERO GPL/AGPL no caminho servido. Permissivo (Apache-2.0/MIT/BSD) = ok. Não-permissivo só em "Propostas comerciais explícitas".
**Referência de arquiteturas:** página de comparação Ultralytics (https://docs.ultralytics.com/compare/) e Roboflow Playground/Universe.

**Nossos números de referência (Orin NX 16GB, dataset PPE próprio):**
- YOLOX-Tiny fp16 = 549 inf/s teto (mAP 71.2) · YOLOX-Tiny INT8 > 600 inf/s · YOLOX-S = mAP 72.3
- RF-DETR Nano = 172 inf/s teto (mAP 75.6)
- Alvo: 5 inf/s por câmera → 16 cams EPI = 80 inf/s · 8 cams estacionamento = 40 inf/s · 2-4 cams qualidade = 10-20 inf/s · total 28-40 cams ≈ 140-200 inf/s agregado (com folga p/ picos)

**Regra de conversão usada (estimativa):** latência T4 fp16 → Orin NX ≈ fator ~0,4× do throughput T4 (calibrado pelo par RF-DETR Nano: 2,3 ms T4 ≈ 435 inf/s → 172 inf/s medidos no Orin). Estimativas marcadas com `~`. **Nada substitui benchmark no box real (harness da campanha de escala, PR #192).**

---

## Tabela-resumo

| Modelo | Licença código / pesos | Comercialização | mAP COCO (variantes) | Custo inferência (T4 fp16, 640 salvo nota) | DeepStream/TensorRT | Veredito por módulo |
|---|---|---|---|---|---|---|
| **D-FINE** (USTC) | Apache-2.0 / Apache-2.0 | Livre | N 42.8 · S 48.5 · M 52.3 · L 54.0 · X 55.8 (Obj365+COCO: S 50.7 · L 57.3 · X 59.3) | N 2.12 ms · S 3.49 · M 5.62 · L 8.07 · X 12.89 | ONNX limpo, sem NMS (end-to-end), parser DETR-like (já temos p/ RF-DETR); transformer → sem DLA | **Qualidade: candidato forte (L/X Obj365)** · EPI: N/S viável |
| **DEIM** (D-FINE + matching) | Apache-2.0 / Apache-2.0 | Livre | DEIM-D-FINE: S 49.0 · M 52.7 · L 54.7 · X 56.5 | Mesma latência do D-FINE base (S 3.49 · L 8.07 · X 12.89) | Idem D-FINE | Upgrade "grátis" sobre D-FINE (mesmo custo, +0.5-0.7 mAP) |
| **DEIMv2** (DINOv3-based) | Apache-2.0 (repo) / **⚠ pesos: cadeia DINOv3 (licença custom Meta)** | Ler termos DINOv3 p/ L/X; variantes HGNetv2 ok | Atto 23.8 · Pico 38.5 · N 43.0 · S 50.9 · M 53.0 · L 56.0 · X 57.8 | Pico 2.13 ms · N 2.32 · S 5.78 · M 8.80 · L 10.47 · X 13.75 | ONNX ok; L/X = ViT (DINOv3) mais pesado de otimizar | S/M interessantes **se** cadeia de pesos auditada |
| **RT-DETR / v2** (Baidu, lyuwenyu) | Apache-2.0 / Apache-2.0 | Livre | v2: S 48.1 · M ~51 · L 53.4 · X 54.3 | v2-X ≈ 74 FPS T4 (13.5 ms) | Maduro; vários parsers públicos; transformer → sem DLA | Superado por D-FINE/DEIM (mesma família, menos mAP/ms) |
| **RT-DETRv4** (ECCV 2026) 🆕 | Apache-2.0 / Apache-2.0 (⚠ destilado de DINOv3 como *teacher* — ver nota) | Livre (flag jurídica leve) | S 49.8 · M 53.7 · L 55.4 · X 57.0 | S 3.66 ms · M 5.91 · L 8.07 · X 12.90 | Backbone CNN (HGNetv2) — DINOv3 só no treino; ONNX limpo | **Qualidade: candidato forte** (X 57.0 ao custo do D-FINE-X) |
| **LW-DETR** (Baidu) | Apache-2.0 / Apache-2.0 | Livre | tiny 42.6 · small 48.0 · medium 52.5 · large 56.1 | tiny ~2 ms · large ~8-9 ms (T4) | ViT encoder → sem DLA; ONNX ok | Interessante, mas D-FINE/RF-DETR dominam a curva |
| **RTMDet** (OpenMMLab) | ⚠ MMDetection: Apache-2.0; **MMYOLO: GPL-3.0** | Usar SÓ via MMDetection | tiny 41.1 · s 44.6 · m 49.4 · l 51.5 · x 52.8 | 300+ FPS (3090, l); CNN pura | **CNN → roda em DLA**; ONNX ok, precisa NMS (parser YOLO-like) | Alternativa CNN se quisermos DLA; ecossistema mmdeploy pesado |
| **DAMO-YOLO** (Alibaba) | Apache-2.0 / Apache-2.0 | Livre | T 43.6 · S 47.7 · M 50.2 · L 51.9 | T 2.78 ms · S 3.83 · M 5.62 · L 7.95 (T4) | CNN → DLA ok; ONNX ok + NMS externo | Sem manutenção desde ~2023; não supera YOLOX p/ nós |
| **PP-YOLOE+** (Baidu) | Apache-2.0 / Apache-2.0 | Livre | s 43.7 · m 49.8 · l 52.9 · x 54.7 (obj365 pretrain) | l ≈ 149 FPS T4 fp16 | CNN → DLA ok; export via Paddle2ONNX (fricção) | Bom mAP, mas ecossistema PaddlePaddle = atrito de treino |
| **YOLO-NAS** (Deci→NVIDIA) | Código Apache-2.0 / **pesos: licença custom NÃO-comercial** | Treinar do zero ou licença Deci/NVIDIA (repo abandonado) | s 47.5 · m 51.6 · l 52.2 | s ~2.4 ms T4 | CNN, DLA ok | **Descartar** (pesos proibidos, projeto morto) |
| **YOLOv9** (Academia Sinica) | **GPL-3.0** | Sem via comercial clara | c 53.0 · e 55.6 | ~ | — | **Proibido servir** (ADR-0043) |
| **YOLOv10** (THU-MIG) | **AGPL-3.0** (deriva de ultralytics) | Sem licença comercial própria | s 46.3 · m 51.1 · x 54.4 | end-to-end sem NMS | — | **Proibido servir** |
| **YOLOv12** (2025) | **AGPL-3.0** | Idem ultralytics | n 40.6 · s 48.0 · x 55.2 | ~ | — | **Proibido servir** |
| **Ultralytics YOLOv8/11/26** | **AGPL-3.0** código E pesos/modelos treinados | **Enterprise License** (cotação sob consulta; relatos ~US$5k/ano — não oficial) | YOLO26: n 40.9 … x 57.5 | YOLO26: 1.7–11.8 ms T4 | Melhor tooling do mercado; YOLO26 end-to-end sem NMS; CNN → DLA ok | Só via proposta comercial explícita (seção final) |
| **RF-DETR Nano–Large** (nosso atual) | Apache-2.0 / Apache-2.0 | Livre | Nano 48.4 · Small 53.0 · Medium 54.7 · Large 56.5 | Nano 2.3 ms · S 3.5 · M 4.4 · L 6.8 | Já rodando no nosso stack | Baseline transformer atual |
| **RF-DETR XLarge/2XL** | **PML 1.0 (não-permissivo)** via `rfdetr_plus` | Termos Roboflow | XL 58.6 · 2XL 60.1 | XL 11.5 ms · 2XL 17.2 | Idem RF-DETR | Só via proposta comercial explícita |
| **YOLOX** (Megvii, nosso atual) | Apache-2.0 / Apache-2.0 | Livre | Tiny 32.8 (COCO; 71.2 no nosso PPE) · s 40.5 | 549 inf/s Orin (medido) | Já rodando; CNN → DLA (testado e descartado por nós) | Baseline CNN atual |

*mAP_small: nenhum repo publica AP_small na tabela principal; papers da família DETR (D-FINE, RT-DETRv4, RF-DETR) reportam AP_s consistentemente acima de CNNs de mesmo custo — é o motivo estrutural (atenção global + queries) do RF-DETR ter batido YOLOX em +4.4 mAP no nosso dataset. Para o módulo Qualidade, medir AP_small no nosso dataset é obrigatório antes de decidir.*

---

## Seções por candidato

### 1. D-FINE (ICLR 2025 Spotlight) — ⭐ melhor custo-benefício permissivo
- **Licença:** Apache-2.0 (código e pesos). Sem asterisco.
- **Acurácia:** N 42.8 / S 48.5 / M 52.3 / L 54.0 / X 55.8. **Com pretrain Objects365+COCO: S 50.7 / M 55.1 / L 57.3 / X 59.3** — o X a 59.3 é o topo permissivo da classe real-time.
- **Custo:** N 2.12 ms / S 3.49 / L 8.07 / X 12.89 (T4 fp16). Estimado Orin NX: N ~190 inf/s, S ~115, L ~50, X ~31.
- **DeepStream:** export ONNX e TensorRT documentados no repo; end-to-end (sem NMS) → parser de saída DETR-like, mesmo padrão do gap que já fechamos para RF-DETR/YOLOX (task-100). Transformer híbrido (backbone HGNetv2 CNN + encoder/decoder) → **não roda em DLA** (irrelevante p/ nós: DLA já foi descartado na exp 103-102).
- **Treino custom:** repo próprio estilo RT-DETR (YAML configs, COCO format), fine-tuning a partir dos pesos Obj365 bem documentado. Dificuldade média (menos polido que Ultralytics/RF-DETR, mais que Paddle).
- Fontes: https://github.com/Peterande/D-FINE · https://roboflow.com/model/d-fine · https://datature.io/blog/real-time-object-detection-d-fine

### 2. DEIM (CVPR 2025) — D-FINE com treino melhor, mesmo custo
- **Licença:** Apache-2.0 (código e pesos).
- **Acurácia:** DEIM-D-FINE S 49.0 / M 52.7 / L 54.7 / X 56.5 — +0.5-0.7 mAP sobre D-FINE **na mesma latência** (é um framework de treino: Dense O2O matching + Matchability-Aware Loss sobre a arquitetura D-FINE).
- **Custo:** idêntico ao D-FINE (S 3.49 ms / L 8.07 / X 12.89 T4).
- **DeepStream:** export ONNX + TensorRT (`trtexec`) no repo; mesma viabilidade do D-FINE.
- **Treino custom:** mesmo fluxo do D-FINE. Se adotarmos D-FINE, adotar via DEIM.
- Fontes: https://github.com/Intellindust-AI-Lab/DEIM

### 3. DEIMv2 (set/2025) — SOTA absoluto, mas com asterisco de pesos
- **Licença:** repo Apache-2.0. **⚠ PESOS:** L/X usam **backbone DINOv3-S/S+** e variantes menores usam ViT-Tiny **destilado de DINOv3**. DINOv3 tem **licença custom da Meta** (comercial permitido, militar proibido, redistribuição de derivados deve carregar a licença DINOv3, acesso mediante cadastro). Ou seja: código permissivo, cadeia de pesos contaminável — exatamente o padrão "pesos ≠ código" que o ADR-0043 manda auditar.
- **Acurácia:** Atto 23.8 / Femto 31.0 / Pico 38.5 / N 43.0 / **S 50.9** / M 53.0 / L 56.0 / X 57.8. O S a 50.9 mAP em 5.78 ms é notável.
- **Custo:** Pico 2.13 ms / N 2.32 / S 5.78 / M 8.80 / L 10.47 / X 13.75 (T4).
- **DeepStream:** ONNX ok (há port C++/ONNX da comunidade); variantes ViT mais chatas de otimizar em TensorRT 10 que HGNetv2.
- **Veredito:** tecnicamente atraente, juridicamente o mais arriscado dos permissivos. Antes de servir, parecer sobre se pesos destilados de DINOv3 herdam a licença DINOv3. Alternativa mais limpa: RT-DETRv4 (abaixo).
- Fontes: https://github.com/Intellindust-AI-Lab/DEIMv2 · https://intellindust-ai-lab.github.io/projects/DEIMv2/ · https://ai.meta.com/resources/models-and-libraries/dinov3-license/ · https://github.com/facebookresearch/dinov3/issues/28

### 4. RT-DETR / RT-DETRv2 (Baidu / lyuwenyu, CVPR 2024)
- **Licença:** Apache-2.0 (código e pesos; versões Paddle e PyTorch).
- **Acurácia:** v2-S 48.1 / v2-L 53.4 / v2-X 54.3. **Superado por D-FINE/DEIM em toda a curva** (mesma linhagem — D-FINE é literalmente o sucessor).
- **Custo:** v2-X ≈ 74 FPS T4 (13.5 ms).
- **DeepStream:** o mais maduro da família — parsers públicos abundantes, suportado por NVIDIA TAO/Deformable-DETR docs como padrão de referência.
- **Veredito:** usar como fallback de compatibilidade, não como escolha primária.
- Fontes: https://github.com/lyuwenyu/RT-DETR · https://arxiv.org/pdf/2407.17140

### 5. RT-DETRv4 (ECCV 2026, nov/2025) — 🆕 achado relevante da pesquisa
- **Licença:** Apache-2.0 (código e checkpoints liberados em 17/11/2025).
- **Acurácia:** S 49.8 / M 53.7 / L 55.4 / **X 57.0** ao mesmo custo do D-FINE (X 12.90 ms).
- **Arquitetura-chave:** destila DINOv3 (ViT-B/16) **apenas como teacher durante o treino**; o modelo servido tem **backbone CNN HGNetv2** — sem ViT no runtime, engine TensorRT leve. Nota jurídica: destilação de teacher DINOv3 é risco menor que embutir o backbone (DEIMv2-L/X), mas vale registro no parecer do ADR-0043.
- **Custo:** S 3.66 ms / M 5.91 / L 8.07 / X 12.90 (T4). Estimado Orin: S ~110 inf/s, M ~68, X ~31.
- **DeepStream:** ONNX limpo, end-to-end, parser igual à família RT-DETR/D-FINE.
- **Treino custom:** fluxo RT-DETR (configs YAML, COCO). Repo novo — maturidade de comunidade ainda baixa.
- Fontes: https://github.com/RT-DETRs/RT-DETRv4

### 6. LW-DETR (Baidu)
- **Licença:** Apache-2.0 (copyright Baidu). tiny 42.6 → large 56.1. ViT encoder puro → engine mais pesada por mAP que D-FINE; comunidade pequena. Dominado por D-FINE e RF-DETR na curva. Fontes: https://github.com/Atten4Vis/LW-DETR

### 7. RTMDet (OpenMMLab)
- **Licença:** ⚠ bifurcada — implementação em **MMDetection = Apache-2.0**; em **MMYOLO = GPL-3.0**. Servir SOMENTE a variante MMDetection (issue open-mmlab/mmdetection#10557 documenta a diferença).
- **Acurácia:** tiny 41.1 / s 44.6 / m 49.4 / l 51.5 / x 52.8. CNN pura, forte em rotated boxes (irrelevante p/ nós hoje).
- **Custo:** RTMDet-l 300+ FPS em RTX 3090; sem número T4 oficial comparável.
- **DeepStream:** CNN clássica com NMS → parser YOLO-like simples; exporta via mmdeploy (dependência pesada no pipeline de treino).
- **Veredito:** única alternativa CNN permissiva moderna caso a estratégia DLA fosse retomada — mas descartamos DLA (exp 103-102), então não agrega sobre YOLOX.
- Fontes: https://github.com/open-mmlab/mmdetection/blob/main/configs/rtmdet/README.md · https://github.com/open-mmlab/mmdetection/issues/10557

### 8. DAMO-YOLO (Alibaba)
- **Licença:** Apache-2.0. T 43.6/2.78 ms · S 47.7/3.83 · M 50.2/5.62 · L 51.9/7.95 (T4). CNN (NAS backbone + RepGFPN). **Sem manutenção desde ~2023** — risco de bit-rot com TensorRT 10. Não supera a curva D-FINE nem justifica troca do YOLOX. Fontes: https://github.com/tinyvision/DAMO-YOLO

### 9. PP-YOLOE+ (Baidu PaddleDetection)
- **Licença:** Apache-2.0. s 43.7 → x 54.7 (pretrain Objects365). l ≈ 149 FPS T4 fp16. CNN.
- **Fricção:** treino em PaddlePaddle (framework fora do nosso stack), export via Paddle2ONNX. Custo operacional de manter segundo framework não compensa dado que D-FINE (PyTorch) entrega curva melhor.
- Fontes: https://github.com/PaddlePaddle/PaddleDetection · https://ar5iv.labs.arxiv.org/html/2203.16250

### 10. YOLO-NAS (Deci / SuperGradients) — descartar
- **Licença:** código super-gradients Apache-2.0, **PESOS pré-treinados sob licença custom Deci que PROÍBE uso comercial/produção** (LICENSE.YOLONAS.md). Deci foi adquirida pela NVIDIA (2024) e o repo está sem manutenção. Treinar do zero (sem os pesos) é permitido, mas sem pretrain o valor some. **Exemplo canônico de "pesos ≠ código" do ADR-0043.**
- Fontes: https://github.com/Deci-AI/super-gradients/blob/master/YOLONAS.md · https://github.com/Deci-AI/super-gradients/issues/1993 · https://roboflow.com/model-licenses/yolo-nas

### 11. YOLOv9 / YOLOv10 / YOLOv12 — proibidos servir
- **YOLOv9:** GPL-3.0 (código e pesos). **YOLOv10 (THU-MIG):** AGPL-3.0 (deriva do código ultralytics; issue #520 pedindo relicenciamento foi negada). **YOLOv12 (2025):** AGPL-3.0. Nenhum oferece via comercial própria; o caminho seria licença Ultralytics (v10/v12, por derivação) — juridicamente turvo. **Gate de licença do CI (task-055a) deve continuar bloqueando os três.**
- Fontes: https://github.com/THU-MIG/yolov10/blob/main/LICENSE · https://github.com/THU-MIG/yolov10/issues/520 · https://roboflow.com/model-licenses/yolov9

### 12. Ultralytics YOLOv8 / YOLO11 / YOLO26 — só como proposta comercial
- **Licença:** AGPL-3.0 em código, pesos **e modelos treinados com o framework** (posição pública da Ultralytics: o modelo que você treina com o pacote herda AGPL). Enterprise License remove as obrigações.
- **YOLO26 (jan/2026):** n 40.9 → x 57.5 mAP, 1.7–11.8 ms T4, end-to-end sem NMS, treino simplificado, o melhor tooling de treino do mercado (é a razão de ser referência de comparação).
- **Custo da licença:** sem preço público — cotação via formulário; relatos de comunidade citam ~US$5.000/ano como ponto de partida (não oficial, varia por escala de deploy). Detalhe na seção final.
- Fontes: https://docs.ultralytics.com/models/yolo26 · https://www.ultralytics.com/license · https://github.com/orgs/ultralytics/discussions/7440 · https://docs.ultralytics.com/compare/

### 13. RF-DETR — variantes que ainda não usamos
- **Apache-2.0:** Nano 48.4/2.3 ms · Small 53.0/3.5 · Medium 54.7/4.4 · **Large 56.5/6.8** (ICLR 2026; benchmark RF100-VL prova generalização em domínio custom — relevante pro nosso caso "cada cliente treina o seu"). **RF-DETR-Seg** (Nano→2XL, jan/2026) Apache-2.0 — abre instance segmentation para o módulo Qualidade sem custo de licença.
- **⚠ XLarge (58.6) e 2XLarge (60.1) são PML 1.0** (Platform Model License, não-permissiva, via pacote `rfdetr_plus`) → seção comercial.
- Upgrade Nano→Small/Medium é o caminho de menor atrito: mesmo parser, mesmo pipeline de treino já validado no box.
- Fontes: https://github.com/roboflow/rf-detr · https://blog.roboflow.com/rf-detr-segmentation/ · https://rfdetr.roboflow.com/latest/

### 14. Roboflow Universe (bootstrap de dataset, não de modelo servido)
- Universe tem dezenas de datasets/modelos PPE prontos: Hard Hats (19.7k imgs, Roboflow Universe Projects), HardHat & SafetyVest (22k imgs), Hard Hat Universe (8k imgs). Úteis para **pré-anotação e augmentação** do dataset RVB (complementa o pipeline zero-shot Apache do task-098). ⚠ Checar licença individual de cada dataset (variam: CC BY 4.0, MIT, etc.) e a licença do modelo hospedado (muitos são YOLOv8/11 → AGPL, servir pelo Universe não nos serve; baixar o **dataset** e treinar YOLOX/RF-DETR/D-FINE é o uso correto).
- Fontes: https://universe.roboflow.com/browse/manufacturing/ppe · https://universe.roboflow.com/roboflow-universe-projects/hard-hats-fhbh5

---

## Viabilidade DeepStream 7.1 / TensorRT 10.3 (transversal)

- **Família DETR (D-FINE, DEIM, RT-DETRv2/v4, RF-DETR, LW-DETR):** ONNX limpo, **sem NMS** (end-to-end) → saída `[boxes, scores, labels]`; precisa parser custom de `nvinfer` (o mesmo gap RF-DETR/YOLOX que a task-100 identificou — um parser DETR genérico cobre todos). Nenhum roda em DLA (irrelevante: DLA descartado na exp 103-102). NVIDIA documenta o padrão em TAO (Deformable-DETR/DINO) e a RidgeRun publicou RF-DETR+DeepStream em Jetson.
- **Família CNN (RTMDet, DAMO-YOLO, PP-YOLOE+, YOLO26):** precisa NMS (exceto YOLO26, end-to-end) via parser YOLO-like ou plugin EfficientNMS; DLA-compatível (não usamos).
- **INT8:** CNNs quantizam bem (nosso YOLOX-Tiny INT8 >600 inf/s comprova); DETRs quantizam pior (atenção/softmax sensíveis) — esperar ganho menor que o de CNN e calibrar com dataset próprio (PTQ com entropy calibration; D-FINE/DEIM têm relatos de PTQ ok em fp16, INT8 exige QAT para não perder >1 mAP).
- Fontes: https://docs.nvidia.com/tao/tao-toolkit/text/ds_tao/deformable_detr_ds.html · https://www.ridgerun.ai/post/rf-detr-with-deepstream-on-jetson-thor · https://medium.com/@jjn62/d-fine-object-detection-at-30-fps-running-datature-models-on-edge-4383f104518e

---

## Curva acurácia × custo (Orin NX 16GB, estimado onde marcado ~)

| Modelo | mAP COCO | inf/s Orin NX (fp16) | mAP/(ms Orin) — eficiência |
|---|---|---|---|
| YOLOX-Tiny (medido) | 32.8 COCO / **71.2 PPE** | **549** (>600 INT8) | ★ campeão absoluto de throughput |
| DEIMv2-Pico | 38.5 | ~185 | alto |
| D-FINE-N / DEIM-N | 42.8 | ~190 | alto |
| RF-DETR Nano (medido) | 48.4 / **75.6 PPE** | **172** | referência transformer |
| RF-DETR Small | 53.0 | ~115 | alto |
| D-FINE-S (Obj365: 50.7) / DEIM-S 49.0 | 48.5–50.7 | ~115 | alto |
| RT-DETRv4-S | 49.8 | ~110 | alto |
| RF-DETR Medium | 54.7 | ~90 | médio-alto |
| D-FINE-M / DEIM-M | 52.3–52.7 | ~70 | médio |
| RF-DETR Large | 56.5 | ~60 | médio |
| D-FINE-L (Obj365: **57.3**) / RT-DETRv4-L 55.4 | 54.0–57.3 | ~50 | médio |
| RT-DETRv4-X / D-FINE-X (Obj365: **59.3**) / DEIMv2-X 57.8 | 55.8–59.3 | ~30 | baixo, só p/ poucas câmeras |

**Leituras:**
1. Nosso par atual (YOLOX-Tiny + RF-DETR Nano) já ocupa os dois joelhos da curva. O ganho real disponível está em **substituir RF-DETR Nano por RF-DETR Small/Medium** (mesmo pipeline, +4.6–6.3 mAP COCO por ~35–50% do throughput) e em **D-FINE-L/X-Obj365 ou RT-DETRv4-X para o módulo Qualidade** (topo permissivo: 57.0–59.3 mAP).
2. Orçamento agregado: 28 cams @ 5 inf/s = 140 inf/s. YOLOX-Tiny cobre sozinho com 4× folga. RF-DETR Small (~115) cobriria as 16 de EPI com margem apertada; num Orin por site com mix de modelos (EPI leve + Qualidade pesado), a soma precisa caber em ~45% de GPU como na config INT8 vencedora da campanha (40 cams viáveis).
3. Modelos ≥ L só fazem sentido nas 2-4 câmeras de Qualidade: D-FINE-X a ~30 inf/s ainda entrega 6-15 inf/s por câmera — dentro do alvo.

## Recomendação por módulo

| Módulo | Recomendação primária | Alternativa | Racional |
|---|---|---|---|
| **EPI (16 cams, throughput manda)** | Manter **YOLOX-Tiny INT8** (>600 inf/s, 71.2 PPE) | **RF-DETR Small** se +mAP justificar ~115 inf/s; D-FINE-S-Obj365 como 2ª opinião | Nenhum candidato permissivo bate YOLOX em mAP/watt nessa faixa; a troca só se paga se o cliente exigir acurácia |
| **Estacionamento (8 cams, pessoa/veículo)** | **YOLOX-Tiny/S** (classes fáceis, COCO-like) | D-FINE-N (~190 inf/s) se quisermos padronizar família DETR | Pessoa/veículo é o caso onde modelo pequeno + pretrain COCO/Obj365 rende muito |
| **Qualidade (2-4 cams, mAP_small manda)** | **D-FINE-L/X com pretrain Objects365 (57.3/59.3)** via framework DEIM — Apache puro, fine-tune PyTorch | **RT-DETRv4-X (57.0)**, mesma latência, flag jurídica leve (teacher DINOv3); **RF-DETR Large (56.5)** = zero atrito de pipeline; RF-DETR-Seg se precisar máscara | Transformers dominam AP_small; rodar shootout D-FINE-L vs RT-DETRv4-L vs RF-DETR Large **no nosso dataset** medindo AP_small antes de fixar |

**Próximo passo sugerido:** bancada no box real (harness PR #192) com D-FINE-S/L (pesos Obj365), RT-DETRv4-S/X e RF-DETR Small/Large — medir inf/s fp16+INT8 e AP/AP_small no dataset PPE + amostra Qualidade; escrever ADR-0043 com o resultado.

---

## Propostas comerciais explícitas (nada daqui vira recomendação silenciosa)

1. **Ultralytics Enterprise License (YOLOv8/11/26)** — remove AGPL de código, pesos e modelos treinados. Preço não público, cotação por formulário (https://www.ultralytics.com/license); relato de comunidade cita ~US$5.000/ano como base (GitHub discussion #7440 — não oficial; varia por escala/nº de deploys). Compraria: o melhor tooling de treino do mercado e YOLO26 (57.5 mAP a 11.8 ms). **Só considerar se o shootout permissivo falhar no módulo Qualidade** — hoje D-FINE-X-Obj365 (59.3, Apache) supera YOLO26-x (57.5, AGPL) no papel, de graça.
2. **RF-DETR XLarge / 2XLarge (PML 1.0, pacote `rfdetr_plus`)** — 58.6/60.1 mAP. Licença Platform Model License da Roboflow (não-permissiva; termos em https://rfdetr.roboflow.com/latest/). Só relevante para Qualidade se AP_small dos XL justificar contato comercial com a Roboflow.
3. **YOLO-NAS (Deci/NVIDIA)** — pesos não-comerciais; empresa absorvida pela NVIDIA e repo abandonado. **Não há caminho comercial vivo — descartado em definitivo.**
4. **DEIMv2 L/X (cadeia DINOv3)** — não é "compra", é risco: a licença custom DINOv3 da Meta permite uso comercial mas impõe termos próprios (proibição militar, redistribuição com a licença anexa, cadastro de acesso). Antes de servir qualquer peso da cadeia DINOv3 (DEIMv2 L/X; e, em grau menor, RT-DETRv4 destilado), obter parecer e registrar no ADR-0043.

## Fontes principais
- https://github.com/Peterande/D-FINE · https://github.com/Intellindust-AI-Lab/DEIM · https://github.com/Intellindust-AI-Lab/DEIMv2 · https://github.com/RT-DETRs/RT-DETRv4 · https://github.com/lyuwenyu/RT-DETR · https://github.com/Atten4Vis/LW-DETR · https://github.com/roboflow/rf-detr · https://rfdetr.roboflow.com/latest/
- https://github.com/open-mmlab/mmdetection/blob/main/configs/rtmdet/README.md · https://github.com/tinyvision/DAMO-YOLO · https://github.com/PaddlePaddle/PaddleDetection
- https://github.com/Deci-AI/super-gradients/blob/master/YOLONAS.md · https://github.com/THU-MIG/yolov10/blob/main/LICENSE · https://roboflow.com/model-licenses/yolov9
- https://docs.ultralytics.com/models/yolo26 · https://docs.ultralytics.com/compare/ · https://www.ultralytics.com/license · https://github.com/orgs/ultralytics/discussions/7440
- https://ai.meta.com/resources/models-and-libraries/dinov3-license/ · https://github.com/facebookresearch/dinov3/issues/28
- https://docs.nvidia.com/tao/tao-toolkit/text/ds_tao/deformable_detr_ds.html · https://www.ridgerun.ai/post/rf-detr-with-deepstream-on-jetson-thor · https://blog.roboflow.com/rf-detr-segmentation/ · https://universe.roboflow.com/browse/manufacturing/ppe
