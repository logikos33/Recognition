# RELATÓRIO F5 — Sessão F5-PESADA (29→30/08/2026)

Migração pesada do front: Estúdio + Admin + Acesso + Kiosk + Mobile no front novo (`/novo`), com paridade auditada, carimbos e demolição zero fora do provado. **16 PRs abertos, 15 mergeados na develop** numa noite, zero interferência nas outras pistas, zero merge fora do rito.

## Placar de PRs (todos com CI 23/23 verde no merge)

| PR | tema | resultado |
|---|---|---|
| #571 | bundle canônico de design (30 pranchas + contrato-dados + lk-loader) | ✅ mergeado — todas as pistas enxergam |
| #572 | Estúdio PR-A: gate `frames:annotate` + layout + Dados (galeria+anotador) | ✅ mergeado |
| #574 | Estúdio PR-B: Cobertura + Classificar + 2 débitos do cético | ✅ mergeado |
| #577 | Estúdio PR-C: Classes (polaridade 3 estados, reorder=tecla) | ✅ mergeado |
| #580 | Estúdio PR-D: Modelos + Modelos por câmera | ✅ mergeado |
| #583 | Estúdio PR-E: Treino ao Vivo (épocas reais, selo simulado) | ✅ mergeado |
| #584 | Acesso: /novo/entrar·esqueci-senha·redefinir (aditivo; antigo intocado) | ✅ mergeado — cético de auth ZERO bloqueios |
| #586 | Paridade: selo SIMULAÇÃO no modelo + origin + dono + module payload | ✅ mergeado |
| #589 | Carimbos @migrado-para + PARIDADE doc + PEDIDOS + LISTA-DESIGN | ✅ mergeado |
| #591 | Admin núcleo: gate `admin:panel` + Visão geral honesta | ✅ mergeado |
| #594 | Admin: Dispositivos (claim-codes) + Auditoria (sem raw fetch) | ✅ mergeado |
| #595 | Admin: Tenants + white-label com clamp real + Usuários | ✅ mergeado |
| #596 | Kiosk re-vestido /novo/tablet/:station (máquina reusada verbatim) | em CI no fechamento deste relatório |
| #597 | Mobile <768 (Eventos/Detalhe/Ações/Dashboard + e2e Chromium real) | em CI no fechamento deste relatório |

## Tela a tela (evidência)

- **/novo/estudio/{dados,cobertura,classificar,classes,treino,modelo,modelos-por-camera}** — 7 sub-rotas, lateral própria 220px, gate SEM PERMISSÃO (analyst/viewer barrados; e2e por perfil 13/13). Núcleo `components/annotation|training` compartilhado por import, `/epi/training` antigo intocado. Paridade: 43 itens auditados por cético opus — 3 bloqueadores achados e QUITADOS (selo simulação/origin/dono), 1 latente (payload `module`) corrigido, adiamentos nomeados no carimbo. Evidência: `docs/migration/PARIDADE-ANTIGO-VS-NOVO.md` §Estúdio.
- **/novo/entrar · /novo/esqueci-senha · /novo/redefinir-senha** — aditivos; catch-all deslogado SEGUE no Login antigo (cadastro do dia D intacto — cético provou diff zero no antigo). Textos batem com o backend (TTL 30min confirmado; régua real mín. 6). Elo aberto: e-mail de reset ainda aponta pra rota antiga (pedido #3).
- **/novo/admin/{,tenants,tenants/:id,usuarios,dispositivos,auditoria}** — superadmin-only; Visão geral omite os KPIs que o backend devolve hardcoded 0 (zero fingindo medição); white-label com prévia clampada (`corDeMarcaUsavel`); convite = senha temporária UMA vez (o `first_access_token` do Redis é infraestrutura morta — nenhuma rota consome); Dispositivos só com o que existe (claim-codes; listagem/revogação sem backend → omitidas com nota); Auditoria matou o raw fetch da antiga.
- **/novo/tablet/:station** — kiosk re-vestido; 7 estados; hook e decisão de estado verbatim; **rota antiga byte-idêntica** (RVB produção).
- **Mobile <768** — 4 telas de leitura; prova em Chromium real 390×844 (3/3, sem scroll horizontal); 3 bugs de layout pré-existentes corrigidos.

## Manifesto (contagem no fechamento)

PENDENTE 149 → (demolição lote 1 da leve removeu 6 do universo) · MIGRADO 4+3 do Estúdio · SUBSTITUIDA/SEM-DESENHO conforme `docs/migration/MANIFESTO-FRONT-ANTIGO.md` (gerado, nunca manual). Telas F5 carimbadas: TrainingPage(.css), ModuleClassesPage. Login/Tablet* antigos NÃO carimbados de propósito: seguem recebendo o tráfego real (flip é rodada futura; draft #592 da leve aguarda GO de quinta).

## O que espera DESIGN (`docs/migration/LISTA-PARA-O-DESIGN-F5.md`)

Re-skin do canvas (AnnotationStudio/CropClassifier) · áreas IA e Dataset da prancha · R4 catálogo de modelos · admin visão geral (aba própria) · troca obrigatória hi-fi · parede TV · CTA "Solicitar acesso" · divergências registradas (estudio:acesso→frames:annotate; Cobertura/Classificar como sub-rotas extras; 6 telas do kiosk sem header câmera/rede).

## O que espera BACKEND (`docs/migration/PEDIDOS-AO-BACKEND-F5.md`)

10 pedidos, destaques: share links (design pronto, zero backend) · login devolver `force_password_reset` · e-mail de reset apontar pro fluxo novo no flip · TV/parede por site · dashboard admin com KPIs reais (hoje hardcoded 0) · listagem/revogação de devices · 🔒 needs-human: `GET /api/training/jobs` vaza `callback_token` e escopa por user_id.

## O que falta para o 100% absoluto

1. **Prova visual por perfil no DEV** (régua do OK): bloqueada em credencial (E2E_ANNOT_PASSWORD/conta de teste — pedida ao Vitor). O que já prova sem ela: e2e por perfil com sessão injetada (13/13), e2e mobile em Chromium real, suítes 1119+ verdes, DEV redeployado com tudo.
2. **Aceite de demo do Estúdio** (história do volante: captado→dificuldades→caixas→Enter) — passe visual humano no DEV; URL fixa `/novo/estudio/dados`.
3. Merges finais #596/#597 (CI em curso no fechamento).
4. TV: não entrou por decisão (sem desenho/rota/endpoint — registrada).
5. Débito estrutural: Shell sem colapso de sidebar <768 (236px fixos) — ticket próprio.
6. Flip do Acesso e demolição do Estúdio antigo: rodadas futuras, pós-quarta, com a leve (#592).

## Custos e método

~15 subagentes (sonnet implementação, haiku leitura, opus SÓ cético crítico — 4 auditorias), ~3,5M tokens de subagentes. 3 CIs vermelhos na noite, todos diagnosticados por log e corrigidos (offbrand em fixture; manifesto 2× — lição: **regenerar o manifesto por ÚLTIMO**). Toda mutação de teste provada (falha-antes/passa-depois). Convivência: 4 pistas simultâneas, zero pisada — uniões de conflito só nos 2 arquivos de integração previstos.
