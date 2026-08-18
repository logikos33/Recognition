# D-090 · Contador de cota persistido + interruptor durável de coleta

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · Claude · ✅ (PR #358) — fecha o buraco operacional apontado no D-86**

O contador `frames_uploaded` do coletor vivia em memória e **re-armava a cota a cada
restart** — prova viva no acervo: RVB Camera 1 com **1.679 frames** para alvo de 1.000.
Com a campanha das câmeras novas isso viraria multiplicador de custo. Agora:

1. **Contador persistido** em `collector_state.json` (`COLLECTOR_STATE_PATH`, mesmo diretório
   e disciplina do `config_cache.json`): carregado no boot, salvo por rajada, atômico,
   best-effort. No deploy do box, o arquivo é **semeado com as contagens reais do banco** —
   partir de zero re-daria cota cheia às 8 câmeras antigas.
2. **`COLLECTOR_ENABLED=0` no .env** = desligado durável: o processo sobe, avisa em WARNING e
   fica ocioso sem abrir nenhuma conexão. **Sobrevive a restart e reboot** — "a cota bateu"
   (memória) e `systemctl stop` (unit habilitada religa no reboot) não são desligamento.
   É o mecanismo do "parar TUDO para treinar" pós-campanha.
