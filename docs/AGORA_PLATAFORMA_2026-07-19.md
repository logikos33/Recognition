# BLOCO AGORA — Plataforma + Documentação (2026-07-19)

> Execução autônoma. Fonte de verdade: código/git/box real (C-04), `git fetch` fresco + `gh` para PR.
> **sudo no Jetson NÃO foi executado** — comandos preparados e validados abaixo para o Vitor rodar.
> **Nada promovido** para staging/main.

---

## ⚠️ PENDÊNCIAS QUE EXIGEM O VITOR (topo)

1. **[A10] Desabilitar GUI no Orin** — pré-condição VERIFICADA no box (produção é headless). Comando pronto em §A10.
   ⚠️ ganho de RAM real medido é **~70 MB** (não os ~800 MB do plano — ver §A10), mas remove o X como superfície de falha.
2. **[A11] Desabilitar `nvargus-daemon`** — pré-condição VERIFICADA (não usamos CSI/Argus). Comando pronto em §A11.
3. **[A12] zram** — **recomendação: NÃO mexer.** O box já está no híbrido ideal (zram prio alta + NVMe prio baixa). §A12.
4. **[docs importados desatualizados]** Os dois arquivos que o plano mandou "LER PRIMEIRO" **não existem no repo**
   (`docs/PLANO_MELHORIAS_AGORA_VS_FEATURES_2026-07-19.md` e `docs/edge/PESQUISA_JETSON_AI_LAB_2026-07-19.md`) —
   nem no working tree nem no histórico git. O conteúdo (landmines L1-L8 etc.) estava embutido no próprio prompt, então
   segui. Se esses docs deveriam ter sido commitados, ficaram fora. **Decisão do Vitor:** criar/commitar, ou aceitar
   que a `REGRAS_PLATAFORMA_JETSON.md §3.6/§8` (alimentada nesta sessão) é o registro canônico.
5. **[premissas obsoletas do plano]** A4/A5/A6 e 5 dos "findings P0 de segurança" **já estavam corrigidos** no código
   (PRs #199/#200 + tasks 073/074/085) — o plano foi escrito contra uma `develop` anterior a esses merges. Detalhe abaixo.
   Não "corrigi" o que já estava certo; **invalidei com evidência** o que o plano supunha quebrado.

---

## A3 — DeepStream 9.1 SAIU?

**SIM. Lançado em 2026-07-14.** E **suporta Jetson Orin** (Nano/NX/AGX) — a primeira release pós-8.0 a voltar a
suportar Orin. **PORÉM exige JetPack 7.2 / L4T r39.2** (não roda no nosso JP6.2).

- **Fontes:** doc oficial NVIDIA (release notes, docs.nvidia.com/metropolis/deepstream); fórum NVIDIA
  (thread "DS 9.0 compatible with Orin" — staff confirma DS 9.0 incompatível c/ JP7.2, "DS-next" = 9.1 é o compatível);
  cobertura MarkTechPost/Blockchain.News (2026-07-18). Confirma o "It will be DeepStream 9.1" de 02/07/2026.
- **Confirmação de suporte a Orin:** SIM, explícito na doc (não só Thor). O bloqueio anterior ("não existe DS com
  suporte a Orin em JP7.2") **caiu**.

**Recomendação sobre JP7.2 / upgrade: NÃO fazer upgrade agora.**
- DS 9.1 não é drop-in: adotá-lo obriga o **port JP7.2 inteiro** (Ubuntu 22→24, kernel 5.15→6.8, CUDA 12.6→13.2,
  TRT 10.3→10.13+, Python 3.10→3.12, **todos os engines TensorRT reconstruídos + INT8 recalibrado**) = **P0-CRÍTICO,
  semanas**. Agora **desbloqueado**, mas o custo permanece.
- DS 9.1 tem **dias de vida** — deixar amadurecer. Manter a baseline congelada (DS 7.1/JP6.2) para o go-live RVB.
- Reavaliar quando (a) houver relato de campo de DS 9.1 estável em Orin NX e (b) RVB estável no baseline atual.

Registrado em `REGRAS_PLATAFORMA_JETSON.md §8.3/§8.4`.

---

## A4 / A5 / A6 — "documentação que mente sobre o código"

**As três premissas do plano estão OBSOLETAS: a documentação já está correta.** O plano foi escrito contra uma
`develop` anterior aos merges de **PR #199** (`fix(edge) escopos de device` — risk:security) e **PR #200**
(`feat(edge) F1 config/poll versionado`), que são os **dois commits mais recentes** da develop e trouxeram tanto as
correções de código quanto as atualizações de doc.

### A4 — bug de device auth em `edge_commands`/`edge_events`
- **Premissa do plano:** `API_CONTRACT_MAP.md:22` afirmaria que o bug "já foi corrigido em edge_commands" (FALSO), e
  o código passaria o objeto `request` onde se espera a string do token.
- **Realidade (C-04):** a linha 22 (achado #8) **já diz "STALE / RESOLVIDO (verificado no código real 2026-07-18)"**
  — e é sobre `edge_events`, não `edge_commands`. O código atual usa o decorator `@require_device_scope(...)`
  (`edge_commands/routes.py:62,76`, `edge_events/routes.py:32`) e, no `/heartbeat`, `auth_header.removeprefix("Bearer ")`
  (`edge/routes.py:145`). **Não existe** passagem de `request` como token. Corrigido pelo commit `ae295c96` +
  PR #199. **→ OBSOLETO. Nenhuma alteração na doc.**

### A5 — `GET /api/v1/edge/config/poll`
- **Premissa do plano:** a doc documentaria a rota como existente, mas ela "não existe" (`grep config` em
  `edge/routes.py` = zero linhas) → deveria virar "PLANEJADA".
- **Realidade (C-04):** a rota **EXISTE** — `edge/routes.py:223` (`@edge_bp.route("/config/poll")`), impl. completa
  F1 (ETag/304, `config_version`, escopo `config:read`). `grep config` retorna ~10 linhas, não zero. Mergeada no
  commit `cbf40104` (PR #200). A doc (`API_CONTRACT_MAP.md:218`) já a descreve **corretamente como existente**.
  **→ OBSOLETO. Rebaixá-la para "PLANEJADA" INTRODUZIRIA um erro — não fiz.**

### A6 — ADR-0019 vs realidade
- **Premissa do plano:** o ADR precisaria ser reconciliado (enroll vs redeem; device auto-assina; `/auth/rotate`).
- **Realidade (C-04):** o `0019-device-tokens-rs256.md` **já tem a seção "Reconciliação com a implementação real
  (2026-07-18) — S7"** (linhas 80-121) que documenta exatamente os três pontos: (1) é `/enroll`, não
  `/enrollment/redeem`; (2) **o device auto-assina** (oposto do desenho); (3) `/auth/rotate` **não existe** → backlog
  (ADR-0054); e nota que a revogação é checada **antes** da verificação de assinatura (correto). Bate 1:1 com o código
  (`edge/routes.py:654-699` enroll; `:162-171` revogação-antes-de-verificar; `grep rotate|redeem` = zero).
  **→ OBSOLETO. Nenhuma alteração no ADR.** (Nota: **ADR-0054 é referenciado mas o arquivo não existe** em
  `docs/decisions/adr/` — pendência menor, ver lista final.)

### Varredura do resto do `API_CONTRACT_MAP.md` — 5 findings P0/P1 estavam STALE (agora corrigidos)
Ao varrer os findings de segurança, achei o oposto do A4/A5: itens marcados como **abertos** que **já foram
corrigidos** — perigoso, porque mandam a próxima sessão caçar vuln fechada (e sugerem exposição de produção que não
existe). **Corrigidos na doc (invalidados com evidência), no estilo inline do próprio documento:**

| # | Afirmação (stale) | Evidência de que está corrigido |
|---|---|---|
| 4 | senha temp previsível `EpiMonitor@..2024!` | `admin/routes.py:337,857,1106` = `secrets.token_urlsafe(12)` |
| 5 | `quality/demo/seed?force=true` apaga produção p/ qualquer user | `quality/routes.py:1976-1985` = superadmin + `{"confirm":true}` |
| 6 | `PATCH modules/.../classes/<id>` cross-tenant sem role | `modules/routes.py:81-95` (task-073) = `modules:write` + 404 cross-tenant |
| 7 | `alerts/<id>/snapshot` sem filtro tenant | `alerts/routes.py:143-158` (task-074) = `get_evidence_key(tenant_id=...)` + 404 |
| 15 | `storage/health` público faz I/O real | `storage/routes.py:23-38` (task-085) = só config, I/O migrou p/ `test-upload` (JWT) |

**Escopo coberto (sem cap silencioso):** verifiquei os itens edge (A4/A5/A6) e **todos os findings P0 de segurança
(#4-#8, #14* , #15)**. **NÃO** re-auditei exaustivamente os P1/P2 restantes (#9-#13 e os itens D-nn) — a doc é bem
mantida (invalida inline com data), mas uma re-auditoria completa das ~30+ linhas é tarefa à parte.
(*#14 já estava marcado "verificar"; #6/#7 cobrem o núcleo cross-tenant.)

---

## A7 / A8 — o que entrou no DOC VIVO (`docs/edge/REGRAS_PLATAFORMA_JETSON.md`)

- **§3 (landmine DeepStream):** linha "8.x/9.x = Thor/JP7" **refinada** → "7.1 p/ JP6.2 Orin; **8.0 = Thor-only SM90**;
  **9.1 (jul/2026) volta a Orin mas exige JP7.2**".
- **§3.6 NOVA — "Landmines de containerização DeepStream / jetson-containers":** L1-L8 completas, cada uma com
  porquê + fonte. **L1 verificada no fonte** (`packages/cv/deepstream/config.py` do HEAD, lido via `gh api`):
  `L4T_VERSION >= 36.4.3` pina `deepstream_sdk_v8.0.0_jetson.tbz2` (Thor-only) → quebra Orin SM 87. Nosso box é
  exatamente r36.4.3.
- **§8 NOVA — "Baseline de produção CONGELADA + matriz":**
  - §8.1 baseline **JP6.2 / L4T r36.4.3 / CUDA 12.6 / cuDNN 9.3 / TRT 10.3 / DeepStream 7.1 / Python 3.10** + motivo.
  - §8.2 matriz **DS ↔ JetPack ↔ L4T ↔ CUDA ↔ TRT ↔ Jetson** (7.1/8.0/9.0/9.1).
  - §8.3 status DS 9.1 (saiu, Orin+JP7.2, recomendação: não upgradar agora).
  - §8.4 port JP7.2 = P0-CRÍTICO (semanas), desbloqueado.
  - §8.5 **FP8 exige SM89+, NVFP4 exige SM110+ — Orin é SM87, não tem. Teto = INT8.** Não perseguir FP4 achando que é software.
- **§7 (config produção):** linha de swap corrigida — zram e NVMe **coexistem** (não "substituiu"), híbrido ideal.
- **`CLAUDE.md` (worktree):** nota de baseline congelada + ponteiro p/ §8 no parágrafo "Cloud → Edge", e nota de que o
  device auto-assina (ADR-0019 S7).

---

## A9 — Issue upstream

**Aberta:** https://github.com/dusty-nv/jetson-containers/issues/1727
Título: *"deepstream config.py picks DS 8.0 (Thor-only) for L4T ≥ 36.4.3 — breaks Jetson Orin (SM 87); JP6.2 needs DS 7.1"*.
Inclui o trecho de `config.py`, a matriz de compatibilidade NVIDIA como evidência, o fix sugerido (split do branch
`>=36.4.3` para dar DS 7.1 ao JP6.2 Orin e reservar DS 8.0 p/ a linha Thor/JP7), e cross-ref dos issues sintomáticos
abertos (#1117, #1722, #1721). Linkada no doc vivo (§3.6). Ofereci PR se os mantenedores concordarem com os limiares.

---

## A10 — Desabilitar GUI (COMANDO PRONTO — sudo = Vitor)

**Pré-condição VERIFICADA no box (produção NÃO depende de X/EGL):**
- Os 4 configs de produção rodando (`app_mm_all_prod_{epi,park,qaux,qmain}.txt`) têm `[tiled-display] enable=0` e
  `[sink0] type=1` (**fakesink**) — nenhum `nveglglessink`/type=2.
- Os 4 processos `deepstream-app` rodando (via systemd `soak-infer-*`) têm **`DISPLAY` ausente no environ** e
  **0 sockets X11 abertos**. Confirmado headless de verdade.
- A dependência de `DISPLAY=:1`/EGL existe **só** no modo de inspeção visual interativo (`mm/screen_mm.sh`,
  `run_mm.sh SCREEN=1`, `SINK_TYPE=2`) — ferramenta manual de QA, **não** o serviço 24/7.

⚠️ **Correção honesta ao plano:** o ganho não é ~800 MB. Medido no box, o stack GUI (gnome-shell 50 MB + Xorg +
gsd-*) soma **~71 MB de RSS**. Em Ubuntu "minimized" o desktop é enxuto. O valor real de desabilitar é **remover o X
como superfície de falha** + liberar um pouco de memória de GPU (alocações do compositor que o RSS subconta) +
~dezenas de MB de RAM. Não conte com 800 MB.

**Efeito colateral a aceitar:** em `multi-user.target` o GDM/X não sobe → `DISPLAY=:1` deixa de existir; a QA visual
no monitor físico (`screen_mm.sh`) para de funcionar até reverter. **Produção (fakesink) não é afetada.** Se quiser QA
visual on-box eventual, ou reverta temporariamente, ou migre aquela inspeção p/ sink RTSP (`nvrtspoutsinkbin`).

```bash
# Aplicar (efetivo no próximo boot — recomendado):
sudo systemctl set-default multi-user.target

# (Opcional) aplicar AGORA sem reboot — derruba a sessão X atual, faça em janela de manutenção:
#   sudo systemctl isolate multi-user.target

# Reverter:
sudo systemctl set-default graphical.target
```

---

## A11 — Desabilitar `nvargus-daemon` (COMANDO PRONTO — sudo = Vitor)

**Pré-condição VERIFICADA:** estado no box = `active` + `enabled` (PID 1019). **Não usamos CSI/Argus** — as fontes
são RTSP via MediaMTX (ADR-0009); `grep -riE 'nvarguscamerasrc|argus|csi|sensor-id'` nos configs `mm/*.txt` = **zero**.
Risco de desabilitar = **zero** para o nosso pipeline.

```bash
# Aplicar:
sudo systemctl disable --now nvargus-daemon.service

# Reverter:
sudo systemctl enable --now nvargus-daemon.service
```

---

## A12 — zram (DECISÃO CONSCIENTE — recomendação: NÃO mexer)

**Estado REAL medido no box (C-04, não o doc):**
```
NAME       TYPE       SIZE   USED PRIO
/swapfile  file        16G  15.8M   -2     ← NVMe, overflow (prio baixa)
/dev/zram0..7 partition 8×978M ~1.8G  5    ← comprimido em RAM (prio alta)
vm.swappiness = 10
```
O box **já implementa o híbrido defensável** que o plano descreve: **zram prio alta (5)** + **NVMe prio baixa (−2)**.
Sob a carga do soak (4 módulos), o kernel prefere o zram (~1.8 GB usados) e **mal toca o NVMe** (~16 MB) — exatamente
o desejado. RAM: 15 Gi total, **4.5 Gi usados, ~10 Gi disponíveis**.

**Trade-off:** ZRAM é swap comprimido em RAM — muito mais rápido que NVMe e **sem desgaste de célula NAND**. A
recomendação da NVIDIA de desabilitá-lo mira **build de container / modelos grandes**, não inferência 24/7.
**Recomendação: MANTER os dois como estão** (já é a "opção defensável" do plano). Nenhum comando necessário. A decisão
final é do Vitor; se quisesse remover zram seria contraproducente aqui.

*(Nota: o doc `§7` dizia "NVMe substituiu o zram-only" — impreciso; corrigi para "coexistem".)*

---

## RAM — antes / projeção depois

| | Estado |
|---|---|
| **Antes (medido, sob soak 4 módulos)** | 15Gi total · **4.5Gi usados · ~10Gi disponíveis** · zram ~1.8G · NVMe ~16M · GPU ~68-76% |
| **Depois de A10+A11 (projeção honesta)** | reclama **~70-150 MB** de RAM (GUI ~71 MB RSS + daemon argus) + um pouco de VRAM. **Não** ~800 MB. Principal ganho = menos superfície de falha (X) num box 24/7. |

O soak segue rodando (10/10 serviços `soak-*` up); as medições foram read-only, sem tocar sudo nem derrubar nada.

---

## Arquivos alterados nesta sessão

- `docs/API_CONTRACT_MAP.md` — invalidados com evidência os findings #4,#5,#6,#7,#15 (todos já corrigidos no código).
- `docs/edge/REGRAS_PLATAFORMA_JETSON.md` — §3 refinada; **§3.6 NOVA** (L1-L8); **§8 NOVA** (baseline+matriz+FP8/NVFP4); §7 swap.
- `CLAUDE.md` (worktree) — nota de baseline congelada + ponteiro §8 + nota device auto-assina.
- `docs/AGORA_PLATAFORMA_2026-07-19.md` — este relatório.
- **Upstream:** issue dusty-nv/jetson-containers#1727.

**Nada promovido.** PR alvo: `develop`.
