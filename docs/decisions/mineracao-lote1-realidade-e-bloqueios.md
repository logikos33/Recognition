# Mineração DVR — Lote 1: realidade do código, bloqueios e o que o Vitor provisiona

- **Tipo:** Registro de rodada (mineração validação) → decisões D-112..D-115
- **Data:** 2026-08-16 · **Escopo:** somente DEV · **Módulo:** EPI · **Tenant:** RVB
- **Garantias:** zero código de produto alterado · **nada minerado** · **nenhum frame** puxado do gravador · nenhuma credencial impressa · não toca `staging`/`main`/`interchange`
- **Resultado da rodada:** 🔴 **Lote 1 NÃO executado — bloqueado em provisionamento (ato do Vitor).** A corrente foi lida ponta a ponta no código; os bloqueios estão abaixo, com escopo mínimo e como revogar.

---

## 0 · Divergências prompt × repo (segui o repo)

| O prompt dizia | O repo/box diz | Segui |
|---|---|---|
| Gate `CONFIRM_MINE=1` liga a mineração | 🔴 **`CONFIRM_MINE` não existe no código** (`grep` vazio). `replay_miner.main()` roda **só o dry-run**; a campanha real exige escrever um script curto no box que chama `ReplayMiner.mine(plan)` — passo humano deliberado **por desenho** (`replay_miner.py:811`; runbook `DVR_REPLAY_MINER.md`) | repo |
| Canais de "presença": 1·8·11·12·19·23·28·4 | Canal **8 é `ceiling`** (teto 60 crops, já 82% Botas) — **não** é fonte de presença. Presença = `full`: **1,4,11,12,19,23,28** (`replay_miner.py:106`). Canal 10 = `absence` | repo |
| Rodar Lote 1 nesta sessão | O `replay_miner.py` **não está no release deployado** no pandora (`find` não achou; `/home/pandora/recognition` não tem `services/edge-sync-agent`). O box está enrolado em **PRODUÇÃO** (unidades `edge-sync-agent`/`edge-live-view` ativas empurram pra nuvem prod) | reportei bloqueio |
| Tela força estado por EPI (bloco 4) | 🔴 **D-108 NÃO implementado** — `SearchFindingsPanel.tsx:44` ainda é por-caixa (crop-tile), sem veredito por-recorte, sem "não sei". Foi só **decisão** na rodada anterior | reportei |
| "Não sei" não entra no dataset (passo 4) | 🔴 **Hoje é FALSO** para `curation_status='duvida'`: o export exclui só `'excluida'`; `'duvida'` **continua entrando** no pool ("ainda não há decisão humana" — `versioning_v2.py:18-19,80-97`) | reportei |

**Confirmados do prompt:** anti-lockout embutido (qualquer 401/403 → `circuit_open` aborta a run inteira, sem retry — `replay_miner.py:533-542`) ✓ · reserva de disco `has_disk_reserve(8GB)` ✓ (box tem 56G livres, folga) · pipeline em memória, delta de disco 0 no Orin (ADR-0033/0045) ✓ · cred DVR nunca em `argv`, injetada por env ✓.

---

## 1 · O que consegui fazer (seguro) e o que não (bloqueado)

| Item de aceite | Status | Nota |
|---|---|---|
| Branch anterior pushada + PR rascunho | ✅ | **PR #385** (D-107..D-111, draft, não mergeado) |
| Lote 1 minerado (~50) + disco/banda/tempo | ❌ **bloqueado** | ver §2 — provisionamento do Vitor |
| Qualidade dos recortes, com exemplo | ❌ | sem recorte real — nada a exemplificar; limiar de blur (`3000.0`) **nunca calibrado com recorte real** (`replay_miner.py:237`) |
| Provisionamento com escopo mínimo + revogar | ✅ | §2 |
| 6 passos, um a um | ❌ **parado no passo 0** | sem conta de teste (`E2E_ANNOT_PASSWORD`), sem fila DEV semeada — não dá pra logar nem percorrer |
| Tempo real por recorte | ❌ | depende do percurso |
| Razão ausência ÷ recorte **medida** | ❌ | duplamente bloqueada: sem crops (§2) **e** sem tela de veredito (D-108) — só projeção (§3) |
| Veredito: meta de ausência alcançável? | ⏸️ **indeterminado** | condição objetiva de desbloqueio em §3 |
| Quantos "não visível" | ❌ | sem crops |

---

## 2 · O que o Vitor precisa provisionar (⛔ nada criado por mim)

Para o Lote 1 poder rodar (no pandora, na VLAN) **e** as imagens caírem no **DEV** (não em prod):

| Item | Para quê | Escopo mínimo | Como revogar |
|---|---|---|---|
| **Token de device DEV com escopo `frames:write`** | o miner sobe via `POST /api/v1/edge/frames` (`edge/routes.py:587`), que exige device JWT `frames:write`. O box está enrolado em **prod** → sem identidade DEV, minerar iria pra prod (proibido) ou pra lugar nenhum | **só `frames:write`**, tenant RVB, ambiente **DEV** | revogar o `device_token` no DEV (`public.device_tokens`) |
| **Confirmar presença da credencial DVR no box** (`RECORDER_USERNAME`/`PASSWORD`/`HOST`/`PORT`) | o miner valida uma vez no boot; **injetada por env, nunca argv** | leitura da unidade que já roda o edge — só **confirmar presença**, ⛔ não me passar o valor | n/a (já é do box) |
| **`RECORDER_CLOUD_ID`** (uuid de `public.recorders`) do gravador RVB no DEV | identificar o gravador no upload | leitura | n/a |
| **`channel_map` real** (camera_id DEV por canal) | montar o `build_sampling_plan` — os canais `full`/`absence` precisam do camera_id DEV correspondente | leitura do DEV | n/a |
| **Conta de teste DEV + `E2E_ANNOT_PASSWORD`** | logar no DEV e percorrer os 6 passos | **usuário próprio (⛔ não o do Vitor)**, só DEV, revogável | desativar o usuário no DEV |
| **Credencial R2 leitura, bucket DEV** | verificar que o crop chegou ao storage | **read-only**, **só bucket DEV** | rotacionar a chave R2 DEV |
| **Acesso read-only ao DEV DB** | conferir procedência (`source='manual'`) e contagem | **read-only** | rotacionar (já pendente — senha vazou) |

🔴 **Justificativa do R2 (frames de trabalhadores reais):** leitura é necessária só para **confirmar que o recorte subiu e é legível** (passo 1 do percurso e qualidade). Read-only + só-bucket-DEV é o mínimo: não permite escrita, não toca prod, e cobre exatamente "o crop está lá e dá pra ver". Sem isso, "imagem carrega" vira palpite.

⚠️ **Além do provisionamento — uma falta no código para o Lote 1 ser "pequeno":** o miner **não tem teto TOTAL de crops** (só `campaign_max_crops` por-canal do canal 8). Para garantir "~50 e para", ou se molda o plano para 1 canal-turno e para na mão, ou se adiciona um `max_total_crops` ao `mine()` (mudança P, segura, com teste). Sem um dos dois, um plano de 4 canais × 1 dia rende ~260 crops estimados, não 50.

---

## 3 · A pergunta da ausência — por que não deu para MEDIR, e a projeção (planejamento, não medição)

**Não medível esta rodada.** A medição exige (a) recortes reais do Lote 1 **e** (b) a tela de veredito forçado (D-108) que **transforma cada recorte em rótulo de ausência por EPI não usado**. Nenhum dos dois existe hoje. O número do dry-run (~209 de ausência) contava só o **já anotado** — não o potencial.

**A projeção, como fórmula (⛔ não é medição):** sob veredito forçado, cada recorte de pessoa rende `(tipos_EPI_aplicáveis − tipos_vestidos)` rótulos de ausência. Para ~50 recortes do Lote 1 e ~3 tipos aplicáveis na RVB (máscara, protetor auditivo, botas — a taxonomia tenant real está em `public.yolo_classes`, que **não consegui enumerar** sem DB DEV):

- se em média ~2 de ~3 tipos são usados → **~1 ausência/recorte** → ~50 rótulos de ausência já no Lote 1
- se menos são usados → razão maior

**Veredito (item 8) — indeterminado, com condição de desbloqueio:** a meta de 100+/classe de ausência é **plausivelmente alcançável se a razão medida for ≥ ~1 ausência/recorte** — mas isso é exatamente o que o Lote 1 + a tela de veredito têm de medir. ⏸️ **Adiar o veredito até:** (1) token DEV `frames:write` provisionado, (2) Lote 1 de ~50 recortes real, (3) D-108 (veredito forçado) implementado. Só então a razão vira número, não fórmula.

---

## 4 · O que ⛔ não deu para determinar

- **Taxonomia RVB real (6 classes tenant)** — em `public.yolo_classes`, sem acesso ao DEV DB (senha vazada/não rotacionada). A migration 009 só tem o EPI genérico (helmet/vest/gloves/glasses).
- **Presença da credencial DVR no box** — não sondei (evitar risco de lockout e de tocar valor); é confirmação do Vitor.
- **Qualidade real do recorte / limiar de blur** — sem hardware/crop real; o `3000.0` é calibrado só contra fixtures sintéticos.
- **Onde exatamente o edge-agent deployado vive no box** — `/home/pandora/recognition` existe mas não bate com o layout do repo; `replay_miner.py` não foi achado no release. Precisa de OTA/deploy do miner antes de rodar.

---

## Apêndice — método

Push + PR via git/gh. Leitura do código no worktree `origin/develop`. Um subagente leu a árvore ERRADA (o checkout iCloud `fix/admin-users-null-tenant-id`, 12 migrations) e foi **descartado** — os fatos aqui foram reverificados por mim no worktree certo (111 migrations, última `122`). SSH ao pandora foi só reachability/localização read-only, sem sudo, sem tocar o DVR, sem imprimir segredo. Nada minerado.
