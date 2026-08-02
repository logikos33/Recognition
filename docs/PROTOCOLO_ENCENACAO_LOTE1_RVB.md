# Protocolo de encenação — Lote 1, câmera 1 (RVB / módulo EPI)

> **Não é "encher o pool". É um experimento com pergunta.**
> A pergunta que o lote 1 precisa responder: **em quantos pixels de cabeça cada item de EPI vira anotável?**
> Óculos já foi respondido pela amostra do playback (~45 px = anotável). **Protetor auricular está em aberto** —
> ninguém na amostra estava usando. Essa é a classe de maior risco do módulo.

## Por que encenar em vez de esperar

Fim de expediente rendeu **8 frames em 40 min**, concentrados em 2 minutos — não é taxa, é chegada esporádica.
15 minutos de passagem deliberada rendem mais **variedade de pose** que horas de espera, e cobrem justamente a
postura curvada, onde o detector era fraco.

## ⚠️ Pré-requisito — confirmar antes de começar

**O endpoint `POST /edge/frames` já aceita bbox e confiança?**

- **Se NÃO:** encene mesmo assim, mas **limite ao lote 1 (50 frames)**. Frame coletado agora nasce sem
  `model_confidence` (afunda na fila de active learning, R3) e sem posição no frame original (insumo da regra por
  zona). Não expandir para 200/500 antes do endpoint.
- **Se SIM:** pode seguir para a expansão gradual normalmente.

## 🔴 Cota — ler antes do roteiro

Com a config original (`burst=5`, `cooldown=30s`), 50 frames se esgotam em **10 disparos**: a rodada A comeria a
cota inteira e a **rodada B — o cordão, a pergunta em aberto — nunca seria capturada**. 20 minutos de encenação e a
pergunta continuaria sem resposta.

Config do experimento (backup em `.env.pre-encenacao`):

```
COLLECTOR_BURST_COUNT=1                  # rajada não serve: quem varia a pose é a pessoa
COLLECTOR_COOLDOWN_S=2                   # 30s cegaria a câmera entre poses
COLLECTOR_TARGET_FRAMES_PER_CAMERA=17    # por RODADA, não pelo lote
```

O contador é **em memória e zera no restart** — por isso a cota é por rodada: `restart` antes de cada uma dá
17+17+17 ≈ 51, com cada rodada garantindo a sua fatia.

## ⚠️ Não pare — mova devagar

O gatilho tem dois estágios: **frame-diff → detector de pessoa**. Se a pessoa **para de verdade** para segurar a
pose, o frame-diff cai abaixo do limiar e o coletor **não captura nada** — sem erro, sem log.

**Instrução para quem está na frente da câmera:** chegar na pose e **ficar em movimento leve** — deslocar o peso,
girar a cabeça devagar, meio passo à frente e atrás. Queremos a *pose*, não a *imobilidade*.

Vale sobretudo no **perfil** (a pose que decide a concha): girar lentamente de frente para perfil, e continuar
girando, rende muito mais frame útil do que travar de lado.

## Divisão de papéis

A pessoa na frente da câmera **não precisa de SSH**. Quem opera o box faz o `restart` remotamente e **anota o
horário**; quem está em Blumenau só caminha, coordenado por telefone. Assim os horários saem do relógio do servidor,
não da memória de ninguém.

**Confirmar antes de marcar:** a pessoa precisa levar **os dois tipos de protetor** (concha *e* plug com cordão).
Só com concha, a rodada B não acontece e a pergunta principal continua aberta.

## O roteiro (≈12 min de encenação)

Uma pessoa atravessa o campo da câmera 1. **Três distâncias** × **quatro posturas** × **três condições de EPI**.

Antes de **cada** rodada, no box — o `date` é o horário de início, **anote**:

```bash
ssh pandora@<host> 'systemctl --user restart edge-frame-collector; date +%H:%M:%S'
```

Ritmo: ~7 s por pose (em movimento leve). O coletor pega um frame a cada ~5 s (poll 3 s + cooldown 2 s).
12 poses ≈ **4 min por rodada**.

### Distâncias
Marcar 3 pontos no chão: **perto** · **meio** · **longe** (o mais distante em que a pessoa ainda aparece inteira).
O objetivo é varrer a faixa de pixels — é isso que produz a curva "tamanho da cabeça × item legível".

### Posturas (em cada distância)
1. **Em pé, de frente** — baseline
2. **De perfil** ← *o mais importante para o protetor auricular:* a orelha só aparece de lado
3. **Curvado / agachado** — postura real de trabalho, onde o detector era fraco
4. **De costas**

### Condições de EPI (a parte que responde a pergunta)
| Rodada | O que a pessoa usa | O que estamos medindo |
|---|---|---|
| A | **concha / abafador** + óculos | a concha é anotável? em que distância deixa de ser? |
| B | **plug com cordão** + óculos | o **cordão** é visível? (hipótese: improvável) |
| C | **sem nenhum EPI** | classe de ausência — insumo da regra, e negativo real |

> **Rodada B é a que decide o desenho da classe.** Se o cordão não aparecer em nenhuma distância, o plug é
> indetectável neste enquadramento e isso precisa virar decisão explícita — não uma classe que nunca converge.

### Enquadramento
Se der, incluir **2 pessoas juntas** em uma passagem (oclusão parcial) — é o caso real de corredor e é onde o
recorte por bbox costuma quebrar.

## Registro (fazer na hora, não depois)

Anotar em papel/celular: **horário de início e fim de cada rodada (A/B/C)**. Sem isso não dá para cruzar frame com
condição de EPI depois, e o lote perde metade do valor — vira "50 fotos de gente".

## Critério de aceite do lote 1

O lote está bom quando dá para responder, **com número**:

1. Óculos vira anotável a partir de ~____ px de cabeça *(hipótese atual: 45)*
2. Concha/abafador vira anotável a partir de ~____ px de cabeça *(hipótese: ~45, não verificado)*
3. Cordão do plug: anotável em alguma distância? **sim / não** *(hipótese: não)*
4. % de frames úteis pelo critério de cabeça mínima — **por classe**, não global (R5 do flywheel)

Se o item 2 ou 3 der "não em nenhuma distância", **a conclusão é sobre a câmera, não sobre o modelo**: reposicionar,
aproximar ou dedicar uma câmera ao enquadramento de cabeça. Melhor descobrir com 50 frames que com 500.

## Depois do lote 1 — o gate

Não expandir automaticamente. Expandir **50 → 200 → 500 → 1000** só com % de útil aceitável no lote anterior,
medido **por classe**. E não ligar a pré-anotação antes de ~100–150 exemplos por classe (R2 — modelo fraco propondo
caixa ruim é pior que tela em branco).

## 🔴 Último passo obrigatório — reverter a config

```bash
cp ~/.config/recognition/edge-sync-agent.env.pre-encenacao ~/.config/recognition/edge-sync-agent.env
systemctl --user restart edge-frame-collector
```

**Se esquecer, a coleta contínua para em 17 frames por restart e fica parada** — sem erro, sem log. Seria o
terceiro caso da mesma família (limiar `8.0` contra ruído 0.39; `2.0` numa variável que virou fração 0–1). Confirmar
depois do revert que frames voltaram a chegar, não só que o arquivo mudou.

## Fora de escopo aqui

Anotação, treino, pré-anotação, expansão de lote. O lote 1 termina quando as 4 perguntas acima têm número.
