# D-094 · Propagação no edge RODOU DE VERDADE no Orin — medida, com live view ligado

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**11/08 (noite) · Claude (execução e medição) · ✅ números reais, decisão de operação é do Vitor**

Dois jobs reais processados no box (DEV, tenant RVB, câmera 2a683620, frames de 11/08 —
**data de operação**, exatamente o que o provider edge desbloqueia), pool de validação de
**8 frames** (3 sementes/9 caixas + 5 alvos), propostas no banco via callback:

| Métrica | Medido |
|---|---|
| **Tempo total por execução** | run 1: **49,9s** · run 2: **46,8s** (8 frames cada) |
| **Por frame (fase pool)** | **≈3,3–4,0 s/frame** (SAM AMG + embeds DINOv2 + callback por frame) |
| Carga fixa por execução | pesos (R2+Meta, sha256 verificado): 6,4–8,3s · modelo+sementes: ~12s — **toda execução repaga** (o executor sempre rebaixa e reverifica os pesos, por desenho) |
| Pico de RAM do job (cgroup) | **2,1 GB** (MemoryMax=6G nunca pressionado) |
| Pico de GPU | GR3D **99%** em rajadas (25 amostras >20% em ~50s) |
| RAM do sistema no pico | 7,4 GB de 15,6 GB (MemAvailable nunca abaixo de **8,4 GB**) |
| **Impacto no live view (MEDIDO)** | POST /segment/min: **55,6 antes · 56,3 durante · 57,4 depois** — flat; **zero** respostas não-201; viewer sintético ativo pelo fluxo tokenizado durante todo o run 2 |
| Propostas | 1 proposta/run ("Botas", confidence 0,71) em `pre_annotations` — **fila de proposta, zero linhas em `frame_annotations`** |

**Projeção para 662 frames** (número do Vitor): 662 × 3,3–4,0s + ~15s de setup ≈ **37–45 min**,
**com o live view ligado** (impacto medido: nenhum) e dentro do timeout default de 2h.
Régua do prompt: ficou entre o cenário "~1s/frame · roda quando quiser" e "~5s/frame · roda com
live view parado" — pelo medido, **não precisa parar o live view**. A decisão é do Vitor.

**Falha legível do LD_LIBRARY_PATH (testada forçando caminho errado):** job 3 rodou com
`LD_LIBRARY_PATH` quebrado de propósito → `error_reason` na tela:
*"não foi possível carregar o modelo no equipamento da fábrica — biblioteca CUDA não encontrada
(libcudss.so.0). Caminhos de busca (LD_LIBRARY_PATH): /caminho/errado/... Ver
docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.5"* — nunca mais traceback cru
(`humanize_startup_error`, commit e35739e).

**Quebras encontradas no caminho (cada uma corrigida e testada):**
1. **`pip install` incondicional do executor** clobberaria o torch jp6 do venv do box (wheel
   SBSA → iGPU morta, REGRAS §3.1/§3.5) → `ensure_dependencies()` instala só o que falta.
2. **`WORK_DIR=/root`** não é gravável no box (systemd --user) → override por env.
3. **🔴 URL presignada com `&` + wrapper `source` bash = env perdida em silêncio**
   ("MANIFEST_URL não definido" com o arquivo presente). Fix estrutural (commit 85739a5):
   lançador virou **serviço transiente com `-p EnvironmentFile=`** (systemd lê literal, sem
   shell, e é detached — não bloqueia o poller). Ack `failed` de `run_propagation` agora
   também derruba o job na hora (sem esperar o reconciler de 2h).

**O que foi contornado (e o que deixou de acontecer):** o box roda um release INTERMEDIÁRIO do
edge-sync-agent (variante `--scope`+source, anterior ao fix) — os lançamentos medidos foram
feitos manualmente com o MESMO `systemd-run`/budget/env-file 0600 que o handler corrigido usa;
o polling nativo do box tentou executar os mesmos comandos, falhou no bug do `&` (exit 1) e
ackou `failed`. O elo comando→launch nativo fim-a-fim ainda NÃO foi provado com o código
corrigido.

**🛑 Trava operacional até o próximo release OTA do box:** com o release atual, TODO job edge
criado no DEV será tentado nativamente pelo box, falhará no launch e o ack `failed` derrubará
o job (comportamento honesto, mas mata o job antes de qualquer execução manual). **Não criar
jobs de propagação edge no DEV até o box receber release ≥ 85739a5** — e esse release precisa
incluir o executor corrigido (e35739e), senão o `pip install torch` incondicional do executor
antigo quebra a iGPU do venv.

**Dívidas pequenas registradas:** callback_token não é revogado após estado terminal no
caminho edge (RunPod revoga; edge fica na coluna até sempre) · o executor rebaixa ~460MB de
pesos por execução (cache local por sha256 pouparia banda em lote grande).
