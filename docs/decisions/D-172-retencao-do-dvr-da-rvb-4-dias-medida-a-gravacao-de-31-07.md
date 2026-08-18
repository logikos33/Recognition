# D-172 · Retenção do DVR da RVB = 4 dias (medida) · a gravação de 31/07 está PERDIDA

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **Data:** 2026-08-18 · **Impacto:** P1-ALTO (operacional, irreversível)

Medido no gravador (Intelbras `iNVD 3032`, série `DQN0009707690`) via CGI `mediaFileFind` — leitura
pura, poucas requisições, credencial que o agente já usa. **O DVR trava por força bruta; medir não
pode virar ataque.**

| medida | resultado |
|---|---|
| mais antigo, janela de 120 dias, canal 1 | **2026-08-14 06:55** |
| canais 4, 6, 8, 12, 20, 27 | **14/08 — todos dentro de 23 min** |
| janela 25/07 → 05/08 | `Error / Bad Request` — **vazia** |
| controle 10/08 → 16/08 | `OK`, primeiro 14/08 06:56 |
| disco, 4 partições | `UsedBytes == TotalBytes` — **100% cheias, ~3,9 TB** |

**O alinhamento entre canais levantou suspeita de wipe; a leitura do disco a descartou.** Disco 100%
cheio é FIFO sobre pool compartilhado: a frente de sobrescrita anda em **ordem de tempo**, não por
canal, e por isso todos os canais perdem o mesmo instante. ~1 TB/dia para ~28 câmeras.

> 🔴 **A gravação de 31/07 está perdida. Irrecuperável. Não há o que minerar dela.**

**Consequências:**
- todo plano de mineração cabe em **4 dias**, não 8 — o default `days=8` era otimista por 2×
- o modo de falha era o pior: metade do plano caía num vazio **sem erro**, só rendimento menor
- mineração tem de ser **contínua**, não campanha mensal: a janela se renova inteira a cada 4 dias
- ⛔ não se conserta com flag — é capacidade de disco

⚠️ **Re-medir quando mudar número de câmeras, bitrate ou disco.** Retenção é consequência das três.
