# Flywheel de anotação — do frame ao modelo de EPI (RVB)

> Desenho do loop humano-no-circuito. Cada volta o anotador trabalha **menos** e o modelo fica **melhor**.
> Atravessa edge + nuvem + front → vira prompts por sessão, respeitando a divisão de diretórios.

## A escada (4 estágios)

```
[0] GATILHO          pessoa detectada no edge → frame capturado → R2 + training_frames (source='nvr')
                     (a bbox da pessoa vai junto = semente de pré-anotação)
        ↓
[1] ANOTAÇÃO MANUAL  humano desenha protetor auricular · luvas · óculos
                     → forma o DATASET SEMENTE
        ↓
[2] PRÉ-ANOTAÇÃO     com semente suficiente, o modelo PROPÕE as caixas nos frames novos
        ↓
[3] VALIDAÇÃO        humano ACEITA / CORRIGE / REJEITA (não desenha do zero) ← ganho de velocidade
        ↓
[4] TREINO           só o VALIDADO vira dataset (COCO) → RunPod → modelo melhor
                     → propostas melhores → volta ao [2], loop apertando
```

## Regras que sustentam o loop (não são detalhe)

**R1 — Proveniência é obrigatória.** Toda anotação precisa carregar sua origem: `humana` · `sugerida pelo modelo` ·
`sugerida e validada por humano`. **Só `humana` e `validada` entram no treino.** Treinar em sugestão não validada é
o modelo aprendendo com o próprio erro (amplificação/colapso). *A migration `095_annotations_provenance.sql` já
existe — usar, não reinventar.*

**R2 — Não pré-anotar cedo demais.** Modelo fraco propondo caixa ruim é **pior que tela em branco**: o humano gasta
mais tempo corrigindo do que desenharia. Só ligar o estágio [2] com semente mínima — referência: **~100–150
exemplos por classe**. Antes disso, anotação manual pura.

**R3 — Priorizar o que o modelo NÃO sabe.** A fila deve trazer primeiro os frames de **baixa confiança** (é onde o
humano ensina mais). A fila de active learning já ordena por `model_confidence ASC` — e agora os frames de câmera
passam a **ter** score (vindo do detector de pessoa), então param de afundar no fim da fila.

**R4 — Guarda contra viés de confirmação.** Se o humano só clica "aceitar", o modelo reforça os próprios erros.
Amostrar periodicamente frames **sem pré-anotação** (às cegas) pra medir qualidade real, não a percebida.

**R5 — Métrica é classe, não total.** O gargalo é a classe rara. Acompanhar **exemplos por classe** (protetor
auricular / luvas / óculos), não o número total de frames.

## O que já existe × o que falta

| Peça | Estado |
|---|---|
| Gatilho por pessoa no edge | 🔨 em construção (prompt do coletor) |
| `training_frames` com `source`, `r2_key`, `camera_id`, `model_confidence` | ✅ existe |
| Proveniência de anotação (migration 095) | ✅ existe |
| UI de anotação manual (`AnnotationInterface`, `/epi/training`) | ✅ existe |
| Serviço de pré-anotação + `accept_suggestions` + `PreAnnotationControls` | ⚠️ existe, **flag OFF** |
| Fila de active learning (`model_confidence ASC`) | ✅ existe |
| Dataset COCO → treino (RunPod) → registry | ✅ existe |
| **Frames de câmera aparecerem na UI de anotação** | ❌ **BLOQUEADO** (ver abaixo) |

## 🔴 Bloqueio nº 1 — o pool está invisível
Frames com `source='nvr'` têm `video_id NULL`; a galeria cai no caminho legado (`get_by_user_paginated`) que faz
`JOIN training_videos` → **eles nunca aparecem**. Sem esse fix, todo o resto da escada não começa: coleta-se um pool
fantasma. **É o primeiro item a resolver** (`services/api/**` + front = sessão da API).

## Ordem sugerida
1. **Destravar a visibilidade do pool** (bloqueio nº 1).
2. Gatilho por pessoa no edge (em curso) → pool enche com frame **útil**.
3. **Anotação manual** até a semente (~100–150/classe) — aqui entram os critérios do Paulo (o que é violação, zonas).
4. **Ligar a pré-anotação** (flag) → estágio [2]/[3].
5. Treino no RunPod → medir → repetir.

> ⚠️ **Pendência que afeta a classe:** confirmar se o **protetor auricular** da RVB é **concha/abafador** (detectável)
> ou **plug de inserção** (praticamente indetectável por câmera). Isso decide se a classe é treinável.
