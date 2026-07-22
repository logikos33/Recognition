# Melhorias: o que fazer AGORA vs o que vira FEATURE

**Data:** 2026-07-19 · **Base:** varredura do repo real (C-04) + pesquisa Jetson AI Lab + relatórios de campanha/soak/shootout

**Critério do corte:**
- **AGORA** = não exige decisão de produto, não exige input do cliente, risco baixo, e o custo de adiar é maior
  que o de fazer. Conserto, higiene, documentação, config.
- **FEATURE** = exige desenho, ADR, task, código novo relevante — e em alguns casos uma decisão sua antes de começar.

---

# PARTE 1 — AGORA

## 1.1 Bloqueantes de go-live (fazer antes de qualquer coisa nova)

| # | Item | Esforço | Por que agora |
|---|---|---|---|
| **A1** | 🔴 **Rotacionar a senha `admin@rvb.com.br`** (pela aplicação, nunca shell/SQL; não commitar a nova) | minutos | Credencial commitada no git. **Bloqueia go-live.** Depende de você |
| **A2** | ⚠️ **Fan `quiet` → `cool`** antes da carga 24/7 (sudo) | 1 comando | Está temporariamente em `quiet`. Já registrado na checklist da task-097 |
| **A3** | **Verificar se o DeepStream 9.1 saiu** | 10 min | Define se existe caminho de upgrade Orin→JP7.2. Dado mais recente: 02/07/2026 |

## 1.2 Documentação que está MENTINDO sobre o código

Estes são os mais perigosos da lista, porque induzem a próxima sessão ao erro.

| # | Item | Onde | Impacto |
|---|---|---|---|
| **A4** | `API_CONTRACT_MAP.md:22` afirma que o bug de device auth "já foi corrigido em edge_commands" — **falso**, está presente nos dois blueprints | `docs/API_CONTRACT_MAP.md` | Doc mente → próxima sessão confia e não corrige |
| **A5** | `API_CONTRACT_MAP.md:218` documenta `GET /edge/config/poll` **como existente** — a rota não existe | idem | Idem |
| **A6** | **ADR-0019 diverge da implementação** em rotas (`/enrollment/redeem` e `/auth/rotate` não existem) e no modelo de confiança (device auto-assina; o ADR diz que o cloud assina) | `docs/decisions/adr/0019-*` | Corrigir o ADR para descrever a realidade |
| **A7** | Landmines **L1–L8** da pesquisa Jetson AI Lab → alimentar o doc vivo | `docs/edge/REGRAS_PLATAFORMA_JETSON.md` | L1 sozinha (jetson-containers instala DS 8.0 no nosso L4T) economiza dias |

## 1.3 Baseline de plataforma — congelar e registrar

| # | Item | Por quê |
|---|---|---|
| **A8** | **Congelar JP6.2 / L4T r36.4.3 / CUDA 12.6 / TRT 10.3 / DS 7.1** como baseline de produção, com o motivo escrito | É a **última combinação Orin + DeepStream plenamente suportada**. DS 8.0 é Thor-only; DS 7.1 quebra no JP7.2 |
| **A9** | **Abrir issue upstream** no `jetson-containers` sobre o mapeamento errado de DS para L4T ≥36.4.3 | Devolve pra comunidade e cria rastro |

## 1.4 Otimização de RAM que ficou na mesa

| # | Item | Ganho | Risco |
|---|---|---|---|
| **A10** | **Desabilitar GUI**: `sudo systemctl set-default multi-user.target` | **~800 MB** | ⚠️ mata o `DISPLAY=:1` do monitor físico (GDM). Confirmar que estamos em RTSP-out e que nenhum config usa `nveglglessink` |
| **A11** | `sudo systemctl disable nvargus-daemon.service` | não quantificado | **Zero** — é daemon de câmera CSI/Argus; usamos RTSP (ADR-0009) |
| **A12** | **Decidir zram conscientemente** (`swapon --show`, `zramctl`) | — | ZRAM é swap comprimido em RAM: mais rápido que NVMe e **sem desgaste de célula**. A recomendação da NVIDIA de desabilitar é para *build*, não para inferência 24/7. Manter os dois com prioridades distintas é defensável |

## 1.5 Consertos de código (não são features — é código quebrado)

| # | Item | Onde | Estado |
|---|---|---|---|
| **A13** | **Bug B1 — device auth**: passa o objeto `request` onde a função espera a **string do token** → `DecodeError` sempre | `edge_commands/routes.py:32-48` · `edge_events/routes.py:41,49` | **Comandos e eventos nunca autenticaram.** Já está no prompt F0 |
| **A14** | **Bug B2** — auth fora do `try` em `poll_pending_commands` → 500 em vez de 401 | `edge_commands/routes.py` | idem |
| **A15** | `CountingLineOperation` **registrada duas vezes** | `operations/canonical/__init__.py:12,18` | Menor, mas registry sem validação de duplicata |
| **A16** | **Zero testes** em `edge_commands` e `edge_events` | — | Escrever junto com o conserto |

## 1.6 Segurança (trilha separada, prioridade alta)

| # | Item | Gravidade |
|---|---|---|
| **A17** | **S1 — escopos de device declarados e NUNCA aplicados** (não existe `require_scope`; device com escopo de heartbeat chama qualquer endpoint) | 🔴 Fazer **antes** de nascerem mais rotas de device |
| **A18** | **S2 — `serve_hls` sem checagem de tenant** (quem souber o UUID lê vídeo de qualquer tenant) | 🔴 Exige decisão de abordagem antes de codar |
| **A19** | **S3 — `toggle_module_class` cross-tenant** (liga/desliga classe de outro tenant) | 🔴 Correção pequena, risco alto → 404 |
| **A20** | **S5** — `GET /edge/commands` e `PATCH /site-gateways/<id>/status` sem gate de admin | ⚠️ |
| **A21** | **S4** — `/api/streams/status` público, sem tenant, expõe topologia de workers | ⚠️ Exigir auth ou remover |

## 1.7 Higiene de repositório

| # | Item | Estado |
|---|---|---|
| **A22** | **Consolidar PRs na develop**: #197 (shootout), #194 (delta provisioning), #189 (4 P1 de segurança), #78 (decidir) | Prompt pronto: `CONSOLIDAR-DEVELOP-PROMPT` |
| **A23** | **Atualizar o relatório do shootout** — o D-FINE-S convergiu e **bateu** o RF-DETR (AP_small 0.626 vs 0.565); o doc ainda diz "provisório/não convergido" | Entra junto no #197 |
| **A24** | **Promoção develop→staging** (108 commits) | ⚠️ **Evento próprio**, com janela e rollback. Produção 24/7 |

---

# PARTE 2 — FEATURES

## 2.1 Integração Recognition ↔ Edge (o programa principal)

Fases do `PLANO_CONTROLE_EDGE_2026-07-18.md` / ADR-0055 (renumerado de 0054). **F0 já está na Parte 1** (é conserto).

| Fase | Feature | Critério de aceite | Dependência |
|---|---|---|---|
| **F1** | **`GET /edge/config/poll`** — a ponte. Device auth, escopo = site, `config_version` + ETag/304, reusar o composer de `scenarios/` | Config gravada na UI chega ao Jetson sem SSH | F0 |
| **F2** | **Fechar o laço decorativo** — `fps_target`, `quality_preset`, `confidence_threshold` lidos da config, não de env global | **Operador muda FPS na UI → pipeline obedece em ≤1 ciclo de poll**, provado por telemetria | F1 |
| **F3** | **Comandos ponta a ponta** — cliente `command_poller` no main tree, ciclo `pending→acked→running→done\|failed\|expired`, TTL, idempotência | Operador reinicia pipeline pelo front | F0 |
| **F4** | **Download de modelo pro device** — `/edge/models/<id>/download`, escopo `models:download`, checksum, rollback automático | Troca de modelo na UI → engine novo no Jetson | F1 |
| **F5** | **operation-types faltantes** — `attention_points`, `stage_timer` (+ `crowd_zone`, `dwell_zone`) | Cenário de qualidade da RVB configurável | ⚠️ **decisão** (§3) |
| **F6** | **Motor de operações em produção** — hoje `evaluate()` só roda no `/test`; `operation_results` não é populada por worker nenhum | Operação configurada gera resultado real | F1 |
| **F7** | **DeepStream configurado pelo banco** — `deepstream/` está **vazio** (só `.gitkeep`) | Config de pipeline vem do cenário | ⚠️ **decisão** (§3) |
| **F8** | **ADM no front** — CRUD de site, enrollment (gerar/mostrar 1×/revogar), gateway, console de comandos, **painel de config efetiva + drift** | Operação administrável sem curl | F1, F3 |

> **Nota sobre F8:** várias dessas rotas **já existem na API** e só não têm cliente no front (sites CRUD,
> enrollment-tokens, device revoke, site-gateways). É trabalho de UI, não de backend.

## 2.2 Features de produto vindas da pesquisa

| # | Feature | Valor | Custo/risco |
|---|---|---|---|
| **P1** | **NanoOWL — pré-anotação zero-shot** no slot `SERVICE_TYPE=pre-annotation` (hoje flag OFF) | Bootstrap de dataset sem rótulo. Ataca o gargalo real: **o dataset de qualidade da RVB ainda não existe rotulado** | Baixo. Apache limpo. ⚠️ usar **só o caminho OWL-ViT puro** (o tree predictor importa CLIP, cujo card proíbe vigilância) |
| **P2** | **VLM como adjudicador de evento** (2 estágios) — detector gera trigger, VLM analisa 4–8 keyframes do clipe já gravado | Responde ao requisito de "atividade suspeita" da RVB **sem prometer detecção de furto**. Gera **justificativa em linguagem natural** do alerta | Médio. ⚠️ **decisão de licença** (§3). Começar por llama.cpp Q4 (~2,1 GB), nunca vLLM com pool pré-alocado |
| **P3** | **Busca semântica sobre a evidência** — "ache clipes com pessoa caída" sobre o que já está no R2 | Diferencial de produto, custo baixo (roda offline, sob demanda) | Baixo. Depende de P1 |
| **P4** | **Triagem de falso-positivo assistida** — o VLM explica por que o alerta disparou | Ataca o que **mata sistema de vigilância em produção**: custo de triagem humana | Depende de P2 |

## 2.3 Features de plataforma/infra

| # | Feature | Valor |
|---|---|---|
| **I1** | **Golden image + registry privado** — build no bench, `docker pull` pinado por **digest** no cliente | Build de DeepStream é ~10 GB e **não existe imagem r36.4 pronta**. Buildar no cliente é inviável. Compilar os parsers dentro do Dockerfile elimina a maior fonte de divergência entre boxes |
| **I2** | **`jetson-device-skills` + `jetson-bsp-skills`** (NVIDIA) | `jetson-diagnostic` vira a coleta automatizada do `REGRAS §1/§4`; `jetson-package` endereça a landmine de torch SBSA. O BSP skills põe **fan/nvpmodel/clocks na imagem flasheada** — resposta estrutural ao provisionamento manual. Insumo novo pro **ADR-0040** |
| **I3** | **INT8 com precisão mista** em RF-DETR/D-FINE (backbone INT8, cabeça/atenção FP16) | É o **único ganho de quantização real no Ampere** — FP8 e NVFP4 não existem no silício do Orin. ⚠️ medir mAP, não tratar como flag |
| **I4** | **CUDA graphs** para overhead de launch | Ganho maior justamente no nosso perfil: modelos pequenos, FPS alto, muitos streams |
| **I5** | **Port JP6.2 → JP7.2** | ⛔ **Bloqueado** até o DS 9.1 sair e ser validado em SM87. Quando vier: P0-CRÍTICO de semanas (Ubuntu 22→24, kernel 5.15→6.8, CUDA 12.6→13.2, TRT 10.3→10.13+, **todos os engines reconstruídos**) |
| **I6** | **Registry declarativo de operation-types** | Torna verdadeira a promessa "configurar sem tocar no código". ⚠️ **decisão** (§3) |

---

# PARTE 3 — DECISÕES QUE TRAVAM FEATURES

Nenhuma destas é implementação. São escolhas suas, e cada uma bloqueia uma feature acima.

| # | Decisão | Opções | Bloqueia |
|---|---|---|---|
| **D1** | **Registry de operation-types: estático ou declarativo?** | Estático (Python + deploy, simples) · Declarativo (schema em banco, cumpre a promessa, exige UI schema-driven). **Meio-termo do Agent Studio:** plugin declara params + type hints + docstring → **UI se gera sozinha**. Não elimina o deploy, mas elimina o trabalho de UI por tipo | **F5, I6** — e `attention_points`/`stage_timer` **bloqueiam a RVB** |
| **D2** | **DeepStream: gerar config do banco, ou pipeline lê config em runtime?** | Gerar = simples, reinicia pipeline · Runtime = elegante, permite hot-reload. `deepstream/` está vazio → **decisão em aberto, não retrabalho** | **F7** |
| **D3** | **`/edge/detections` vs `/events/ingest`** — qual é o canônico? | O agent chama `/detections` (não existe); `/events/ingest` existe sem cliente. **Um morre** | **F1, F3** |
| **D4** | **Dois enrollments incompatíveis** — qual sobrevive? | `devices/` (claim code, JWT HS256, público) vs `edge/enroll` (token opaco, SHA-256). `devices/` é órfão | **F8, S6** |
| **D5** | **`serve_hls`: qual abordagem?** | Token de playback assinado de vida curta · cookie scoped ao tenant · proxy autenticado. Não deixar nu, não quebrar o player | **A18** |
| **D6** | 🔴 **Cosmos Reason2: aceitar a licença NVIDIA?** | A **Seção 3.2 exige atribuição "Built on NVIDIA Cosmos"** em produtos derivados → **colide com o white-label (ADR-0035)**. Ganha +27,5 pts em "Smart Spaces" sobre o Qwen3-VL. **Plano B: Qwen3-VL-8B, Apache 2.0, roda no Orin NX** | **P2, P4** — precisa de parecer jurídico |
| **D7** | **Sinalização automatizada de suspeição × LGPD** | O card de Bias do Cosmos declara *"adversely impacted groups: None"*. Output nunca deve ser "pessoa X é suspeita" — deve ser **descrição factual** ("3+ pessoas paradas junto ao veículo por >2min") com humano no loop | **P2** |

---

# PARTE 4 — ORDEM SUGERIDA

**Esta semana (AGORA):**
1. A1 senha · A2 fan · A3 verificar DS 9.1 — os três são rápidos e A1 é bloqueante
2. A17/A19/A20 segurança (escopos + cross-tenant) — prompt pronto, e fica mais caro a cada rota nova
3. A13–A16 device auth + testes (F0) — destrava tudo que vem depois
4. A4–A7 docs que mentem + landmines no doc vivo
5. A22 consolidar PRs na develop

**Próximas duas semanas:**
6. A10–A12 RAM (com o cuidado do DISPLAY) · A8 congelar baseline
7. **F1** `config/poll` — a ponte
8. **F2** fechar o laço decorativo (é o que faz a UI existente virar verdade)
9. A24 promoção develop→staging, como evento próprio

**Depois, na ordem do valor pra RVB:**
10. **D1** decidir o registry → **F5** operation-types (bloqueia a RVB)
11. **F3** comandos · **F4** modelo pro device · **F6** motor de operações
12. **I1** golden image + **I2** jetson skills (provisionamento reproduzível — vira crítico no 2º cliente)
13. **P1** NanoOWL pré-anotação (o dataset de qualidade da RVB não existe — este é caminho crítico)
14. **D6** parecer jurídico → **P2** VLM adjudicador
15. **I3** INT8 misto · **I4** CUDA graphs
16. **I5** port JP7.2 — só quando o DS 9.1 existir

> **Observação de prioridade:** o item que mais atrasa a RVB hoje não é técnico — é o **dataset de qualidade
> rotulado, que não existe**. Todo o shootout (RF-DETR × D-FINE × RT-DETRv4) roda sobre PPE como proxy. **P1
> (pré-anotação zero-shot) ataca exatamente esse gargalo** e por isso está mais alto do que o valor aparente.
