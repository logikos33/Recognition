# ESTADO-F5 — Sessão F5-PESADA (Estúdio + Admin + Acesso + TV + Kiosk + Mobile)

> Reentrante: TODA retomada relê este arquivo antes de agir. Evidência = caminho de arquivo/screenshot, nunca conteúdo colado.

## Identidade
- Worktree: `~/Logikos-mutirao/wt-f5` (base `f5/base` = origin/develop @ `230f7382`, 29/08). Branch temático por PR.
- Faixa desta pista: `apps/frontend/src/app/{estudio,admin,acesso,kiosk}` + edições CIRÚRGICAS em `RotasNovas.tsx`, `navPorPerfil.ts`, `App.tsx` (só ramo deslogado, PR acesso), `lk.css.ts` (+TELA_ESTREITA).
- ⛔ NÃO toca: `services/api` (pista semana-cliente) · `components/annotation|training/*` INFRA (congelado; bugfix = PR separado) · `/admin` e `/tablet` antigos · checkout ~/Documents (iCloud).

## Regras de merge (inegociáveis)
- Antes de QUALQUER merge: ler `~/Logikos-mutirao/wt-semana/tools/agent-driver/tasks/ESTADO-SEMANA-CLIENTE.md` + `/livez` com `running_jobs==0` + fila do worker vazia + aviso aqui.
- Antes de merge que toque `RotasNovas.tsx`/`navPorPerfil.ts`/`App.tsx`: `git fetch` + varrer branches remotas recentes por trabalho da migração-leve nesses arquivos (a mensagem direta a ela expirou sem aprovação em 29/08; este ESTADO é o canal). Colisão detectada = sequenciar depois dela ou adiar o arquivo.

## Sync às outras pistas (respostas que a semana-cliente pediu, 29/08)
(a) Em voo F5: PR #571 (bundle docs) + SR1 Estúdio PRs A–E até terça 18h. (b) Admin/usuários no front novo: virá em `/novo/admin/usuarios` (admin:panel), NÃO antes de quarta e sem pressa — cadastro do dia D é na tela ANTIGA `/admin/users` congelada. (c) Aba de escopo (CameraModelScope): F5 embrulha em `/novo/estudio/modelos-por-camera` SEM editar o núcleo INFRA; `/epi/training` antigo intocado.
- 🔴 CONGELAMENTO: terça 02/09 18h → quarta pós-onboarding = ZERO merge na develop (trabalho em branch, PRs verdes acumulam). Exceção única: hotfix do dia D com aviso.

## Plano aprovado (29/08, com emendas do Vitor)
- Plano completo: `~/.claude/plans/prompt-sess-o-eventual-noodle.md`. Emendas: bundle F5 é referência CANÔNICA quando chegar (v3 é ancestral; divergência → bundle vence e se registra); `--st-*` do bundle mapeiam para tokens reais de `lk.css.ts` (convergir por token, não criar paralelo); TV/share-links/troca-obrigatória = não construir + pedidos; kiosk com rota antiga intocada; `@paridade-pendente` ≠ MIGRADO.
- SR1 Estúdio: compartilhar núcleo INFRA via wrappers em `src/app/estudio/`; renascem hub/Modelo/Treino/Classes; gate `can('frames:annotate')` no layout + `SemPermissao`; abas→sub-rotas; PRs A(guard+layout+Imagens)→B(Cobertura+Classificar)∥C(Classes)∥D(Modelo+ModelosPorCamera)→E(Treino+carimbos).
- SR2: Admin 6 áreas sob `admin:panel` em `/novo/admin/*`; Acesso 3 rotas ADITIVAS deslogadas (catch-all antigo fica); TV não entra.
- SR3: Kiosk re-skin em `/novo/tablet/:station` (máquina de estados reusada verbatim); Mobile <768 em Eventos/EventoDetalhe/Acoes.

## ✅ Bundle de design F5 — NO REPO (PR #571)
- Resolvido 29/08 ~19h40: bundle achado em `/Users/vitoremanuel/Logikos Recogntion/Recognition/docs/design/handoff-f5/` (cópia do Cowork; o de ~/Downloads existe mas o sandbox nega leitura — lição: `Operation not permitted` ≠ inexistente, find/Spotlight silenciam). Commitado em `docs/design/handoff-f5/` (41 arquivos, commit `234d2ecd`, branch `docs/handoff-f5-bundle`, **PR #571** aguardando CI). Bundle = referência CANÔNICA F5; v3 é ancestral.
- Reconciliação de tokens FECHADA: `--st-ok/atencao/nc` do bundle = `lk.estado.{ok,atencao,nc}` byte-idênticos (#3ECF8E/#E8A13C/#E5484D). Zero paralelo a criar. README canônico confirma rotas do plano (/estudio/*, /tv/:site, /tablet/:station, admin com share links, mobile eventos/ações leitura) e EmptyState-com-CTA como padrão (convergir VazioPainel→EmptyState na F5).
- Achado novo do README: Evento Detalhe desenha "Compartilhar com expiração 1h/24h/7d + permissão ver/ver+baixar" → reforça pedido-ao-backend share links (design existe, backend não). Verificação desenha tecla "A" = enviar pra fila do Estúdio (extensão de tela F3 — registrar, não fazer agora).

## Log
- 2026-08-29 ~19h — Fase 0: worktree wt-f5 criado; agentes leitor/implementador/cetico/arquiteto; ESTADO-F5. Exploração e plano completos (3 leitores + 2 arquitetos). Plano aprovado pelo Vitor com emendas.
- 2026-08-29 ~19h45 — Bundle F5 commitado e PR #571 aberto (docs-only). `/livez` DEV saudável (`running_jobs:0`, commit=develop 230f7382). ESTADO-SEMANA-CLIENTE lido: nada mergeado por eles; congelamento de terça = congelamento de MERGE (confirmado); pedido de sync deles à migração-leve SEM resposta → mandei sync completo à sessão `frontend-migration-logikos-bd4acf-26` (faixas, colisão RotasNovas/navPorPerfil, bundle, respostas dos 3 pontos). Medição estática dos endpoints SR1 concluída (duas listas de modelos user-scoped vs tenant-scoped; classes[] na raiz; jobs vazam callback_token — ver Achados).
- 2026-08-29 ~20h15 — **#571 MERGEADO** (bundle canônico na develop). Pranchas destrinchadas: Estúdio = 6 áreas (Dados/Classes/IA/Dataset/Treinos/Modelos) + anotador overlay + sidebar própria 220px; DIVERGÊNCIAS registradas: (1) gate desenhado "estudio:acesso" não existe → chave real `frames:annotate`; (2) Cobertura e Classificar não têm aba própria na prancha — decisão de encaixe fica pro PR-B com arquiteto; (3) CTA "Solicitar acesso" sem backend → não implementado, registrado. Admin prancha: 8 seções incl. Dispositivos=claim-codes (backend EXISTE: /api/devices/claim-codes) e Share Links (backend NÃO existe). Acesso prancha: login/esqueci/troca-obrigatória (troca segue bloqueada por backend). contrato-dados.js validado: 421 ops (207 FRONT-ATUAL/122 GAP/61 ÓRFÃO).
- 2026-08-29 ~20h40 — **PR-A implementado por mim no main loop** (subagente implementador herdou plan mode e não pôde editar — plano dele em ~/.claude/plans/...-agent-a75e157df846df621.md foi seguido): branch `f5/estudio-pr-a`; criados SemPermissao.{tsx,css.ts,test.tsx} (shell), Estudio.{tsx,css.ts,test.tsx} + Dados.{tsx,css.ts,test.tsx} (app/estudio); editados Shell.tsx (SEM_BARRA_LATERAL + nav concat), navPorPerfil.{ts,test.ts} (NAV_ESTUDIO, FlaskConical), RotasNovas.tsx (rota aninhada estudio/dados), front-novo-perfis.spec.ts (MENU + Estúdio). Deep-link novo por URL (?camera=/?status= com guard exaustivo). `npm ci` do worktree em curso → tsc/vitest na sequência.
- Próximo: verificação (tsc → vitest área → suíte) → teste de mutação do gate → commit → cético → push/PR.

## Achados para outras pistas (não são meus arquivos)
- 🔒 `GET /api/training/jobs` VAZA `callback_token` na listagem (training/routes.py) e escopo é por user_id, não tenant — registrar como issue de segurança para a pista de backend (risk:security = fila para revisão humana, não mexo).
- `GET /api/classes` devolve `classes[]` na RAIZ (fora do envelope data) — bug de contrato conhecido; front novo vai consumir como está e registrar.

## Placar de PRs
| PR | tema | branch | estado |
|---|---|---|---|
| #571 | docs: bundle canônico F5 | docs/handoff-f5-bundle | CI rodando → merge quando verde |

## Pedidos-ao-backend (a registrar em doc na 1ª leva)
1. Share links admin (zero backend). 2. Login devolver `force_password_reset`. 3. Parede kiosk por site (reforço DECISOES 29/08). 4. TV por site `/tv/:site`.

## LISTA-PARA-O-DESIGN (a registrar via build_migration_map + doc)
Estúdio 7 sub-telas + re-skin canvas + R4 catálogo + home trainer · esqueci/redefinir/troca obrigatória · admin visão geral · share links · parede TV por site · Kiosk RVB · bundle F5 ausente do repo.
