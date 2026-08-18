# D-175 · Mineração é SERVIÇO com cadência, não campanha

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **Data:** 2026-08-18

A janela do DVR **se renova inteira a cada 4 dias** (D-172). Campanha mensal mineraria 4 dias e
encontraria vazio nos outros 26. O desenho:

| | |
|---|---|
| **Cadência** | **2 dias** — metade da janela. Margem para uma falha e um retry **sem perder nada**. |
| **Onde roda** | **Orin, systemd --user timer** (`edge-replay-miner.timer`). ⛔ Não pelo beat da nuvem: mineração fala com o DVR na LAN, e o beat nunca foi provisionado. |
| **Horário** | 03:30 — madrugada, faixa que o plano **não** minera, então não disputa o DVR com turno nenhum. |
| **Janela** | 3 dias por ciclo (margem dentro da retenção de 4). Pedir além da retenção **avisa** em vez de voltar vazio calado. |

**Estratificação** (`SHIFTS_RVB`, ladrilha 05:00→24:00 sem buraco):

| faixa | intervalo | janelas/dia/canal |
|---|---|---|
| **dia** 05–17h | 20 min (cheio) | 36 |
| **crepúsculo** 17–20h | 60 min (**leve, nunca zero**) | 3 |
| **noite** 20–24h | 20 min (cheio) | 12 |
| **madrugada** 00–05h | — | **fora** |

**O crepúsculo é leve, não ausente — e isso é medição, não gosto.** É a faixa com a menor mediana de
nitidez (477 contra ~700) e a maior rejeição por blur (9,2% contra 3,8%), D-173. Luz de transição é
difícil, e é **por isso** que o modelo precisa vê-la. ⚠️ **"Leve" e "ausente" são coisas diferentes**
— há teste fixando a distinção, porque a faixa difícil é sempre a mais tentadora de cortar.

**Regras mantidas:** 250 é **alvo**, não cota · dedup contra o pool inteiro · `excluida` reversível ·
retomável (estado em disco) · anti-lockout (sequencial, pacing, circuito abre em 401/403, zero
varredura de porta) · reserva de disco intocável.

⚠️ **Cada ciclo LOGA início e fim.** Coleta silenciosa que falha é o `days=8` de novo — só que sem
ninguém perceber. O log é a diferença entre serviço e superstição.
