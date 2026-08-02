# Runbook — Encenação do lote 1 (câmera 1, RVB / módulo EPI)

> **Não é "encher o pool". É um experimento com uma pergunta:**
> **em quantos pixels de cabeça cada item de EPI vira anotável?**

Óculos já foi respondido pela amostra do playback: **~45 px de cabeça = anotável**
(armação e lentes visíveis sem ambiguidade). **Protetor auricular está em aberto** —
ninguém na amostra estava usando. É a classe de maior risco do módulo.

---

## Pré-requisito — checar antes de marcar

**`POST /api/v1/edge/frames` já aceita bbox e confiança?**

- **NÃO** (situação em 2026-08-02): encenar mesmo assim, mas **parar no lote 1**.
  O frame nasce sem `model_confidence` (afunda na fila de active learning) e sem
  posição no frame original. **Não expandir para 200/500 antes do endpoint.**
- **SIM**: seguir para a expansão gradual normal.

As colunas `pre_annotations` e `model_confidence` **já existem** em
`public.training_frames` — falta só o contrato do endpoint.

---

## Por que a config muda para o experimento

Três números medidos em campo que determinam a config:

| medição | valor |
|---|---|
| ruído da cena vazia (poll 3 s, n=11) | **0,0000** |
| pessoa **andando** (n=15) | 0,0195 – 0,06 · mediana **0,0266** |
| custo do detector de pessoa | 118 ms → **3,9%** de ocupação com poll 3 s |

Duas consequências:

**1. O limiar de movimento padrão (0,020) fica no PISO da faixa da pessoa,
não acima do ruído.** Quem segura pose cai abaixo e não é capturado — sem erro,
sem log. Para a encenação usamos **0,003**: o ruído real é zero, e o gate de
verdade é o detector de pessoa (precisão 95%), que custa 3,9%.

**2. A cota se esgota antes das rodadas acabarem.** Com `burst=5`/`cooldown=30s`,
50 frames = **10 disparos**, e o roteiro tem **36 combinações**. A rodada A comeria
tudo e a rodada B — o cordão, a pergunta em aberto — nunca aconteceria.

Config do experimento (backup automático em `.env.pre-encenacao`):

```
COLLECTOR_BURST_COUNT=1                  # rajada não serve: quem varia a pose é a pessoa
COLLECTOR_COOLDOWN_S=2                   # 30s cegaria a câmera entre poses
COLLECTOR_TARGET_FRAMES_PER_CAMERA=17    # por RODADA, não pelo lote
COLLECTOR_MOTION_THRESHOLD=0.003         # ruído real é 0; o gate é o detector
```

O contador de frames é **em memória e zera no restart** — por isso a cota é por
rodada: `restart` antes de cada uma dá 17+17+17 ≈ 51.

---

## Divisão de papéis

Quem está na frente da câmera **não precisa de SSH**. Quem opera o box faz o
`restart` remotamente e **anota o horário**; quem está no site só caminha,
coordenado por telefone. Os horários saem do relógio do servidor.

**Confirmar antes de marcar:** a pessoa precisa levar **os dois tipos de protetor**
(concha *e* plug com cordão). Só com concha, a rodada B não acontece.

---

## Roteiro (~12 min)

Antes de **cada** rodada — o `date` é o início, **anote**:

```bash
ssh pandora@<host> 'systemctl --user restart edge-frame-collector; date +%H:%M:%S'
```

Ritmo: ~7 s por pose. O coletor pega um frame a cada ~5 s (poll 3 s + cooldown 2 s).
12 poses ≈ 4 min por rodada.

**Distâncias** (3 marcas no chão): perto · meio · **longe** (o mais distante em que a
pessoa ainda aparece inteira). É a varredura de distâncias que produz a curva
"tamanho da cabeça × item legível".

**Posturas**, em cada distância:
1. Em pé, de frente — baseline
2. **De perfil** — decide o protetor auricular: a orelha só aparece de lado
3. Curvado / agachado — postura real de trabalho, onde o detector era fraco
4. De costas

**Rodadas:**

| rodada | EPI | o que mede |
|---|---|---|
| A | concha/abafador + óculos | a concha é anotável? até que distância? |
| B | plug com cordão + óculos | o **cordão** aparece? (hipótese: não) |
| C | sem EPI nenhum | classe de ausência / negativo real |

> **B decide o desenho da classe.** Se o cordão não aparecer em nenhuma distância,
> o plug é indetectável neste enquadramento — e isso vira decisão explícita, não uma
> classe que nunca converge.

Se der, uma passagem com **2 pessoas juntas** (oclusão parcial) — é o caso real de
corredor e onde o recorte por bbox costuma quebrar.

**Movimento leve:** o gatilho tem dois estágios (frame-diff → detector). Mesmo com o
limiar em 0,003, chegar na pose e continuar em movimento leve (deslocar o peso, girar
a cabeça devagar) rende mais frame que travar imóvel. Vale sobretudo no perfil:
**girar lentamente** de frente para perfil rende mais que parar de lado.

---

## Acompanhar em tempo real

```bash
railway run --service Postgres -- psql "$DATABASE_PUBLIC_URL" -c \
  "SELECT to_char(captured_at AT TIME ZONE 'America/Sao_Paulo','HH24:MI:SS') h,
          width||'x'||height dim
   FROM public.training_frames
   WHERE source='nvr' AND captured_at > now() - interval '30 min' ORDER BY 1;"
```

---

## Critério de aceite

O lote 1 termina quando estas quatro têm **número**:

1. Óculos vira anotável a partir de ~____ px de cabeça *(hipótese: 45)*
2. Concha/abafador a partir de ~____ px *(hipótese: ~45, não verificado)*
3. Cordão do plug: anotável em alguma distância? **sim / não** *(hipótese: não)*
4. % de frames úteis **por classe**, não global

Se 2 ou 3 der "não em nenhuma distância", **a conclusão é sobre a CÂMERA, não sobre o
modelo**: reposicionar, aproximar, ou dedicar uma câmera ao enquadramento de cabeça.
Melhor descobrir com 50 frames que com 500.

Análise: `scripts/analisar_lote1.py` (baixa os frames, estima px de cabeça, separa por
rodada). Ele mede o pixel; **quem julga é humano**. Ressalva: a estimativa cabeça =
altura/7 vale para pessoa em pé — para **agachado ela subestima**, trate como piso.

---

## 🔴 Último passo — reverter

```bash
cp ~/.config/recognition/edge-sync-agent.env.pre-encenacao \
   ~/.config/recognition/edge-sync-agent.env
systemctl --user restart edge-frame-collector
```

**Confirmar que frames voltaram a chegar**, não só que o arquivo mudou.

Se esquecer, a coleta para em 17 frames por restart — em silêncio. Seria o **quarto**
caso da mesma família (limiar 8.0 contra ruído 8.19; limiar 2.0 numa métrica que virou
fração 0–1; limiar 0.020 no piso da faixa da pessoa). Por isso o coletor agora
**ecoa a config efetiva no boot** e avisa quando ela é auto-sabotadora — ver
`log_configuracao_efetiva` em `app/collector/collector_loop.py`. Procure no log:

```
collector_config alvo=... burst=... cooldown=... limiar_movimento=...
```

---

## Fora de escopo

Anotação, treino, pré-anotação, expansão de lote. Não ligar pré-anotação antes de
~100–150 exemplos por classe: modelo fraco propondo caixa ruim é pior que tela em branco.
