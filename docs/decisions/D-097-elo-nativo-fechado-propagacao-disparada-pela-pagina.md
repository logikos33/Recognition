# D-097 · Elo nativo FECHADO: propagação disparada pela página, executada pelo box sozinho

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · Vitor (sequência) + Claude (execução) · ✅**

Sequência do "PODE" executada na ordem: PR #367 mergeado no develop (CI verde; única falha =
SCA npm audit do landing, pré-existente e não-bloqueante) → **OTA do box** pelo canal
(`PUT /admin/software-channels/dev` → `f8a3f1d`, updater timer, swap atômico 08:43, agente
reiniciado — release já com o executor `ensure_dependencies`; trava do D-94 removida) →
**duas rodadas nativas disparadas pela PÁGINA, zero intervenção no box**.

**A prova do elo (job `8e914792`, validação via UI):** estúdio de anotação → frame semeado do
Canal 8 (11/08) → painel "Buscar imagens iguais" (selo *"processando no equipamento da fábrica
— as imagens não saem do site"*, SEM linha de custo) → Iniciar busca → worker despachou
`edge_commands` → **poller nativo do box consumiu e ackou `done {launched: true, unit:
propagation-8e914792}`** → unit systemd orçada (6G/400%) rodou o executor → callbacks →
**`completed` em 10min23s (134 frames: 129 sementes embedadas + pool)** → barra na página:
*"✓ 1 proposta encontrada · Revisar"*. Recursos durante: job 2,1 GB, GR3D 38–99%,
MemAvailable ≥ 8,0 GB, live view intocado.

**Lote de 100 (job `9a764297`, pela página, opção "100 imagens"):** pool completo do dia
(208 frames, 211 caixas/129 frames de semente, top-100 resultados): **completed em 15min48s (948s), mesma esteira nativa (ack `done {launched: true}`), 1 proposta — 'Capacete', confidence 0,79, num frame-ALVO novo**. Ritmo bruto consistente nos dois jobs: ~4,6 s/frame incluindo o re-embed das sementes.

**🔴 O achado que muda a próxima conversa — rendimento do v1:** com 211 caixas de semente e
threshold 0,65, a validação produziu **1 proposta em 134 frames**; o lote de 100, **1 proposta em 208 frames (79 alvos novos)**. A infra
está provada e barata (equipamento da fábrica, sem custo por rodada); o gargalo agora é o
**recall do pipeline v1** (SAM AMG `points_per_side=12` + similaridade média por classe +
threshold 0,65). Antes de gastar horas no pool completo restante (~2.300 frames nas outras
fatias câmera×dia), calibrar: threshold menor / `points_per_side` maior / top-K por frame —
decisão do Vitor com a fila de revisão aberta na frente.

**Quebra achada e corrigida no caminho:** o api-v3 DEV estava servindo um deploy de 04:04Z
(`railway up` de árvore SEM a feature, da sessão paralela) — preflight sem `gpu_provider` e a
UI honestamente mostrando custo RunPod. Redeploy de `develop f8a3f1d` (api-v3 + worker +
frontend) restaurou. Regra que fica: **depois de merge, o deploy DEV precisa vir do develop
mergeado — duas sessões dando `railway up` de árvores diferentes se atropelam em silêncio.**

**Dívidas novas (próxima rodada, não esta):**
- Poller lança TODOS os comandos `run_propagation` pendentes de uma vez — 2 jobs simultâneos
  = 2×6G no box (OOM). Serializar (1 unit por vez) antes de qualquer fila de fatias.
- Env file 0600 fica no disco após job concluído (só é removido em falha de launch).
- Barra: "Preparando referências (129 **caixas**)" — `seed_count` conta FRAMES (211 caixas em
  129 frames); wording.
- Somam-se às do D-94 que ficam: callback_token pós-terminal, cache de pesos por sha256.
