# Plano dos 500 — dimensionamento do dataset EPI RVB (Onda 2 implementa; nada de propagação implementada nesta rodada)

> Rodada 06/08. Insumos: triagem dos 679 (régua D-65), diagnóstico da coleta (D-68),
> inventário do R2 e das entradas de front (abaixo). Decisões pendentes do Vitor marcadas com 🔴.

## 1 · A cadeia

```
coletar em alta → ANOTAR 50 (humano) → PROPAGAR p/ ~500 (SAM+DINO) → APROVAR (humano) → dataset → treino
```

Esta rodada entregou até "50 prontos para anotar". Este documento dimensiona o resto.

## 2 · De onde saem os 500 — três fontes, somadas

| Fonte | Estado | Rendimento esperado |
|---|---|---|
| **A. Os 679 existentes** (682 no R2 já contando os 3 da coleta nova; câmera 1: 615 frames 704×480 + 67 recortes de pessoa do desfecho C) | **MEDIDO** (régua a conf 0.10, 06/08): **170 anotáveis** (107 substream + 63 recortes), 237 duvidosos (80–140 px), 43 descartar, 232 sem pessoa. Mediana de altura 128,8 px — o substream vivia na borda do corte. **Lista dos 50 pronta** (dedup perceptual, estratificada por data; 170 disponíveis, sem shortfall) | **50 hoje, ~170 no total** (+237 duvidosos p/ decisão do Vitor) |
| **B. Coleta para frente religada** (06/08 20:13: 8 câmeras, mainstream 1080p, meta 500/câmera, gate de pessoa) | **VIVA** — uploads multi-câmera confirmados no 1º minuto (pessoas de 194–490 px). ⚠️ O desfecho C sobe **recorte de pessoa** (margem p/ cabeça), não o frame inteiro — coerente com D-62 (1º modelo = curta distância/cabeça); registrar a decisão de treinar em recorte × frame inteiro antes do dataset v1 | ~dezenas/dia por câmera com gente em cena; medir em 48h |
| **C. Colheita retroativa do NVR** (~59 dias gravados, provavelmente 1080p) | código existe (playback RTSP/ONVIF Replay); gates: 🔴 janela + 🔴 LGPD | centenas em horas de extração, alta variedade de datas/luz |

**Leitura honesta:** com B viva em 1080p e 8 câmeras, **C deixou de ser pré-requisito de VOLUME**
— vira acelerador de VARIEDADE (datas, turnos, condições de luz que a coleta para frente só
alcançaria em semanas). A decisão LGPD pode ser tomada sem pressa de prazo.

**Achados da triagem que valem registro à parte:**
- 1 câmera com **obstrução física confirmada** (tela metálica entre lente e cena) — resolução
  não conserta; é informação de instalação (lista completa em
  `triage-679-work/resultado/obstruction_candidates.json`, maioria falso-positivo a confirmar).
- Reconciliação R2×banco: **100% dos objetos baixam** (682/682, zero falha) — nenhum frame
  órfão; o "frame não encontrado" era só o bug de tenant (#313), nunca objeto faltando.
- Não existe classificador de EPI para pré-marcar com/sem capacete — variedade com/sem EPI
  da lista dos 50 é julgamento humano na hora de anotar (o relatório avisa).

## 3 · Compatibilidade semente × pool (6.2)

Critério proposto: a semente (50) e o pool (500) devem se sobrepor em **câmera e faixa de
distância**. Regra prática: propagar somente para frames da MESMA câmera da semente ou de
câmeras com distribuição de altura-de-pessoa equivalente (bucket ≥140 px); frames "duvidosos"
(80–140 px) só entram no pool se a semente tiver exemplos naquela faixa. Nota técnica: DINOv2
redimensiona a entrada — semente 480p com pool 1080p deve funcionar, **validar com 5 frames
antes do lote** (não assumir).

## 4 · Procedência (6.3) — gate implementado

D-39: `humana`/`auto_aprovada` entram no treino; o resto não. A migration 095 tem 2 valores
(`manual`/`pre_annotation` + `reviewed_by`); a semântica equivalente já cobre:
`manual` = humana; `pre_annotation` com `reviewed_by` = auto_aprovada. **O gate no construtor
de dataset (versioning_v2) está em PR nesta rodada** — pré-anotação não revisada não entra
no treino. Estender o CHECK para os 4 valores nominais do D-39 fica para a Onda 2 (migration
aditiva), sem bloquear nada.

## 5 · Onde roda a propagação (6.4)

D-38: GPU sob demanda, mesma conta do treino (1 suboperador). 🔴 **Bloqueio contratual novo
(D-72): o dicionário nomeia RunPod, o código aponta Vast.ai** — confirmar o provedor real
antes de mandar frame de trabalhador para lá, e com a flag
`training_third_party_cloud_enabled` consciente. Pesos já no R2 (`models/groundingdino_swint_ogc.pth`
694 MB, `models/sam_vit_b_01ec64.pth` 375 MB — Apache 2.0, verificar sha256 no uso):
o serviço `pre-annotation` já sabe baixá-los de lá (zero download novo).

## 6 · As três entradas de front (6.6) — o que existe e o que custa

| # | Recurso | Front | API | Schema | Esforço estimado |
|---|---|---|---|---|---|
| A | **Refino de caixa (SAM)** — clica e a caixa encaixa | ❌ (só desenho manual; `PreAnnotationControls.tsx` é órfão) | ❌ (SAM só roda dentro do batch DINO; não há endpoint caixa-humana→máscara) | parcial (`pre_annotations` jsonb) | **1,5–2,5 dias**: endpoint box→mask no serviço pre-annotation + proxy flag-gated + interação no anotador. Runtime: SAM ViT-B em CPU ≈ 2–6 s/clique (ok p/ 50; interativo ideal exige GPU) |
| B | **Grounding por texto** — digita "capacete", propõe caixas | ❌ (sem campo de texto) | parcial (`/training/frames/<id>/pre-annotate` com prompt FIXO de `module_classes.dino_prompt`, flag OFF) | ✅ (migration 020) | **0,5–1 dia** para plugar texto livre. ⚠️ MAS é exatamente a tarefa que decepcionou na ADR-0031 (zero-shot de EPI) — esforço baixo, expectativa de qualidade baixa |
| C | **Propagação em lote (DINOv2)** — ache parecidos com a semente | ❌ | ❌ (DINOv2 não existe no código; `prioritize` é incerteza, não similaridade) | ❌ (sem embeddings de frame) | **3–5 dias**: extrator de embeddings + storage (pgvector) + job em lote + **fila de aprovação** (ver §7). É a Onda 2 |

🔴 **Decisão do Vitor (A/B antes das 50?):** A ataca diretamente o custo da anotação manual
(50 caixas com SAM encaixando ≈ 1/3 do tempo). B é barato mas foi o que falhou em maio.
Recomendação técnica: **A sim (se a sentada de anotação não for imediata), B não** — e nada
disso bloqueia anotar à mão hoje.

## 7 · Tela de aprovação (6.5)

Não existe fila de aprovação em lote. O que há: badge/validação por frame no fluxo atual.
Aprovar ~450 propostas exige: fila ordenada por confiança, atalhos de teclado
(aceita/rejeita/ajusta), lote por classe. Estimativa: **2–3 dias** de front + endpoints de
lote (aceite já existe por frame: `accept-suggestions`). Entra na Onda 2 junto com C.

## 8 · Desalinhamento treino × produção (3.4)

Inferência de produção roda no stream configurado por câmera (`cameras.subtype`, hoje
default substream em produção DeepStream; a coleta agora é 1080p). **Anotar em alta continua
certo** (coordenada é normalizada; caixa precisa sobrevive ao downscale). Mitigação padrão na
Onda 2 de treino: augmentation simulando a entrada real (downscale/blur/compressão).
⚠️ Correlato: D-66 (preproc RGB/255 zerando YOLOX stock) está em correção nesta rodada —
qualquer avaliação de modelo servida antes desse fix é suspeita.

## 9 · Cronograma honesto até o dataset v1

1. **Hoje**: Vitor mergeia #313 → anota as 50 da lista da triagem (galeria já filtrada por veredito).
2. **+48 h**: medir rendimento real da coleta B (frames/dia por câmera) e refazer a conta do gap.
3. **Decisões 🔴**: LGPD/C (colheita), provedor GPU (RunPod×Vast.ai), A antes das 50.
4. **Onda 2**: implementar C + fila de aprovação; propagar; aprovar; montar dataset v1
   (composição por câmera VISÍVEL — sem dataset separado por câmera, D-36/regra da rodada).
