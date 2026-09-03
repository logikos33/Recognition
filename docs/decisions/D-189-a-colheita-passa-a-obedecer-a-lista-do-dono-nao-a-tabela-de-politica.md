# D-189 · A colheita passa a obedecer a lista do dono, não a tabela de política

**Seção:** Rodada 02/09 — colher os frames das câmeras que importam · **Status:** ✅ vigente · **Data:** 2026-09-02

## O pedido

> "as imagens dos frames captados grande maioria são fora da fábrica, tipo estacionamentos, entradas
> etc, precisamos priorizar as entradas da expedição onde vai ter maior reconhecimento de uso de
> protetor auricular, corredor lateral usinagem, entrada preparação, entrada usinagem madeira,
> entrada expedição 2 — essas câmeras precisam passar pela validação, talvez sejam as que mais vão
> gerar reconhecimento."

## O que a colheita de 02/09 tinha entregue (medido)

`public.training_frames` ⋈ `public.cameras`, tenant RVB, `created_at > now() - interval '12 hours'`:

| câmera | canal | frames | prioritária? |
|---|---|---|---|
| Entrada Usinagem Madeira 2 | 4 | 166 | ✅ |
| Espaço de convivência | 10 | 113 | ❌ |
| Entrada WC Usinagem Papelão | 11 | 82 | ❌ |
| Entrada Expedição | 1 | 39 | ✅ |
| Entrada Preparação | 7 | 17 | ✅ |
| Entrada Usinagem Madeira 01 | 8 | 15 | ✅ |
| Entrada Expedição 02 | 21 | 8 | ✅ |
| **Corredor Lateral usinagem Madeira** | **2** | **0** | ✅ 🔴 |

Bate exatamente com o contador do próprio minerador
(`~/colheita-full-0902/state/recognition/replay_miner_state.json`):
`{"ch1":39,"ch4":166,"ch10":113,"ch11":82,"ch8":15,"ch7":17,"ch21":8}` — soma 440.

## Duas causas, ambas medidas — nenhuma é "o DVR não tinha gravação"

**1. O corredor lateral (ch2) nunca foi pedido.** O cabeçalho da run anterior
(`~/colheita-full-0902/escala.log`) diz `canais=[1, 4, 7, 8, 11, 21, 10]`. O canal 2 **está** no
`channel_map` da nuvem (18 canais). Zero não foi resultado: foi ausência de pergunta.

Recon de 12 janelas em 02/09 09:00–11:00 mostrou que ele é o canal **mais movimentado de todos**:
144 frames escaneados, **136 com pessoa (94%)** — contra 52% de média da run anterior. A câmera que
ficou com zero era a de maior rendimento.

**2. As entradas caíam no teto de 1 frame por janela.** `policy_for_channel()` devolve `REDUCED`
(`per_window_cap=1`) para qualquer canal não listado em `_FULL_CHANNELS = {1,4,11,12,19,23,28}`.
Os canais 2, 7 e 21 — corredor lateral, preparação, expedição 02 — não estão listados. Por isso
ch7 rendeu 17 e ch21 rendeu 8: não por falta de gente, por teto.

## Decisão

**A tabela de política compartilhada não muda.** Ela é decisão do Vitor de 15/08 e governa a
campanha contínua da produção. Quem sobe os canais prioritários é o **driver pontual**
(`scripts/ops/colheita_full.py`, `PRIORIDADE=<canais>`), que troca `policy_for_channel` **dentro do
próprio processo** e some quando o processo morre.

A alternativa seria manter o teto e compensar com 4× mais janelas contra o gravador para o mesmo
número de frames. **Mais requisição no DVR é exatamente o que não se quer** (D-160, anti-lockout).
Levantar o teto é o caminho de MENOS conversa com o gravador.

**O canal 8 fica em `CEILING`, de propósito.** Seu teto de campanha (`_CH8_CAMPAIGN_MAX_CROPS = 60`)
é decisão de anti-concentração do Vitor — "já tem 194 frames, 82% Botas". O contador persistido já
marcava 15, então o teto para esta campanha em 60, que é justamente o piso da meta pedida. Honra as
duas coisas sem escolher entre elas.

## Limite honesto

- O dedup **não** foi afrouxado. Ele derrubou 118 de 136 frames-com-pessoa no recon (87%, e o modo
  gritou o aviso que foi feito para gritar). Isso é comportamento correto: 12 frames de um clipe de
  6 s numa câmera fixa são near-duplicates de verdade e não ensinam nada. O rendimento real é
  ~1,5 frame **novo** por janela; a alavanca é número de janelas, não limiar.
- `PRIORIDADE` promove a `FULL`, que não tem teto nenhum. Numa câmera muito movimentada isso pode
  passar da meta. Aqui a contenção é o escopo de dias, não o código.
