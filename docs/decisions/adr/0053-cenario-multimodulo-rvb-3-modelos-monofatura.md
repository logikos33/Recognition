# ADR-0053 — Cenário RVB multi-módulo: 3 modelos simultâneos no mesmo Jetson + integração monofatura

**Status:** Proposta · **Data:** 2026-07-17 · **Autores:** Vitor Emanuel (Logikos) + Claude Code
**Relaciona:** ADR-0043 (AGPL-zero + addendum de licença) · ADR-0044 (detector plugável) ·
ADR-0045 (evidência recorder-first) · task-045 (modelo por câmera) · tasks 107–112
**Nota de numeração:** o prompt de origem referenciava este ADR como "0048", mas o slot 0048 já estava
ocupado (`0048-anotacao-self-hosted-ferramenta-propria.md`); registrado como 0053 (próximo livre).

## Contexto

A RVB Isolantes opera **28 câmeras num único Jetson Orin NX Super 16GB** e quer **3 módulos
simultâneos**, cada um com seu(s) modelo(s):

| Grupo | Câmeras | Modelo alvo | Observação |
|---|---|---|---|
| Qualidade principal | 2×4MP | RF-DETR-M/S ou YOLOX-M, **alta-res POR ROI** | mAP_small é o juiz; nunca o frame 4MP inteiro |
| Qualidade auxiliar | 2×2MP | YOLOX-Nano/Tiny + NvDCF | rastrear a peça + cronometrar etapa |
| Estacionamento | 8×2MP | YOLOX-Tiny/Nano | pessoa/veículo, linha de cruzamento, aglomeração |
| EPI | 16×2MP | YOLOX-S/Tiny INT8 | já validado (campanha 2026-07-17) |

A campanha de escala (docs/edge/CAMPANHA_ESCALA_2026-07-17.md) validou o box com **UM** modelo
(YOLOX-Tiny INT8: 40 cams @ GPU 45%). O custo de **3 engines simultâneas + 2 streams 4MP em
alta-res por ROI** nunca foi medido — é o ponto crítico deste cenário.

Além da visão, a Qualidade integra com o ERP do cliente (**monofatura**): a peça é "bipada"
(ID) na entrada da linha, e ao fim de cada etapa o sistema devolve **evidência (imagem) +
resultado por atributo + tempo de etapa** associados ao ID. O contrato real do cliente ainda
não existe → o acoplamento tem que ser **plugável**.

## Decisão

1. **Roteamento por câmera usa a config existente** (`active_module` + `model_<módulo>_id`,
   task-045). NÃO se cria mecanismo novo de roteamento.
2. **No edge, cada grupo de câmeras roda numa instância nvinfer própria** (na prática desta fase:
   processos DeepStream separados por grupo, mesma GPU), com a config ótima da campanha
   (INT8/fp16 + sub-batch + interval + NvDCF, headless em produção).
3. **Qualidade principal infere em alta resolução POR ROI** (nvdspreprocess com ROIs nos pontos
   de atenção), nunca o frame 4MP inteiro reescalado.
4. **Monofatura**: inbound = endpoint "peça bipada" que abre sessão de inspeção idempotente e
   tenant-scoped; outbound = **adaptador plugável** (contrato real do cliente pendente) que
   entrega evidência + resultado por atributo + tempo por etapa.
5. **Trava de licença (addendum ADR-0043) vale para TODA exploração de modelos**: candidato só
   entra na curva acurácia×custo com licença identificada; permissivo (Apache/MIT/BSD) é o
   padrão; licença comercial só como proposta explícita ao Vitor com custo; AGPL sem licença
   comercial comprada = proibido servir (license-gate).
6. **Métricas de treino por modelo** (precision, recall, mAP@0.5:0.95, mAP_small/medium/large,
   losses, LR por época) são persistidas e alimentam o dashboard do Recognition (task-112) —
   observabilidade de modelos e telemetria de edge ao vivo dentro da plataforma, não HTML solto.

## Consequências

- Tasks 107–112 executam o cenário (modelos por grupo, monofatura, qualidade multi-atributo,
  estacionamento, stress 3-módulos, dashboard integrado).
- O stress combinado define o **ponto de saturação** do Orin NX com os 3 módulos e vira o
  número de venda/expansão (upsell) do cenário RVB.
- Telemetria JSONL passa a ser **etiquetada por módulo** (extensão do sampler da campanha) e o
  coletor task-099/100 ganha os campos que faltam (fan, rails, label de fase).
- Inputs do cliente pendentes (pontos de atenção da peça; contrato monofatura) ficam plugáveis
  e NÃO travam o stress — simulados no teste.
