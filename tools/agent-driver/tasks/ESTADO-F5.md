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

## Adendos do Vitor (leis da sessão)
- v2 29/08: origin é a verdade (fetch antes de rodada/merge) · varrer inbound (PRs abertos+branches+ESTADOs) antes de criar qualquer coisa · rebase 1×/dia e pré-PR · numeração no momento do merge · registrar SHA-base+inbound no ESTADO.
- v3 29/08 (economia máxima, orçamento 72%): haiku default p/ mecânico/leitura; sonnet só não-trivial; opus SÓ cético crítico (security/demolição/flip/paridade) · ⛔ Read inteiro >200ln · saída de agente ≤20ln tabela · suíte da área 1×/PR, completa 1×/sub-rodada+pré-merge · screenshots só aceite final · ESTADO em delta · relatórios telegráficos · modo-reserva a ~85% (só P1, opus congelado exceto security).

## Log
- 2026-08-29 ~19h — Fase 0: worktree wt-f5 criado; agentes leitor/implementador/cetico/arquiteto; ESTADO-F5. Exploração e plano completos (3 leitores + 2 arquitetos). Plano aprovado pelo Vitor com emendas.
- 2026-08-29 ~19h45 — Bundle F5 commitado e PR #571 aberto (docs-only). `/livez` DEV saudável (`running_jobs:0`, commit=develop 230f7382). ESTADO-SEMANA-CLIENTE lido: nada mergeado por eles; congelamento de terça = congelamento de MERGE (confirmado); pedido de sync deles à migração-leve SEM resposta → mandei sync completo à sessão `frontend-migration-logikos-bd4acf-26` (faixas, colisão RotasNovas/navPorPerfil, bundle, respostas dos 3 pontos). Medição estática dos endpoints SR1 concluída (duas listas de modelos user-scoped vs tenant-scoped; classes[] na raiz; jobs vazam callback_token — ver Achados).
- 2026-08-29 ~20h15 — **#571 MERGEADO** (bundle canônico na develop). Pranchas destrinchadas: Estúdio = 6 áreas (Dados/Classes/IA/Dataset/Treinos/Modelos) + anotador overlay + sidebar própria 220px; DIVERGÊNCIAS registradas: (1) gate desenhado "estudio:acesso" não existe → chave real `frames:annotate`; (2) Cobertura e Classificar não têm aba própria na prancha — decisão de encaixe fica pro PR-B com arquiteto; (3) CTA "Solicitar acesso" sem backend → não implementado, registrado. Admin prancha: 8 seções incl. Dispositivos=claim-codes (backend EXISTE: /api/devices/claim-codes) e Share Links (backend NÃO existe). Acesso prancha: login/esqueci/troca-obrigatória (troca segue bloqueada por backend). contrato-dados.js validado: 421 ops (207 FRONT-ATUAL/122 GAP/61 ÓRFÃO).
- 2026-08-29 ~20h40 — **PR-A implementado por mim no main loop** (subagente implementador herdou plan mode e não pôde editar — plano dele em ~/.claude/plans/...-agent-a75e157df846df621.md foi seguido): branch `f5/estudio-pr-a`; criados SemPermissao.{tsx,css.ts,test.tsx} (shell), Estudio.{tsx,css.ts,test.tsx} + Dados.{tsx,css.ts,test.tsx} (app/estudio); editados Shell.tsx (SEM_BARRA_LATERAL + nav concat), navPorPerfil.{ts,test.ts} (NAV_ESTUDIO, FlaskConical), RotasNovas.tsx (rota aninhada estudio/dados), front-novo-perfis.spec.ts (MENU + Estúdio). Deep-link novo por URL (?camera=/?status= com guard exaustivo). `npm ci` do worktree em curso → tsc/vitest na sequência.
- 2026-08-29 ~20h10 — **PR #572 aberto** (f5/estudio-pr-a, base c399155b). Verificação: tsc 0 · vitest 1026/1026 · área 79/79 · e2e perfis 13/13 · mutação do gate provada. Cético (opus): alegações 1-4,7-8 CONFIRMADAS (diff mecânico do refill = idêntico); **1 BLOQUEIO achado e corrigido** (`in` deixava passar toString/valueOf do protótipo → white screen por URL; agora hasOwnProperty.call + teste) + layout (minHeight/padding duplicados, Suspense local) — commits 993c4c79/f2615e79. Aguardando CI → merge.
- DÉBITOS registrados pelo cético (não bloqueiam #572): (a) coexistencia.test não varre rotas ANINHADAS (ponto cego novo — corrigir teste-régua no PR-B); (b) `?camera=` sem validação (falha macia); (c) refill/pedirMaisFila coberto por leitura+diff, sem teste próprio no arquivo novo (adicionar teste com continuacao fake no PR-B); (d) lateral do Estúdio nasce DENTRO da caixa 1280/padding do Shell — aceite visual no navegador pendente; (e) `frames:annotate` cru na tela SemPermissao (jargão; alternativa é pergunta ao design).
- DECISÃO de encaixe (minha, registrada p/ design): Cobertura e Classificar NÃO têm aba própria na prancha de 6 áreas — entram como sub-rotas extras da lateral do Estúdio (função do delta > desenho; divergência para a LISTA-PARA-O-DESIGN), em vez de espremê-las numa área onde não cabem.
- Próximo: CI #572 → rito → merge; PR-B (Cobertura+Classificar; considerar #498 em voo no CropClassifier) ∥ PR-C (Classes).

- 2026-08-29 noite — **SR1 FECHADA + Acesso no ar**: 8 PRs mergeados (#571 bundle · #572 A · #574 B · #577 C · #580 D · #583 E · #584 Acesso · #586 selos/paridade) + carimbo em CI. /novo/estudio completo (Dados·Cobertura·Classificar·Classes·Treinos·Modelos·Modelos-por-câmera), paridade 43 itens auditada por cético opus (3 bloqueadores quitados; adiamentos nomeados), Acesso aditivo com cético de auth ZERO bloqueios. Adendos v2/v3 do Vitor aplicados (economia: implementações sonnet, opus só cético crítico; inbound varrido a cada leva). Convivência: leve mergeou #585 (6→MIGRADO) e prepara f5leve/pr-b-demolicao — sync direto expirou 2×, canal = este ESTADO; lição operacional: MANIFESTO se regenera POR ÚLTIMO. CIs vermelhos da noite: 3, todos diagnosticados e corrigidos (offbrand em fixture; manifesto 2×).
- PENDENTE para a régua do OK: prova visual por perfil no DEV (bloqueada em credencial — pedida ao Vitor), aceite de demo (história do volante) até segunda à noite, SR2 admin (nucleo→tenants/usuarios→dispositivos/auditoria), SR3 kiosk+mobile, RELATORIO-F5.md.

## Achados para outras pistas (não são meus arquivos)
- 🔒 `GET /api/training/jobs` VAZA `callback_token` na listagem (training/routes.py) e escopo é por user_id, não tenant — registrar como issue de segurança para a pista de backend (risk:security = fila para revisão humana, não mexo).
- `GET /api/classes` devolve `classes[]` na RAIZ (fora do envelope data) — bug de contrato conhecido; front novo vai consumir como está e registrar.

## Placar de PRs — FINAL (15 mergeados, 0 abertos)
#571 bundle · #572 A · #574 B · #577 C · #580 D · #583 E · #584 Acesso · #586 selos · #589 carimbos · #591 admin-nucleo · #594 dispositivos+auditoria · #595 tenants+usuarios · #596 kiosk · #597 mobile · (+ #585/#588/#590/#593 da migração-leve na mesma janela, sem colisão). Relatório completo: docs/reports/RELATORIO-F5.md.

## SESSÃO F5-PESADA — FECHADA em 30/08 ~02h
Aceite de código: Estúdio(7)+Admin(6)+Acesso(3)+Kiosk+Mobile no ar na develop; paridade auditada e carimbada; manifesto verdadeiro; listas design/backend entregues. ABERTO para humano: prova visual por perfil no DEV (credencial), aceite de demo do volante (/novo/estudio/dados), gates de terça 18h. Retomada: reler este arquivo + RELATORIO-F5.md.


## Pedidos-ao-backend (a registrar em doc na 1ª leva)
1. Share links admin (zero backend). 2. Login devolver `force_password_reset`. 3. Parede kiosk por site (reforço DECISOES 29/08). 4. TV por site `/tv/:site`.

## LISTA-PARA-O-DESIGN (a registrar via build_migration_map + doc)
Estúdio 7 sub-telas + re-skin canvas + R4 catálogo + home trainer · esqueci/redefinir/troca obrigatória · admin visão geral · share links · parede TV por site · Kiosk RVB · bundle F5 ausente do repo.
