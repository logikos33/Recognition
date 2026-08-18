# D-123 · A campanha real de mineração é passo humano no box — `CONFIRM_MINE` não existe

**Seção:** Rodada 16/08 (tarde) — mineração DVR Lote 1: realidade do código e bloqueios · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-112→D-123** na consolidação dos PRs #385/#386/#388 (D-112 já em uso na develop).

**16/08 · Claude · 📄 análise (sem código)**

**Medido no código.** `grep CONFIRM_MINE` = vazio; o gate citado no prompt **não existe**.
`replay_miner.main()` (`services/edge-sync-agent/app/collector/replay_miner.py:811`) roda **só o dry-run**.
Ligar a mineração real exige escrever um script curto **no pandora** que constrói `RecorderClient` +
`PersonDetector` + `TokenSource` e chama `ReplayMiner.mine(plan)` — **por desenho** não há entrypoint
automático (runbook `DVR_REPLAY_MINER.md`). Correções de fato ao prompt: **canal 8 é `ceiling`** (teto 60,
82% Botas), **não** presença — presença = `full` (1,4,11,12,19,23,28); ausência = canal 10
(`replay_miner.py:106`).

**Veredito: registrar a realidade.** A campanha real é **ato humano deliberado no box**, não autônomo da
nuvem. Anti-lockout embutido confirmado (401/403 → aborta run inteira, sem retry, `replay_miner.py:533-542`).
