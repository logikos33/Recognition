# LISTA PARA O DESIGN — o que o backend exige que o novo front construa ou melhore

> Gerado por `tools/build_migration_map.py design` (HEAD `98bff30e51283399c0d70554be760b56824af12e`) a partir dos JSONs verificados por domínio e dos fluxos do front atual. Linguagem de **produto** (telas/fluxos), não de rota. O anexo no fim dá a rastreabilidade rota→item para quem for implementar. **Não edite à mão** — corrija `docs/migration/inventory/domains/*.json` e regere.

Como usar: cada item é uma tela/fluxo que o backend já suporta (ou exige) e que o front atual não cobre, cobre mal, ou cobre com bug. O design decide `cobre` / `não cobre` por item; a decisão volta para a coluna **NOVO FRONT** do mapa-contrato. Itens marcados **[pré-requisito backend]** dependem de correção no servidor antes de o front conseguir entregar.

## 0. Transversal (vale para todas as telas)

### Páginas (pages/)

1. **Autenticação**: login e-mail/senha, criar conta, esqueci/redefinir senha por link com token; sessão persistida em storage; logout local; tratar 401 com redirect único (single-flight) e 429 com mensagem amigável.
2. **Pós-login por papel**: superadmin → `/admin`; demais → seleção de módulo (EPI sempre; Qualidade/Carregamento conforme `modules` do tenant); sidebar por módulo; itens Admin/Configurações só superadmin; "Treinamento" só se o tenant tem `epi|quality|counting`.
3. **Superadmin operando clientes**: "ver como" usuário (30 min, banner + sair), "assumir contexto" de tenant (30 min, banner danger, renovação proativa antes de expirar, reassumir após expirar), detecção de câmera cross-tenant (404 → inventário → banner/auto-assume).
4. **White-label**: branding por tenant (cores, nome, logo, favicon) aplicado antes da UI; tema claro/escuro do usuário.
5. **Dashboard EPI**: KPIs (câmeras ativas, conformidade 24 h c/ detalhamento por EPI, alertas hoje/hora, modelo ativo + mAP50) com polling 30 s; grade VMS estilo DVR (layouts 1x1…1+7, arrastar, presets, fullscreen, rótulos) persistida por usuário; widgets BI reordenáveis/ocultáveis (timeline, distribuição, top câmeras, últimos alertas, registro de eventos) por período 24h/7d/30d.
6. **Live view**: sempre obter a URL HLS do backend (`/stream/start`, token no path, TTL 1 h), renovar antes de expirar, recuperar de 410/404/425 re-assinando, parar de buscar segmentos em aba oculta, sessão única por câmera, fallback Safari, overlay de detecções por WebSocket com `subscribe_camera`.
7. **Câmeras**: lista + detalhe; onboarding em 4 passos com **probe** antes de salvar (sugere substream/codec); edição em 4 passos com salvar→testar (5 checks); testar conexão; iniciar/parar stream; arquivar/restaurar (nunca apagar); FPS/qualidade/substream de coleta com aviso de carga baseado em telemetria do site; modelo por módulo por câmera (admin); atalhos p/ operações e cenário.
8. **Triagem de canais**: ordenação por canal, rename inline, confirmar posição, ativar/arquivar em lote, preview ao vivo de uma câmera por vez, miniatura por snapshot sob demanda (refresh + poll) com fila de concorrência, totalizador de upload/egress.
9. **Monitoramento VMS**: abas por módulo, cards lazy (só visíveis pedem stream), drawer com feed/logs ao vivo/desempenho.
10. **Alertas**: histórico paginado com filtros (câmera, datas, tipo, status) via query string, deep-link do sino com destaque, reconhecer, ver snapshot presignado, exportar CSV; sino com pendentes (30 s).
11. **Treinamento**: galeria paginada (60) com facetas, filtros (status/curadoria/propostas pendentes/câmeras/origem), seleção múltipla, curadoria com desfazer, upload multipart de imagens; **estúdio keyboard-first** com autosave (debounce + flush + keepalive), fila congelada com reabastecimento, propostas de IA (aprovar/rejeitar), dúvida, zoom/pan, undo/redo, criar classe inline, guidelines; **classificação por recorte** (multilabel por tipo de EPI, fila por carência, prefetch keyset, persistência local anti-401, desfazer); **matriz de cobertura** com deep-links; modelos (ativar com gate campeão×desafiante, configurar cenário 6 passos, origem/simulado); modelos+escopo por câmera (permissão `training:approve`); treino ao vivo (iniciar/parar, status 3 s + socket, logs, sparklines, aviso GPU); classes do módulo (rename, cor, arquivar/restaurar, reordenar = tecla); propagação semeada e busca por conteúdo com **preflight de custo → confirmar → barra de progresso (4–5 s) → revisar/promover**.
12. **Investigação de eventos**: filtros (módulo, classes, câmeras, período, confiança), timeline por bucket, lista paginada com preview presignado.
13. **Verificação humana**: fila `needs_human` (15 s) com aprovar/rejeitar.
14. **Contagem**: iniciar/encerrar sessão por câmera, stats 3 s, totais finais; validação/aceite (relatório por período/baia/limiar, editar contagem manual, aceitar/rejeitar).
15. **Operações por câmera**: CRUD de operações por tipo (catálogo do módulo) com desenho de ROI/linha sobre o vídeo, status ao vivo via socket, exclusão com confirmação por nome.
16. **Cenário por câmera**: hoje quebrado — novo front deve usar `GET /api/v1/cameras/<id>/scenario` e `GET /api/v1/scenarios/operation-types`.
17. **Edge**: admin troca `deployment_mode` dos sites; dashboard integrado (curvas de treino + telemetria ao vivo); página oculta de observabilidade do Jetson (superadmin) com comandos assíncronos (query/snapshot/logtail → poll de comando), thresholds.
18. **Assistente (chat)** SSE com histórico local, escondido no estúdio.
19. **Carregamento (fueling)**: dashboard/baias/eventos com polling 30 s, demo mode superadmin, validação de contagem.
20. **Saúde**: rodapé DB/Redis/câmeras ativas (admin), atalho p/ observability (superadmin).
21. **Relatórios**: hoje inexistente — decidir se o novo front consome `/api/reports/*` ou mantém placeholder.
22. **Transversal**: toasts traduzidos/deduplicados, silenciar erros de polling em background, timeouts (15 s REST / 30 s download), polling com backoff e pausa em aba oculta.

### Módulos (modules/)

**Transversal**
- Gate de rota por papel (`superadmin` → `/admin/*`; redirect raiz superadmin→`/admin`, demais→`/modules`) e por módulo habilitado do tenant (`quality`), ambos derivados do payload do login (`role`, `modules`, `permissions`) — sem chamada extra.
- Sessão: token em storage, 401 → logout; **exceto** quando há "ver como"/"contexto assumido" ativo: restaurar sessão original, sinalizar expiração e oferecer "Reassumir".
- Dois modos temporários de superadmin, mutuamente exclusivos, com banner global persistente: **Ver como usuário** (30 min, auditado, `POST …/impersonate` + `POST /api/v1/impersonation/stop`) e **Assumir contexto de tenant** (30 min, renovação proativa 5 min antes via `/renew`, retry 30 s, catch-up ao voltar à aba).
- Envelope `{success,message,data}`; erros com toast; downloads autenticados (CSV) via blob, nunca token em query string.

**Admin (superadmin)**
- Dashboard de plataforma com métricas (tenants ativos, usuários, câmeras online, alertas 24 h, aprovações pendentes, tickets abertos, MRR) + workers online/fallback/offline + eventos críticos recentes, atualizado a 30 s; badges de aprovações/tickets no menu.
- Tenants: listar/buscar, criar (nome, slug, plano, módulos do catálogo) com exibição única de `admin_email`+`temp_password`; detalhe com abas Visão geral, Usuários (criar, ativar/desativar, permissões, ver como), Worker, Módulos (toggle), Configurações (assentos, sessão única, rate limit, retenção padrão), Armazenamento & Integrações por tenant, Feature flags do tenant, Histórico de plano; suspender (com motivo)/reativar.
- Usuários globais: busca/filtro por role/paginação 20; wizard 3 passos (dados → acesso com módulos do tenant, role customizada, expiração → credenciais mascaradas com copiar); reset de senha com senha temporária exibida uma vez; ativar/desativar.
- Permissões: matriz a partir do registry; roles customizadas por tenant (CRUD, checkboxes por grupo); gaveta por usuário com role base, role customizada e overrides tri-state (herdar/permitir/negar) + encerrar sessões.
- Planos (CRUD c/ módulos permitidos, limites, preço por câmera, features por módulo, aprovação de treino obrigatória, ativo) e retenção de vídeo por tenant (tiers 1/7/30/90).
- Feature flags globais e por tenant.
- Aprovações de treinamento (lista por status, aprovar com notas, rejeitar com motivo).
- Tickets: lista com filtros **e** detalhe/resposta/estatísticas (hoje inacessível).
- Comunicados (criar/arquivar; e exibição ao cliente com "lido", hoje sem UI).
- Auditoria com filtros e export CSV.
- Observabilidade com abas (visão geral, infra, frota edge com drill-down de heartbeats, workers com restart, streams agregado), intervalo de polling global persistido (incl. "pausado"), janela histórica, "coletar agora".
- White-label por tenant: lista com previews, editor (cores primária/acento, superfícies, nome do produto, logo e favicon com upload), preview ao vivo, reset; sandbox de paleta.
- Integrações de plataforma e por tenant (R2, Vast.ai, GPU genérico, notificação, BYO-DB): salvar sem reexibir segredo (`••••last4`), testar conexão, remover; deep-link `?type=`.
- Versões/Registry (criar, rollback com confirmação) e Changelog (filtros, criar).
- Console de teste E2E: nº de câmeras simuladas, FPS padrão/por câmera, modelo real do tenant, cenário (classes/limiar/ROI) carregável do modelo, start/stop, métricas e log ao vivo (poll 3 s), aviso de Vast.ai não configurado.
- Inventário de câmeras: filtros, probe individual/lote, importação CSV com relatório de erros por linha.
- Vídeos demo (upload MP4/remover) e eventos demo por tenant/módulo.
- Workers on-premise (lista + restart).

**Qualidade (tenant com módulo `quality`)**
- Câmeras do módulo: atribuir/remover, editar OP e tipo de peça (e, a completar: modo setup, modelo ativo, snapshots de referência).
- Dashboard ao vivo (totais + estações) com polling curto e backoff; modo demo opcional.
- Inspeções: lista **real** com filtros (câmera, resultado, feedback, turno, OP, datas) e paginação; detalhe com evidência e clipe assinados (renovação automática), feedback confirmar/rejeitar com notas; preparar anotação.
- Workspace de anotação: frames NOK, bbox normalizada por classe, auto-save por frame, pular, atalhos de teclado, progresso; criar job de treino; acompanhar jobs e ativar modelo por câmera.
- Andon (monitor de chão, polling 15 s, flash em NOK) e CEP (gráfico de controle por câmera).
- Quality Gate RVB: histórico de peças com drill-down (validações, retrabalhos, foto), retrabalhos com métricas e fotos antes/depois, relatórios por OP com status/export Wiser e CSV, configuração de estações e parâmetros globais (OCR, thresholds V1/V2/V3, frames, confiança mínima) — **tudo dependente de endpoints a criar/alinhar no backend (ver C)**.
- Tablet kiosk por bancada: máquina de estados dirigida por eventos de socket (estado da bancada, peça identificada, resultado OK/NOK), ações iniciar inspeção / corrigir / falso positivo / liberar para bancada B, auto-avanço no OK — com evento de resultado **corretamente** entregue pelo backend e autenticação adequada ao dispositivo (sessão ou allowlist de IP).

### Tempo real / ambiente

1. Um cliente SocketIO único (`socket.io-client`), base = `VITE_WS_URL || VITE_API_URL`, path default `/socket.io`, `transports: ['websocket']` (polling só se o servidor passar a exigir), **JWT em `auth: {token}`** (contrato fechado em #524: `?token=` só por compatibilidade; `connect_error` com `auth_required`/`invalid_token`/`tenant_required`; reconectar com token novo após login/renovação de contexto).
2. Namespaces: `/monitor` (`detection`, `operation:status_changed`, `operation:reloaded`, `edge_telemetry`), `/training` (`training_progress`, `quality_training`), `/quality` (`quality_inspection`, `quality_cep_alert`, `quality_andon`, `quality_piece_identified`, `quality_inspection_started`, `quality_inspection_result`, `quality_station_state`). **Não** implementar `alert`, `quality_gate_result`, `/admin`, `subscribe_camera` até existir emissor/handler.
3. Tratar payloads pelos shapes do publicador (tabela acima), não pelos tipos TS atuais.
4. Manter polling como fallback (treino 3s, câmeras 60s) — com #524 o WS passa a funcionar; tratar `connect_error` e `disconnect` sem quebrar a tela.
5. Reconexão infinita com backoff (1s→10s) e re-render tolerante a `disconnect` (A9).
6. Filtrar por tenant no cliente **não basta** (A2) — #524 faz o isolamento no servidor (rooms por `tenant_schema`); superadmin **sem contexto assumido** é recusado (token sem `tenant_schema`) — para ver tempo real de um tenant, assumir contexto.

## 1. Autenticação, identidade, permissões e contexto

_Autenticação por e-mail/senha com JWT HS de 24h (sem refresh) cujas claims carregam o contexto de tenant (tenant_id, tenant_schema, role, modules, perms) — tudo que o resto da API usa para isolar dados (ADR-0004/0017). Sustenta: tela de Login (+ aba 'Criar Conta' quebrada), recuperação de senha self-service por e-mail (Resend/SMTP + token Redis 30min), dois modos de 'superadmin entra no tenant' — Assumir contexto (mantém identidade, token 30min renovável, auditoria por request) e Ver como (assume identidade do usuário-alvo, 30min, stop best-effort) — ambos implementados no front como troca de token com backup em localStorage e restauração no branch 401 do api.ts. Completa o modelo de permissões WS7: registry canônico em código, roles customizadas por tenant (CRUD admin/superadmin em namespace /api/admin, paralelo ao /api/v1/admin) e overrides grant/deny por usuário (superadmin), cujo efeito só chega ao usuário no próximo login (claim perms) — /permissions/mine recalcula do banco mas ninguém o chama._

1. Tela de login sem aba de auto-cadastro: onboarding de usuário é por convite/criação do administrador (wizard já existe no admin); se auto-cadastro for desejado, precisa de fluxo de tenant (convite com token) — hoje cria conta órfã.
2. Boot da aplicação que valida a sessão no servidor (quem sou eu + tenant + módulos + permissões) em vez de confiar no localStorage; exige que /me passe a devolver tenant_schema/modules ou que o front combine /me + /permissions/mine.
3. Tratamento uniforme de 'sessão inválida' no cliente: expirado, revogado, ausente E inválido (422 hoje) devem levar ao mesmo estado de logout/reautenticação, com mensagens do envelope padrão.
4. Gating de UI por permissão efetiva atualizável em tempo real (buscar 'minhas permissões' no boot e após ações de admin), com aviso claro de que mudanças de permissão/role valem no próximo login ou ao encerrar as sessões do usuário.
5. Painel de 'Assumir contexto' do superadmin com: seletor de tenant (ativos), banner persistente com nome do tenant/tempo restante, renovação automática silenciosa, botão sair, e tela 'contexto expirado — reassumir?'; auto-entrada quando a grade de monitoramento pertence a um único tenant (com guard anti-loop).
6. Modo 'Ver como usuário' no detalhe do tenant: iniciar com confirmação (alvo não pode ser superadmin/inativo), banner fixo com nome/e-mail do alvo e quem está vendo, sair sempre possível mesmo com falha de rede; exclusivo com 'assumir contexto' (mensagem amigável em 409/403).
7. Tela de gestão de permissões que sirva TAMBÉM ao admin de tenant (não só superadmin): roles customizadas do seu tenant (criar/editar/excluir com bloqueio 'há N usuários vinculados — desatribua antes'), atribuição por usuário, e labels/descrições pt-BR do registry (hoje só superadmin consegue carregar o registry).
8. Drawer de permissões por usuário (superadmin): papel base, role customizada (sempre do tenant do usuário, resolvendo o bug do tenant_id), matriz de overrides herdado/permitir/negar com motivo, permissões efetivas resultantes e botão 'encerrar sessões' para aplicar imediatamente.
9. Fluxo de recuperação de senha: telas 'esqueci minha senha' (mensagem neutra, anti-enumeração) e 'definir nova senha' via link do e-mail (token 30min, uso único), informando que todas as sessões serão encerradas; feedback de 429 por tentativas.
10. Feedback de limite de tentativas de login (429 por IP/conta) e de conta sem tenant/role atribuída (401 com mensagem orientando contato com administrador).
11. Visão de auditoria para o superadmin: histórico de 'assumir contexto', 'ver como' e mudanças de permissão (tabelas audit_log/impersonation_sessions/tenant_context_audit já existem; hoje sem leitura na UI) — e política de retenção para tenant_context_audit.

_GAP-DE-PRODUTO neste domínio: 3 endpoint(s) sem UI — ver anexo A.1._

## 2. Admin da plataforma (A) — tenants, usuários, planos, flags

_Backoffice do superadmin (tudo @require_superadmin, 403 para outros papéis): dashboard agregado, CRUD de tenants (criação provisiona schema + admin com senha temporária), planos (limites/módulos/preço), feature flags globais e por tenant, catálogos estáticos de módulos/permissões, inventário cross-tenant de câmeras com importação CSV e probe, audit log com export CSV, comunicados da plataforma, canais OTA do edge e health legado. Sustenta as páginas do módulo admin do front atual (AdminTenantsPage/DetailPage, AdminPlansPage, AdminFeatureFlagsPage, AdminInventoryPage, AdminAuditLogPage, AdminAnnouncementsPage, AdminDashboard/AdminLayout) e o helper crossTenantCameras. Tudo em public.* (tenant é parâmetro, não contexto); envelope success/error exceto export CSV._

1. Tela de criação de tenant com etapa final 'Credenciais geradas' (e-mail admin + senha temporária copiável, aviso de exibição única) em vez de alert(); validação de slug reservado e seleção de plano vinda da lista de planos.
2. Painel de planos com drill-down 'clientes neste plano' (lista de tenants do plano) e edição inline de limites/funcionalidades por módulo a partir do registry.
3. Tela de comunicados com edição (título/conteúdo/tipo/alvo/expiração) e agendamento visível — hoje só cria/arquiva.
4. Painel de canais de software do edge (OTA): lista de canais com target_ref/atualizado por, ação 'publicar ref' com confirmação e trilha de auditoria.
5. Inventário de câmeras com paginação/busca server-side, importação CSV com pré-visualização e relatório por linha (201/207), e teste de conectividade que deixe claro que roda da nuvem (ou delegue ao edge) com estado 'sem resposta' para itens fora do resultado do lote.
6. Dashboard admin honesto: ocultar/rotular KPIs não implementados (câmeras online, alertas 24h, tickets, MRR) ou ligá-los a fontes reais; atualização periódica (30s) e eventos críticos clicáveis para o audit log.
7. Auditoria com export que respeite os mesmos filtros da lista (data/tenant/ação) e indicação do limite de 10k linhas.
8. Flags: globais com catálogo de chaves conhecidas (evitar criar chave por engano) e, por tenant, criar/remover chaves além de alternar.
9. Importação de câmeras que funcione de ponta a ponta: backend precisa atribuir dono (user_id) ao criar a câmera (ator superadmin ou admin do tenant) — hoje a coluna NOT NULL derruba todo o lote; erros por linha devem ser legíveis (não a mensagem do driver).

_GAP-DE-PRODUTO neste domínio: 4 endpoint(s) sem UI — ver anexo A.2._

## 3. Admin da plataforma (B) — tickets, workers, auditoria, inventário, anúncios

_Painel do superadmin (blueprint admin, /api/v1/admin/*) — parte B: gestão de tenants (políticas, suspensão/reativação com revogação de sessões, histórico de plano, visão geral), ciclo de vida de usuários (criação com senha temporária e assentos, role, ativação, reset de senha, sessões), fila de aprovação de treinamento, workers on-premise (registro via heartbeat com segredo compartilhado, métricas, comando de restart) e tickets de suporte; mais dois endpoints de cliente (JWT de qualquer role) para comunicados da plataforma. Sustenta no front atual: AdminTenantDetailPage (abas módulos/políticas/usuários/histórico), AdminRetentionPage, AdminUsersPage + CreateUserWizard + UserPermissionsDrawer, AdminTrainingApprovalsPage, WorkersPanel (Workers/Observabilidade, polling 10s) e AdminTicketsPage. Todas as rotas admin usam @require_superadmin (403 para outras roles), escopo global (não há contexto de tenant do JWT — o tenant vem do path/body) e envelope success/error. 11 wrappers de adminService.ts (detalhes de ticket/usuário/worker/aprovação/overview, stats, reply, force-reset) existem sem nenhuma tela que os use; a fila de aprovações e a tabela de tickets não têm writer no repositório; o overview do tenant responde 400 para qualquer tenant (whitelist de schemas quebrada em core/tenant.py:65); o único cliente do heartbeat manda cameras_active=0 fixo (falso camera_gap)._

1. Tela de detalhe de ticket: thread cronológica distinguindo notas internas de respostas ao cliente, caixa de resposta com toggle 'interno', triagem de status/prioridade/responsável e faixa de KPIs (abertos, críticos, altos, normais, baixos); corrigir a navegação da lista (hoje aponta para rota inexistente) e filtros de status/prioridade que o back respeite.
2. Canal para o cliente abrir e acompanhar tickets (formulário + lista no app do tenant) — hoje não existe nenhuma forma de criar ticket.
3. Painel de detalhe do usuário (drawer ou página): dados completos, últimas ações no audit, sessões ativas com IP/navegador/expiração, botões 'encerrar sessões', 'resetar senha' (senha temporária exibida uma vez com copiar) e 'forçar troca de senha' — este último só faz sentido quando o login passar a exigir a troca.
4. Fluxo de primeiro acesso para o usuário recém-criado (link/tela que resgate o token de 48h e defina a senha) ou remoção do token da tela de credenciais do wizard.
5. Detalhe do worker on-premise com série temporal (GPU %, VRAM, FPS, câmeras ativas) selecionável 1h/24h/7d, estado do heartbeat (onpremise/railway/offline com 'visto há X s') e feedback do restart (enviado → aguardando próximo heartbeat ≤30s → confirmado/expirado em 120s). O cliente de heartbeat precisa reportar cameras_active/cameras_total reais antes de qualquer indicador de liveness ser confiável.
6. Aba 'Visão geral' no detalhe do tenant (câmeras com status/módulo, alertas das últimas 24h, jobs de treino) — e alinhar a fonte de jobs com a pipeline real. — pré-requisito: corrigir a whitelist de schemas (core/tenant.py:65) ou o endpoint responde 400 sempre.
7. Detalhe da aprovação de treinamento com métricas e galeria de amostras do dataset (URLs expiram em 5 minutos — recarregar ao expirar) e modais de aprovar/rejeitar com notas/motivo; a tela só terá valor quando a pipeline passar a criar aprovações. Filtro de status com opção 'Todos' que realmente envie status vazio (hoje cai no default 'pending').
8. Inbox/banner de comunicados da plataforma no app do cliente com 'marcar como lido' (decidir se leitura é por usuário ou por tenant; hoje o back marca por tenant).
9. Política de retenção por tenant deve editar 'default_retention_days' (tiers permitidos) e não 'video_retention_days'; mensagens de validação do back (max_seats, single_session, rate limit, tiers) exibidas inline.
10. Suspensão/reativação de tenant e ativação/desativação de usuário com modais próprios (motivo, aviso de logout imediato de todos os usuários do tenant, aviso de consumo de assento na reativação com contagem x/y).
11. Indicador de sessões revogadas/logout forçado e troca de role com aviso 'vale no próximo login' (ou oferecer encerrar sessões junto).

_GAP-DE-PRODUTO neste domínio: 13 endpoint(s) sem UI — ver anexo A.3._

## 4. Admin auxiliar — branding, integrações, versões, observabilidade, consoles de teste/demo

_Domínio auxiliar de administração da plataforma (superadmin em quase tudo): white-label por tenant (branding flat canônico em public.tenants.branding + endpoint JWT-opcional de boot do tema — chamado pelo front só após login, App.tsx:67), integrações externas com credenciais cifradas (R2/Vast/RunPod/notification/byo_db, por tenant), versionamento/changelog do sistema (snapshot de plan/modules/feature_flags + rollback cross-tenant), observabilidade consolidada (summary/timeseries/edge-fleet/streams/collect sobre platform_metrics, Redis, Celery, R2), dados de demonstração (vídeos MP4 por módulo servidos ao superadmin no stream; eventos sintéticos por tenant) e dois consoles de teste (UI stub em memória + harness de staging para scripts). Sustenta no front atual: ThemeProvider (tema no boot), /admin/branding/tenants[/:id], /admin/integrations + painel no detalhe do tenant, /admin/versions, /admin/changelog, /admin/observability (abas), /admin/demo-videos, /admin/test-console. 12 endpoints não têm UI no front (4 órfãos, 3 gaps de produto, 5 consumidos só por scripts de staging) e a página Eventos Demo (3 endpoints FRONT-ATUAL) existe mas perdeu a rota num merge._

1. Tela White-label: lista de tenants com preview do branding carregada em UMA chamada (lote) em vez de N+1; editor com preview ao vivo, upload de logo/favicon (PNG/JPEG/SVG/GIF/WebP ≤2MB) com feedback de URL persistida, salvar sempre o conjunto completo de campos (o PUT substitui), botão 'restaurar padrão' e aviso de que usuários do tenant veem o tema só ao recarregar.
2. Aplicação do tema no boot tolerante a falha (fallback Recognition) e reaplicação após login/logout/assumir contexto — a branding segue o tenant do token atual.
3. Tela de Integrações por tenant (dentro do detalhe do tenant e também visão de plataforma): formulário por tipo (R2, RunPod/GPU, notificação, banco próprio) com segredo mascarado (••••last4), ações Salvar → Testar → status/último erro/última verificação, remover com confirmação; para admin de tenant, só 'banco próprio' do seu tenant.
4. Versões do sistema: lista com filtro para separar versões automáticas de deploy das manuais, tela de DETALHE da versão (snapshot de tenants/planos + changelog da versão) e rollback com confirmação forte mostrando o que será restaurado em quais tenants (hoje é window.confirm sem preview).
5. Changelog: lista paginada com filtros (categoria, importância, área, versão) e formulário de entrada manual; badge de importância.
6. Observabilidade: dashboard com abas deep-linkáveis (visão geral, infra, edge, workers, streams), intervalo de atualização configurável/pausável persistido, gráficos de séries com janela 1h/6h/24h/7d, botão 'coletar agora' com feedback, estados degradados por seção (nunca tela vazia por uma fonte fora); incluir card 'Processo' (RSS, uptime, requisições por worker, backend de storage, gauges de live view) a partir do endpoint de introspecção.
7. Vídeos demo: gestão por módulo (abas), upload MP4 ≤100MB com progresso, lista com preview/URL e remoção; indicação clara de que só o superadmin vê o vídeo no lugar do feed.
8. Eventos demo: página re-exposta na navegação admin (seletor de tenant, módulo, quantidade 1..500, status por módulo com último seed, remoção por módulo com confirmação) — hoje existe mas está sem rota.
9. Console de teste: redesenhar como ferramenta honesta — ou integrar ao harness real (status/evidências/métricas reais, start/stop com poll) ou rotular explicitamente como simulação; estado deve vir de fonte compartilhada (Redis) e não da memória de um worker.
10. Padronização de contrato para o novo front: todos os endpoints deste domínio sob /api/v1/admin (eliminar /api/admin/demo-videos), 201 real em criações, 404 em cross-tenant, e um único formato flat de branding.

_GAP-DE-PRODUTO neste domínio: 6 endpoint(s) sem UI — ver anexo A.4._

## 5. Câmeras, streams/live view e gravadores

_Domínio que sustenta o cadastro e a operação das câmeras IP (CRUD em public.cameras com senha Fernet, probe/teste de conectividade, arquivar/restaurar, config de FPS/qualidade/coleta com propagação ao edge via edge_commands), a atribuição de modelo por câmera (duas famílias: cameras.model_{módulo}_id e model_deployments com geometria/histórico/rollback), módulo ativo/agenda, retenção por câmera, snapshot de triagem (refresh→poll, capturado pelo edge e servido do R2) e o live view HLS (POST /stream/start → URL com token de playback no path → serve_hls público lendo segmentos do Redis empurrados pelo edge, com 425/410 como sinais de retry/renovação). Inclui ainda gravadores NVR/DVR (/api/v1/recorders: CRUD, teste, timeline, extração de frames via Celery) sem UI, 8 aliases /api/v1/cameras duplicados e o status de workers Celery (/api/streams/status). Fluxos do front atual: CamerasPage (lista, onboarding probe→criar, wizard salvar→testar, iniciar/parar, arquivar/restaurar, FPS, modelo por módulo), CameraTriagePage (snapshot + renomear/confirmar posição/ativar), grade de monitoramento (stream/info → useLiveView → hls.js), TrainingPage (escopo de modelo por câmera) e fueling (feed demo × real)._

1. Ficha/detalhe da câmera (GET /cameras/<id>): dados de conexão (sem senha), site edge, módulo ativo, modelo efetivo (override × herdado × deployment ativo) e último teste/probe — hoje só existe lista + modais.
2. Wizard de onboarding corrigido e único: probe (com ramo NAT/gateway) → revisar URL sugerida/codec → escolher site edge (obrigatório para edge) → criar; unir com o wizard de edição/teste (hoje são dois componentes com contratos diferentes).
3. Player de live view com os estados do contrato: carregando (425 = aguardando edge/FFmpeg), renovando token (410), indisponível (404), limite (429), e indicação de tipo de feed (HLS × edge × demo para superadmin); botão 'parar' explícito com aviso de que derruba para todos.
4. Banner/ação 'assumir contexto do tenant' para superadmin quando câmeras da grade pertencem a outro tenant (já existe em parte — manter no novo front).
5. Tela de configuração operacional por câmera: FPS/qualidade/coleta (PATCH /config) com indicador de propagação ao edge (queued/sem site/erro) e telemetria do site (health-context) — depois de consertar o 500.
6. Troca de módulo ativo por câmera (epi/quality/counting/basic/pausar) respeitando modules_enabled, e agenda semanal dia/hora→módulo com visualização do 'módulo valendo agora' (PATCH /module, PUT /schedule, GET /module/current).
7. Histórico e rollback de escopo de modelo por câmera (GET /model-config/history, POST /rollback) dentro da aba 'Modelos por câmera'; unificar a visão com a atribuição simples por módulo (PUT /models) para o usuário não ver duas verdades.
8. Retenção por câmera (tier 1/7/30/90 ou herdar do tenant) na ficha da câmera, e retenção padrão do tenant nas configurações do tenant (usar /api/v1/tenant/retention, não a rota quebrada de /api/cameras).
9. Módulo de gravadores NVR/DVR: cadastrar (protocolo, host/porta, credenciais), testar conexão, ver canais, timeline de gravações por canal/período e disparar extração de frames com acompanhamento do job (hoje só 202 + task_id) — pré-requisito do coletor do edge (RECORDER_CLOUD_ID).
10. Exclusão definitiva de câmera só para admin, com confirmação forte, aviso de cascata e bloqueio explícito quando houver frames de treino (ou manter só arquivar).
11. Diagnóstico de stream por câmera (status/ffmpeg) via o agregado de observability, não via /stream/status por câmera.
12. Lista de câmeras com filtros/paginação (site, módulo, ativa/arquivada, status de probe/teste) — hoje é lista inteira sem filtros; e badge de gateway deve sair (serviço extinto).

_GAP-DE-PRODUTO neste domínio: 18 endpoint(s) sem UI — ver anexo A.5._

## 6. Treinamento, anotação, propagação e busca

_Pipeline de dados de treino do módulo EPI: acervo de imagens (training_frames) com galeria facetada e curadoria, classes custom do tenant (yolo_classes, união com o catálogo module_classes via ids namespaced 100000+id), estúdio de anotação (caixas YOLO normalizadas, autosave, propostas de IA com fila de aprovação), matriz de cobertura classe×câmera, dois jobs GPU assíncronos com callback (propagação semeada DINOv2+SAM no RunPod ou no Jetson; busca por conteúdo OWLv2 no RunPod) e o treino em si (jobs RunPod via Celery, progresso por polling, modelos treinados e config de cenário por modelo). Sustenta no front atual a TrainingPage (abas Imagens, Cobertura, Classificar, Modelos por câmera, Modelo, Treino), o AnnotationStudio, a ModuleClassesPage (PATCH/POST classes), o wizard de cenário, a atribuição de modelo por câmera e o fallback de stats do dashboard. Tudo vive em public.* com tenant_id (classes/frames/jobs de propagação e busca) ou, no legado (vídeos, jobs de treino, modelos), com recorte por user_id._

1. Tela de treino com histórico de jobs do TENANT (não só do usuário), detalhe por job (status, épocas, métricas, erro, custo GPU, quem disparou) e progresso ao vivo confiável (polling ou WebSocket funcionando) — hoje só 'último job do usuário'.
2. Formulário 'Novo treino' que mostre apenas os campos que o back honra (preset, tamanho do modelo, épocas, framework/base_model, dataset_version) e deixe explícito qual versão de dataset será usada; sinalizar limite de 20 treinos/dia e o gating de GPU (chave por tenant/flag).
3. Galeria/estúdio: carregar miniaturas e imagem do estúdio exclusivamente por URL pré-assinada (1h, com renovação ao expirar) — nenhuma <img> apontando para o endpoint autenticado; miniaturas dos achados de busca precisam da mesma solução.
4. Upload de imagens de treino direto para o acervo do tenant (multipart ≤50 arquivos/10 MB, resultado parcial 207 com lista de falhas por arquivo) substituindo o upload legado por 'vídeo sintético'.
5. Fila de rotulagem priorizada por incerteza (active learning) como visão/atalho na galeria ou no estúdio ('próximo frame que mais ajuda o modelo').
6. Revisão/QA humano: ação 'marcar como revisado' por frame (e em lote), com filtro 'revisados' na galeria e contagem na cobertura — o back já suporta status reviewed.
7. Gestão de classes: além de arquivar/restaurar/reordenar, permitir excluir classe sem uso (com mensagem 409 orientando arquivar quando há anotações) e tratar o 409 de nome duplicado cross-módulo/contexto com mensagem clara.
8. Barra de status persistente para jobs assíncronos (propagação e busca) visível em qualquer aba do treino, com retomada ao reabrir a tela, custo estimado×real, motivo de falha legível e CTA 'Revisar' que leva à fila de propostas.
9. Painel de achados da busca com seleção por grupo/termo, escolha/criação de classe inline e proteção contra promover duas vezes (idempotência é do front).
10. Wizard de cenário por modelo que ofereça as classes reais do modelo/tenant (não um set fixo de 13 nomes) e valide a câmera escolhida dentro do tenant.
11. Ativação de modelo sempre pelo fluxo com aprovação (campeão×desafiante, 409 eval_rejected) — não expor o atalho legado; lista de modelos por tenant (registry) em vez de por usuário.
12. Alertas por câmera devem vir da tela/endpoint de alertas do domínio alerts (com filtro de câmera), não do atalho sem isolamento de tenant.

_GAP-DE-PRODUTO neste domínio: 5 endpoint(s) sem UI — ver anexo A.6._

## 7. Modelos (rollout), datasets, cenários, módulos e regras

_Módulos do tenant (lista, detalhe, classes = catálogo global ∪ classes custom, stats/KPIs), catálogo de tipos de operação e composição read-only do 'cenário' de uma câmera, regras de alerta (CRUD sem motor que as aplique), datasets pai + build assíncrono de versões COCO (Celery + R2), registry MLOps de modelos em public.trained_models (lista, linhagem, ativação com gate campeão×desafiante, eval, drift) e o manifesto legado de rollout em {schema}.models (active/pin — sem writer de produto, órfão). No front atual sustenta: HomePage/InvestigationPage (lista de módulos; o detalhe GET /modules/<code> tem wrapper sem chamador), KPIRow do dashboard (stats do EPI), anotador/curadoria/classificador (classes do módulo), CameraModelScope (lista+detalhe de modelos), botão 'Ativar' da TrainingPage e o ScenarioEditor (que hoje chama os paths sem /v1 e está quebrado)._

1. Tela 'Regras de alerta' do módulo EPI: lista por câmera/tenant-wide, criar/editar (tipo de violação vindo das classes do módulo, duração mínima OU ocorrências em janela), ativar/desativar, excluir — com aviso claro de que só vale quando o motor aplicar as regras (decisão de produto: implementar enforcement ou aposentar o CRUD).
2. Tela 'Datasets e versões' do treinamento: criar dataset (nome, módulo), disparar build de versão (nome, split train/val/test com validação soma=1, augmentations), acompanhar status building→ready|error com polling, ver contagens/distribuição de classes por versão, baixar COCO por split (links com expiração de 1h — rebuscar ao clicar) e escolher versão ao iniciar treino.
3. Tela 'Registry de modelos' (MLOps): lista do tenant com filtros módulo/status, detalhe com linhagem (dataset → job → modelo → deployments ativos), métricas (mAP50/precision/recall, validação ONNX), botão 'Avaliar contra o campeão' com acompanhamento assíncrono, painel da última avaliação (veredito, métricas, matriz de confusão) explicando o 'reprovado', ação 'Ativar' com fluxo de 409 (pedir override por admin) e gráfico de drift por janela/câmera.
4. Gating visual de permissões no treinamento: esconder/desabilitar 'Ativar'/'Avaliar'/'Criar dataset' conforme perms do JWT (training:write / training:approve) em vez de descobrir o 403 no clique.
5. Editor de cenário da câmera funcional: carregar composição (módulos + classes, operações, regras ativas, agenda) e catálogo de tipos de operação pelo path correto; modelar tipos do DTO (hoje unknown[]) e tratar estados vazios por módulo.
6. Gestão do catálogo global de classes por módulo como tela de PLATAFORMA (superadmin): ativar/desativar classe com aviso de impacto em todos os tenants; no admin de tenant manter só as classes custom (/api/classes).
7. Dashboard por módulo: usar o módulo selecionado (não 'epi' fixo) ao buscar KPIs; exibir fórmula do compliance proxy em tooltip e estado 'sem câmera ativa' (compliance null); tratar 403 'módulo não disponível'.
8. Seleção de módulos: chamar '/api/modules/' com barra final (evitar 308), refletir filtro de plano (enforce_plan_limits) e estado 'módulo expirado' (expires_at).

_GAP-DE-PRODUTO neste domínio: 16 endpoint(s) sem UI — ver anexo A.7._

## 8. Módulo Qualidade (inspeções, gate, estações, relatórios, treino)

_Módulo Qualidade industrial: (1) inspeção contínua por câmera (worker quality_inference_loop grava quality_inspections, clips/evidências no R2, CEP) com feedback do operador, anotação de frames e retreino; (2) Quality Gate RVB — state machine de peças (idle→identified→validating_v1..v3→approved / rework_vN), bancadas, retrabalhos, torre luminosa, exportação Wiser, tablet kiosk e dashboard ao vivo; (3) relatórios de turno (JSON/PDF) e dados para monitor Andon sem JWT no backend (a página do front atual, porém, fica atrás do login — App.tsx:54). Tudo em schema do tenant (quality_* + cameras) com log de acesso a vídeo em public. O front atual sustenta: câmeras do módulo (lista/atribuir/config), detalhe de inspeção (clip/evidência/feedback/preparar anotação), workspace de anotação, dashboard cockpit (summary+stations polling), páginas de peças/retrabalho/relatórios/config do gate e o tablet. Estado real: todas as tabelas quality_* têm 0 linhas no DEV, a tela de inspeções é mock, a página de treino do módulo não está roteada e há ~20 drifts de contrato front×back (vários fluxos não fecham)._

1. Tela 'Câmeras do módulo Qualidade' com duas listas (atribuídas × disponíveis), atribuição/remoção, edição inline de OP/produto/thresholds/cooldown e toggle de 'modo setup' (pausa inferência) com estado visível — respeitando que a atribuição exige o módulo habilitado no plano.
2. Lista real de inspeções (substituir o mock) com filtros câmera/resultado/categoria de defeito/feedback/turno/período/OP, paginação com total real, badge de alerta CEP e chegada ao vivo via WebSocket; barra de métricas do turno + pareto de defeitos (summary).
3. Detalhe da inspeção com player de clip e foto de evidência usando URLs pré-assinadas que expiram em 15 min (renovação automática, tratamento de 403/429 'limite de 60/h'), ações de feedback com os 4 estados (confirmar, rejeitar, solicitar retreino, falso negativo) e notas.
4. Workspace de anotação: preparar frames (estado 'processando' com polling/evento até os frames existirem), navegação frame a frame com auto-save, 'pular' explícito, barra de progresso com a regra 'mínimo 10 frames anotados' e botão 'criar job de retreino' ligado ao fluxo correto.
5. Central de treinamento do módulo: lista/detalhe de jobs (status, métricas, erro), progresso ao vivo por WebSocket, e ação 'ativar modelo' escolhendo uma ou mais câmeras (só jobs concluídos; um modelo ativo por tenant) — com aviso claro de que o treino real depende do pipeline ONNX (task-086).
6. Quality Gate: telas de operação da peça — criar/identificar peça (entrada manual ou OCR), iniciar inspeção escolhendo a câmera da bancada, resultado OK/NOK com foto do defeito (precisa de endpoint de foto/URL pré-assinada que hoje não existe), falso positivo, liberar para bancada B, início e conclusão de retrabalho com duração — e tablet kiosk com estado inicial carregado da bancada e eventos WebSocket filtrados por estação.
7. Configuração de bancadas: criar/editar (nome, descrição, câmeras, torre luminosa, URL do tablet) e ativar/desativar; 'configurações globais do gate' (thresholds/voting) precisam de backend novo — hoje só existem por câmera.
8. Cockpit ao vivo (summary + estações com polling 5/15s e backoff) e painel de KPIs do gate (peças do dia, aprovadas, NOK, taxa, retrabalhos, tempo médio, defeito mais comum, por validação).
9. Relatórios: relatório de turno por câmera/data/turno com pareto, exportação PDF via download autenticado (não abrir URL em aba) e lista de aprovadas por OP com status de exportação Wiser — exportação manual/lote para Wiser e CSV exigem endpoints novos.
10. Monitor Andon de chão de fábrica (tela grande, sem login, restrita à rede interna/edge) mostrando turno, OK/NOK, últimas inspeções e status CEP, e gráfico de controle (CEP) por câmera com baseline/UCL e taxas das últimas 24h.
11. Snapshots de referência por câmera/OP (galeria) — exige endpoint de URL pré-assinada para quality-snapshots/ que ainda não existe.

_GAP-DE-PRODUTO neste domínio: 19 endpoint(s) sem UI — ver anexo A.8._

## 9. Edge / frota — enrollment, heartbeat, comandos, eventos, monitoring

_Frota edge (Jetson no site do cliente) e tudo que a liga à nuvem: onboarding (site → enrollment token one-time → POST /edge/enroll com chave pública RS256 → heartbeat periódico), canal de controle outbound (fila public.edge_commands consumida por polling do box + ack), canais de dados do box (config/poll com ETag, frames de treino, snapshots de câmera, segmentos HLS do live view, alvo OTA) e observabilidade (saúde derivada de heartbeats, telemetria espelhada no Dashboard Integrado, painel oculto /monitoring superadmin que conversa com o box via comandos monitoring.*). Front atual sustenta: painel de frota em /admin/observability?tab=edge (overview, sites/health, heartbeats, summary), /epi/sites (listar sites e alternar deployment_mode), /epi/edge-observability (curvas de treino + telemetria edge histórica e ao vivo via SocketIO) e /monitoring (superadmin: frota multi-tenant, query/snapshot/logtail por comando com poll, limiares, detecções). Todo o lado device (enroll, heartbeat, config, comandos, frames, live view, OTA) é BACKEND-ONLY; onboarding/gestão de sites, tokens, devices, gateway e console de comandos/eventos são capacidades sem UI (GAP)._

1. Tela 'Sites edge' do tenant com criação de site (nome, localização, modo cloud/edge/hybrid), edição de status/modo e detalhe com saúde derivada, nº de devices e último heartbeat (hoje só existe lista + toggle de modo).
2. Assistente de onboarding do box dentro do detalhe do site: gerar token de enrollment (exibir plaintext uma única vez, copiar, mostrar expiração 24h), listar tokens com status ativo/usado/expirado e revogar; instruções do passo no box.
3. Lista de devices do site com último contato, versão do agente, status do heartbeat e ação 'Revogar acesso' (com motivo) + indicação de que um device revogado pode ser re-enrolado com token novo.
4. Console de comandos do site: histórico por status (pendente/executado/falhou/expirado), resultado (JSON), e envio manual de comandos suportados (recarregar config de câmeras, captura de snapshot, diagnóstico) — com UX de 'o box só acorda a cada ~60s' (estado pendente + acompanhamento).
5. Timeline de eventos do box por site (detecção, câmera offline/online, modelo carregado, stream iniciado/parado) com filtro por tipo e paginação por cursor — depende do backend consertar o produtor (uploader → /events/ingest).
6. Tela de rede do site (gateway MikroTik/WireGuard): cadastrar/editar chave pública WG, endpoint, sub-rede LAN e configuração, com status de provisionamento (provisionando/ativo/inativo/erro) — visível só para quem gerencia gateways.
7. Unificar o painel de frota: uma visão multi-tenant para superadmin (com divergência OTA por device, canal e target) e uma visão do tenant para admin, ambas com a mesma regra de 'offline' e a mesma série de heartbeats paginável (cursor 'before', janela do resumo selecionável 24h/7d).
8. Painel de observabilidade do box (hoje /monitoring oculto): manter o padrão comando→pendente→acompanhar (spinner 'acordando o box', poll até resposta), snapshot ao vivo pausando com aba oculta, logtail por unit, limiares editáveis por site e detecções por câmera com lag de ingest; o cliente não deve enviar campos que a API ignora (from/to epoch).
9. Dashboard Integrado: telemetria ao vivo deve chegar filtrada por tenant (exigir correção do backend/socket antes de expor a mais de um tenant) e os empty-states devem refletir produtores reais (heartbeat do box), não o seed script de dev (services/api/scripts/seed_dashboard_observability.py) nem os POST de ingest.
10. Não construir UI sobre o fluxo de claim code (pareamento por código curto) enquanto o backend não ligar claim→enroll; se o produto quiser 'parear com código', o caminho hoje é o token de enrollment por site.

_GAP-DE-PRODUTO neste domínio: 13 endpoint(s) sem UI — ver anexo A.9._

## 10. Eventos, alertas, notificações, feedback, verificação, vídeos, storage, retenção

_Domínio de leitura/tratamento do que o detector produz e da mídia associada: alertas (public.alerts, criados pelo worker de inferência — tasks/inference.py::_save_alert — e, para liveness, por liveness_service via heartbeat admin; nunca pelas rotas deste domínio), busca investigativa/timeline/resumo de eventos (alerts ∪ demo_events), fila de verificação humana (verification_status='needs_human' após triagem por Claude no worker), feedback do operador, canais de notificação, retenção do tenant, sonda de storage e o pipeline v1 de vídeos/imagens de treino (R2 + Celery). Sustenta no front atual: Histórico de Alertas (lista/filtros/CSV/reconhecer/snapshot), sino de notificações (polling 30s), widgets do dashboard (alertas recentes, timeline, distribuição por classe), página Investigação (EPI), página Verificação (EPI) e o upload de imagens da Galeria de Treinamento. Tudo é REST + polling: não há evento SocketIO de alerta (o front escuta 'alert' em /monitor, mas o backend nunca emite). Dos 36 endpoints, 10 são usados pelo front; do pipeline v1 de vídeos (14 rotas) só images/upload tem UI — o front usa o legado /api/training/videos. Dois endpoints GAP estão quebrados em produção (POST /api/v1/feedback → 500 por UUID não adaptado; GET /api/verification/queue/count → sempre 0)._

1. Central de alertas com lista paginada, filtros (câmera, período, tipo de violação, reconhecido), ação 'reconhecer', painel lateral com imagem de evidência (URL expira em 1h — recarregar ao reabrir) e exportação CSV respeitando os mesmos filtros (avisar teto de 10.000 linhas).
2. Sino/central de notificações em tempo quase real: enquanto não houver push de alerta, polling curto com badge; idealmente o backend passar a emitir 'alert' no socket /monitor (o front antigo já escutava um evento que nunca chega).
3. Investigação de eventos com filtros combinados (múltiplas câmeras e classes, módulo, período, confiança mínima), lista com miniatura da evidência e gráfico de timeline por hora/dia/semana; toggle 'incluir eventos de demonstração' coerente entre lista, gráfico e resumo.
4. Fila de verificação humana com imagem da evidência por item (hoje a fila não traz a imagem — usar o snapshot do alerta), motivo da triagem automática, ações Confirmar/Rejeitar e badge de pendências na navegação. (o endpoint de contagem precisa do fix row['count'] antes).
5. Feedback do operador em qualquer evento/alerta ('detecção correta / errada / incerta' + classe corrigida) e painel 'qualidade do modelo' com resumo por módulo e veredito — fecha o flywheel de treino que o backend já persiste. (o POST de feedback precisa do fix de str(created_by) antes de ligar a UI).
6. Configurações do tenant (admin do cliente): retenção padrão de vídeo por tier (1/7/30/90 dias) mostrando override vs plano vs efetiva, e cadastro de canais de notificação (WhatsApp/Telegram/e-mail/webhook) com destinatários e ativar/desativar — sinalizando que o envio ainda não está implementado no backend.
7. Upload de vídeos de treino unificado: um único fluxo (preferir upload direto ao R2 com progresso + extração no worker + tela de progresso/poll + 'tentar novamente' + excluir + indicador de cota), substituindo o legado /api/training/videos e descartando extração no browser/thread.
8. Upload de imagens na galeria de treino (arrastar até 50 imagens JPG/PNG/WebP ≤10MB) com resultado 'enviadas/falhas' e recarga da galeria.
9. Estado 'sem imagem de evidência' e 'storage indisponível' tratados explicitamente (snapshot 404/400) em todas as telas que mostram evidência.

_GAP-DE-PRODUTO neste domínio: 18 endpoint(s) sem UI — ver anexo A.10._

## 11. Dashboard, relatórios, contagem, operações, abastecimento, chat, monofatura, health

_Miscelânea operacional do monolito: (1) operações configuráveis por câmera (ROI/contagem/zona) que o worker OperationsEngine avalia e hot-recarrega via Redis/SocketIO — sustenta a tela de Operações da câmera (EpiOperationsPage/TrainingModeLayout) e o editor de cenário; (2) sessões de contagem (carga/descarga) com validação manual e aceite — sustentam CountingPage e FuelingValidationPage, embora hoje nada alimente counting_events; (3) módulo Fueling (dashboard/baias/eventos) — demo mockada para superadmin por feature flag, com o caminho 'real' quebrado; (4) relatórios/dashboard legados (/reports/home, /v1/dashboard/*, export xlsx) chamados só por páginas mortas (não importadas) → ÓRFÃO, e relatório de compliance PDF sem UI (GAP); (5) chat assistente SSE (Ollama) e health/liveness/readiness (infra) + /v1/health/metrics para o rodapé; (6) integração monofatura (inspeção por peça, tenant_schema) sem consumidor._

1. Tela de Operações da câmera unificada com o editor de cenário: mesmo identificador de módulo, catálogo por módulo (com formulário gerado do config_schema), validação inline com as mensagens do back (422), exclusão com confirmação por nome quando há histórico (409) e indicador de 'recarregado no worker' (version/evento).
2. Histórico de avaliações por operação (timeline de operation_results com result_json) e status ao vivo (last_value_json/last_evaluated_at), hoje sem tela.
3. Contagem/carga-descarga: decidir produto antes de migrar — ou ligar um produtor real de eventos (edge) ou retirar a tela; se mantida: retomada de sessão em andamento, polling/stream de contagens, encerramento com totais por classe.
4. Validação e aceite de contagem (CD-07): filtros de período/baia/threshold, edição de contagem manual, aceite/rejeição por sessão, agregado diário e resumo — já existe, migrar com o mesmo contrato.
5. Fila de revisão de placas (LPR): lista de sessões com placa (filtro 'só revisão'), correção manual com validação de formato Mercosul/antiga e indicação de confiança do OCR.
6. Fueling: substituir a demo mockada por tela ligada a dados reais (ou explicitar 'modo demonstração' por flag) — hoje o caminho real não existe; precisa definição de baias (UUID) e KPIs reais a partir de counting_sessions.
7. Relatórios: tela de relatório de compliance EPI (período dia/semana ou intervalo, resumo, top câmeras, tendência por hora, download do PDF com link que expira em 1h; rotular a taxa como estimativa) e listagem dos PDFs diários já gerados no R2 (hoje sem endpoint de listagem).
8. Exportação de alertas em planilha (xlsx) — ou consolidar na exportação CSV da tela de alertas e aposentar /v1/reports/export.
9. Assistente/chat: indicador de disponibilidade (usar /api/chat/health), tratamento dos dois formatos (SSE vs JSON de erro) e decisão sobre manter o recurso sem Ollama em produção.
10. Rodapé/painel de saúde: consumir métricas corretas (câmeras ativas de public.cameras), latências e readiness (/status) numa visão de observabilidade para admin.
11. Integração monofatura: tela/tablet de bipagem de peça por etapa (abrir sessão, concluir com resultado por atributo e evidência) e consulta de sessões por peça; contrato outbound real ainda pendente.

_GAP-DE-PRODUTO neste domínio: 7 endpoint(s) sem UI — ver anexo A.11._

---

## Anexo A — Rastreabilidade: endpoints GAP-DE-PRODUTO por domínio (para quem implementa)

### A.1 Autenticação, identidade, permissões e contexto (3)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| GET | `/api/admin/users/<user_id>/role` | data: {user_id,email,system_role,custom_role_id\|null,custom_role_name\|null,permissions\|null} | wrapper adminService.getUserCustomRole (adminService.ts:434) existe mas NENHUM componente o chama (grep); único caminho para admin de tenant (não-superadmin) ver a role customizada de um usuário — o equivalente /api/v1/admin/users/<id>/permissions é superadmin-only |
| GET | `/api/auth/me` | data: {id,email,name,role,is_active,created_at,updated_at,tenant_id,custom_role_id,permissions[]} | front atual NÃO chama (useAuth hidrata user do localStorage); único consumidor é scripts/smoke_test.sh (verificação, não produto). Novo front precisa de 'quem sou eu' para reidratar/validar sessão no boot |
| GET | `/api/v1/permissions/mine` | data: {role, permissions[]} | wrapper adminService.getMyPermissions (adminService.ts:186) sem nenhum chamador; front atual faz gating (useAuth.can) pelo permissions do login em localStorage, que fica obsoleto até o próximo login. Novo front deve usar /mine para atualizar gating sem relogar |

### A.2 Admin da plataforma (A) — tenants, usuários, planos, flags (4)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| PATCH | `/api/v1/admin/announcements/<announcement_id>` | data: {updated: true} | wrapper adminService.updateAnnouncement existe mas nenhuma página o chama — edição de comunicado não está na UI atual |
| GET | `/api/v1/admin/plans/<plan_id>/tenants` | data.tenants[]: {id,name,slug,is_active,created_at} | wrapper adminService.getPlanTenants sem consumidor; drill-down 'clientes deste plano' é capacidade plausível da tela de planos |
| GET | `/api/v1/admin/software-channels` | data.channels[]: {channel, target_ref, updated_at, updated_by} | sem UI; operado por curl no runbook de OTA — painel de canais/versões de software do edge é capacidade admin plausível |
| PUT | `/api/v1/admin/software-channels/<channel>` | data: {channel, target_ref, updated_at, updated_by} | sem UI; publicado via curl (runbook edge-ota) — 'publicar versão para canal' é ação admin plausível com confirmação |

### A.3 Admin da plataforma (B) — tickets, workers, auditoria, inventário, anúncios (13)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| GET | `/api/v1/admin/tenants/<tenant_id>/overview` | data: {tenant:{id,name,slug,plan,schema_name}, cameras[]:{id,name,status,active_module} (≤50), recent_alerts[]:{id,violation_type,confidence,created_at} (24h, ≤20), training_jobs[]:{id,name,status,module,created_at} (≤10)} | wrapper adminService.getTenantOverview existe mas nenhuma página o invoca — e o back responde 400 para qualquer tenant (bug da whitelist); 'visão geral do tenant' sem tela e sem back funcional |
| GET | `/api/v1/admin/users/<user_id>` | data: {user: {…todas colunas de users exceto password_hash, tenant_name, recent_actions[]:{action,target_type,target_id,created_at,ip_address} (≤10)}} | wrapper adminService.getUser existe mas nenhuma página o invoca — não há tela de detalhe de usuário |
| POST | `/api/v1/admin/users/<user_id>/force-password-reset` | data: {forced: true} | wrapper adminService.forcePasswordReset sem consumidor em páginas; além disso a flag não é aplicada no login |
| GET | `/api/v1/admin/users/<user_id>/sessions` | data: {sessions[]: {id,jti,ip_address,user_agent,created_at,expires_at}} | wrapper adminService.getUserSessions sem consumidor — não há UI listando sessões ativas (IP/UA) do usuário |
| GET | `/api/v1/admin/training-approvals/<approval_id>` | data: {approval: {…training_approvals, tenant_name, dataset_sample_urls[] (≤10 URLs R2 pré-assinadas, TTL 300s)}} | wrapper adminService.getTrainingApproval sem consumidor — não há tela de detalhe da aprovação com amostras do dataset |
| GET | `/api/v1/admin/workers/<tenant_schema>` | data: {worker: {…worker_registry, tenant_name, metrics_24h[]:{gpu_pct,vram_used_gb,fps_avg,cameras_active,recorded_at} (≤200), status, live_metrics\|null}} | wrapper adminService.getWorkerDetail sem consumidor — não há tela de detalhe do worker |
| GET | `/api/v1/admin/workers/<tenant_schema>/metrics` | data: {metrics[]: {gpu_pct,vram_used_gb,fps_avg,cameras_active,recorded_at}} (ordem asc; [] se worker não existe) | wrapper adminService.getWorkerMetrics sem consumidor — não há gráfico de série temporal do worker |
| GET | `/api/v1/admin/tickets/<ticket_id>` | data: {ticket: {…support_tickets, tenant_name, messages[]:{id,ticket_id,author_id,content,is_internal,created_at,author_email}}} | wrapper adminService.getTicket sem consumidor; TicketRow navega para /admin/tickets/:id mas a rota não existe (cai no catch-all) |
| PATCH | `/api/v1/admin/tickets/<ticket_id>` | data: {updated: true} | wrapper adminService.updateTicket sem consumidor — não há tela para triar ticket (status/prioridade/responsável) |
| POST | `/api/v1/admin/tickets/<ticket_id>/reply` | data: {message_id} | wrapper adminService.replyTicket sem consumidor — não há tela de resposta a ticket |
| GET | `/api/v1/admin/tickets/stats` | data: {stats: {open_count, critical_count, high_count, normal_count, low_count}} | wrapper adminService.getTicketStats sem consumidor — cabeçalho de KPIs de suporte não existe |
| GET | `/api/v1/announcements` | data: {announcements[]: {id,title,content,type,published_at}} | nenhum consumidor no front (o app do cliente não exibe comunicados); o admin já publica via /admin/announcements (outro domínio) |
| POST | `/api/v1/announcements/<announcement_id>/read` | data: {read: true} | nenhum consumidor no front — par do GET acima |

### A.4 Admin auxiliar — branding, integrações, versões, observabilidade, consoles de teste/demo (6)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| GET | `/api/v1/admin/branding/tenants` | data.tenants[]: {id, name, slug, is_active, branding:{JSONB cru}} | Sem consumidor (só testes). A necessidade existe na UI atual: AdminBrandingTenantsPage faz N+1 (GET /v1/admin/tenants + GET /admin/tenants/<id>/branding por tenant, l.23-29). Ressalva: este endpoint é da família legada de branding/routes.py — devolve branding CRU (sem merge com _DEFAULT_BRANDING) e inclui tenants inativos; usar como está exige merge no cliente ou ajuste no backend. |
| DELETE | `/api/v1/admin/demo-events` | data: {deleted:int} | Única chamada está em modules/admin/pages/DemoEventsPage.tsx, página NÃO roteada (não alcançável a partir de main.tsx; ver frontend-flows-modules §(c) #16) — capacidade de semear eventos demo para Investigação é funcionalidade de produto do superadmin |
| GET | `/api/v1/admin/demo-events` | data: {counts[]: {module_code, count, last_seeded_at}, total} | Única chamada está em modules/admin/pages/DemoEventsPage.tsx, página NÃO roteada (não alcançável a partir de main.tsx; ver frontend-flows-modules §(c) #16) — capacidade de semear eventos demo para Investigação é funcionalidade de produto do superadmin |
| POST | `/api/v1/admin/demo-events/seed` | data: {created:int, batch_id:uuid} | Única chamada está em modules/admin/pages/DemoEventsPage.tsx, página NÃO roteada (não alcançável a partir de main.tsx; ver frontend-flows-modules §(c) #16) — capacidade de semear eventos demo para Investigação é funcionalidade de produto do superadmin |
| GET | `/api/v1/admin/introspection` | data: {ru_maxrss, ru_maxrss_mb, rss_current_mb\|null, uptime_seconds, requests_served (por worker), storage_backend:'r2'\|'local'\|'desconhecido', worker_class, service_type, live_view:{segments_buffered, bytes_buffered, avg_segment_bytes, streams_active, degraded}} | Sem consumidor em código (front/edge/scripts/deployments; só testes unitários). Criado no mutirão 1.2 como diagnóstico manual via curl (docstring: separa platô de vazamento de memória) — não é código morto, mas a capacidade (RSS/uptime/requests por worker, backend de storage, gauges de live view) não tem superfície no produto; candidato a card 'Processo' na aba Infra da Observabilidade. Indeterminado: se uma UI foi planejada (nenhum doc fora de docs/migration menciona). |
| GET | `/api/v1/admin/versions/<version_id>` | data.version: {todas as colunas de system_versions incl. config_snapshot:{tenants[],plans[]}, git_sha, created_by_email, rolled_back_by_email, changelog[]: {...,created_by_email}} | adminService.getVersion existe mas NENHUMA página o usa — detalhe de versão (snapshot p/ preview de rollback + changelog da versão) não tem UI |

### A.5 Câmeras, streams/live view e gravadores (18)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| DELETE | `/api/cameras/<camera_id>` | data {deleted: true} | Front removeu o botão de propósito (issue #428, cameraService.ts comenta) — exclusão definitiva administrativa continua no back sem tela nem confirmação forte. |
| GET | `/api/cameras/<camera_id>` | data = câmera (SELECT * menos password_encrypted — inclui também model_epi_id/model_quality_id/model_counting_id, schedule_rules, brand, model, ip, rtsp_substream_url, substream_ok, probe_status, notes, module_code, active_model_id) | cameraService.get existe (cameraService.ts:173) mas nenhuma página/componente o chama; detalhe de câmera é necessidade plausível de produto (tela de detalhe/diagnóstico). |
| GET | `/api/cameras/<camera_id>/effective-model` | data {camera_id, model_id\|null, module, source: 'override'\|'inherited'} | Nenhuma tela mostra 'qual modelo está valendo nesta câmera' (override × herdado do módulo); necessidade plausível na ficha da câmera. |
| GET | `/api/cameras/<camera_id>/model-config/history` | data {deployments[]: {…mesmo shape do deployment…}, total} | Histórico de deployments por câmera existe no back; a aba de escopo não mostra linha do tempo. |
| POST | `/api/cameras/<camera_id>/model-config/rollback` | data.deployment (NOVO registro com model_id/config do alvo) | Rollback de configuração de modelo por câmera sem UI. |
| PATCH | `/api/cameras/<camera_id>/module` | data {camera_id, active_module} | Trocar o módulo ativo de uma câmera (ou pausar com 'none') não tem tela; CameraModelScope só lê active_module. |
| GET | `/api/cameras/<camera_id>/module/current` | data {camera_id, current_module\|null, paused: bool, default_module} | Resolve schedule_rules × horário atual; útil para badge 'módulo rodando agora' — sem consumidor. |
| GET | `/api/cameras/<camera_id>/retention` | data {camera_id, retention_days\|null, tenant_default_days, effective_days, allowed_tiers:[1,7,30,90]} | adminService.getCameraRetention existe (adminService.ts:444) mas nenhuma página chama; retenção por câmera é configuração plausível de produto. |
| PUT | `/api/cameras/<camera_id>/retention` | data {camera_id, retention_days} | adminService.setCameraRetention (adminService.ts:447) sem chamador; não há UI de tier por câmera. |
| PUT | `/api/cameras/<camera_id>/schedule` | data {camera_id, schedule_rules} | Agendamento de módulo por horário (JSONB) sem UI. |
| GET | `/api/v1/recorders` | data {recorders[]: {id,tenant_id,name,host,port,username,protocol,manufacturer,channels,retention_days,status,last_tested_at,last_error,created_by,created_at (sem password_encrypted)}, total} | Gravadores NVR/DVR (ADR-0034) existem no back e são pré-requisito do coletor do edge (RECORDER_CLOUD_ID), mas não há tela de cadastro/lista — hoje se cria via curl. |
| POST | `/api/v1/recorders` | data.recorder (sem senha) | Cadastro de gravador sem UI (mesma família). |
| DELETE | `/api/v1/recorders/<recorder_id>` | data {deleted: true, id} | Remoção de gravador sem UI. |
| GET | `/api/v1/recorders/<recorder_id>` | data.recorder | Detalhe de gravador sem UI. |
| PUT | `/api/v1/recorders/<recorder_id>` | data.recorder | Edição de gravador sem UI. |
| POST | `/api/v1/recorders/<recorder_id>/extract-frames` | data {task_id, recorder_id, status: 'queued'} | Disparo de extração de frames do gravador sem UI; não há endpoint de status do task_id neste domínio. |
| GET | `/api/v1/recorders/<recorder_id>/recordings` | data {recorder_id, channel, segments[]: {channel, start, end}} | Timeline de gravações (ADR-0034) para escolher trecho a extrair — sem UI. |
| POST | `/api/v1/recorders/<recorder_id>/test` | data.recorder (com status: online\|offline\|error, last_tested_at, last_error) | Teste de conexão de gravador sem UI. |

### A.6 Treinamento, anotação, propagação e busca (5)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| DELETE | `/api/classes/<int:class_id>` | data: {deleted: true, id} | Página de classes só arquiva (PATCH archived); excluir classe sem uso (erro de digitação) é ação plausível que o back já suporta com guarda 409. |
| GET | `/api/training/active-learning/queue` | data: {frames[]: {id, video_id, camera_id, filename, r2_key, model_confidence, uncertainty_score, ...}, total, module} | Fila de rotulagem priorizada por incerteza (WS-B2/ADR-0031) pronta no back, sem tela que a consuma. |
| POST | `/api/training/frames/<frame_id>/validate` | {success, frame_id, validated_at} | Revisão humana de anotação (status 'reviewed' já filtrável em GET /api/training/images?status=reviewed) sem nenhuma UI que marque o frame como validado. |
| POST | `/api/training/images/upload` | data: {uploaded, failed, failed_files[]: {filename, reason}, images[]: {id, r2_key, filename, source:'upload', width, height, module_code}} | Front ainda sobe imagens pelo legado POST /api/v1/videos/images/upload (cria vídeo sintético user-scoped, sem 207); este é o upload tenant-scoped (video_id NULL, source=upload) que a galeria nova já lista. |
| GET | `/api/training/jobs/<job_id>/status` | data: linha completa de training_jobs (inclui callback_token) | Detalhe de um job do histórico (deep-link/drawer) — wrapper trainingService.getJobStatus existe mas só é referenciado por hooks/useTraining.ts (hook sem consumidor); nenhuma tela chama. Pré-condição para o novo front: checagem de posse (user/tenant) + strip de callback_token (hoje IDOR cross-tenant). |

### A.7 Modelos (rollout), datasets, cenários, módulos e regras (16)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| GET | `/api/modules/<module_code>` | data.module: {id, tenant_id, module_code, enabled, config, activated_at, expires_at} | Wrapper moduleService.get() existe (moduleService.ts:40) mas nenhuma página/hook o chama (useModules.getModule filtra a lista local de GET /api/modules/). Wrapper morto ≠ consumo — mesmo critério dos demais domínios (cameraService.get, trainingService.getJobStatus). Detalhe isolado de módulo é dispensável no novo front: a lista já devolve os mesmos campos. |
| PATCH | `/api/modules/<module_code>/classes/<class_id>` | data.class: {id, module_code, class_id, class_name, display_name, icon, is_violation, color, dino_prompt, is_active} | Gestão do catálogo de classes por módulo (ativar/desativar) sem UI; o front atual edita só classes do tenant via PATCH /api/classes/<id> (outro domínio). Efeito é GLOBAL (todos os tenants) — pertence a tela de plataforma (superadmin), não a admin de tenant. |
| GET | `/api/rules` | data.rules[]: {id, tenant_id, camera_id\|null, violation_type, min_duration_seconds, min_occurrences, time_window_seconds, create_alert, enabled, created_at, updated_at} | CRUD de regras de alerta (duração/ocorrências por câmera ou tenant) sem UI no front atual; configuração plausível do módulo EPI — MAS nenhum motor aplica as regras hoje (só o cenário as lê). |
| POST | `/api/rules` | data.rule: {id, tenant_id, camera_id, violation_type, min_duration_seconds, min_occurrences, time_window_seconds, create_alert, enabled, created_at, updated_at} | Par do GET — criação de regra de alerta sem UI. |
| DELETE | `/api/rules/<rule_id>` | data: {deleted: true} | Par do CRUD de regras sem UI. |
| GET | `/api/rules/<rule_id>` | data.rule: {id, tenant_id, camera_id, violation_type, min_duration_seconds, min_occurrences, time_window_seconds, create_alert, enabled, created_at, updated_at} | Par do CRUD de regras sem UI. |
| PUT | `/api/rules/<rule_id>` | data.rule: {...mesma shape} | Par do CRUD de regras sem UI. |
| POST | `/api/rules/<rule_id>/toggle` | data.rule: {...mesma shape, enabled invertido} | Par do CRUD de regras sem UI. |
| GET | `/api/v1/datasets` | data: {datasets[]: {id, tenant_id, module_code, name, description, created_by, created_at}, total} | Pipeline de treino (WS-A3) — datasets pai + versões COCO; front atual não tem tela de datasets (TrainingPage.tsx:405 cria job sem dataset_version_id). No DEV há 2 datasets e 12 dataset_versions criadas fora do front (indeterminado por qual via: nenhum script no repo chama /api/v1/datasets). |
| POST | `/api/v1/datasets` | data.dataset: {id, tenant_id, module_code, name, description, created_by, created_at}; message 'Dataset criado' | Criação de dataset pai sem UI. |
| GET | `/api/v1/datasets/<dataset_id>` | data: {dataset{...}, versions[]: {id, user_id, dataset_id, tenant_id, module_code, version, split, augmentations, coco_r2_key, export_format, status:'building'\|'ready'\|'error', frame_count, train_count, val_count, test_count, class_distribution, metadata_key, created_by, created_at}} | Detalhe de dataset + versões (é o endpoint de POLL do build) sem UI. |
| POST | `/api/v1/datasets/<dataset_id>/versions` | data: {task_id, dataset_id, version, split, format, status:'building'}; message 'Build da versão iniciado' | Build assíncrono de versão COCO sem UI — etapa obrigatória antes do treino real. |
| GET | `/api/v1/dataset-versions/<version_id>` | data.version: {...linha de dataset_versions, coco_files{train\|val\|test: {key, url}} (só quando status='ready' e coco_r2_key; vazio caso contrário)} | Detalhe de versão + download dos COCO por split sem UI. |
| GET | `/api/v1/models/<model_id>/drift` | data: {windows[]: {id, tenant_id, model_id, camera_id, window_start, window_end, detections_count, avg_confidence, class_distribution, drift_score, created_at}, total} | Janelas de drift por modelo (preenchidas por task de monitoramento) sem UI — painel MLOps/saúde do modelo é plausível. |
| GET | `/api/v1/models/<model_id>/eval` | data.evaluation: {id, tenant_id, model_id, champion_model_id, dataset_version_id, metrics, confusion_matrix, verdict:'pending'\|'promote'\|'reject' (EvalVerdict, CHECK da migration 101), created_at} | Resultado da avaliação campeão×desafiante (é o que gera o 409 do activate) sem UI — o usuário vê 'reprovado' sem conseguir ver por quê. |
| POST | `/api/v1/models/<model_id>/evaluate` | data: {task_id, status:'queued', model_id}; message 'Avaliação campeão×desafiante iniciada' | Disparo manual de avaliação (reavaliar contra outro split) sem UI. |

### A.8 Módulo Qualidade (inspeções, gate, estações, relatórios, treino) (19)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| POST | `/api/v1/quality/cameras/<camera_id>/toggle-setup-mode` | data: {camera_id, is_setup_mode} | wrapper qualityService.toggleSetupMode existe mas nenhuma página o chama; capacidade de 'modo setup' (pausa inferência) é de produto |
| GET | `/api/v1/quality/cep/<camera_id>` | data: {camera_id, baseline{mean_nok_rate,stddev_nok_rate,ucl,lcl,calculated_at}\|{}, recent_rates[]:{timestamp,rate,is_above_ucl} (últimas 24h por hora), current_status: in_control\|warning\|out_of_control} | wrapper qualityService.getCepData e componente CepChart.tsx existem mas nenhuma página importa; gráfico de controle (CEP) é capacidade de produto |
| GET | `/api/v1/quality/defect-categories` | data: {categories[]: {slug,label}} | wrapper qualityService.getDefectCategories sem chamador; lista serve a filtros de inspeção por categoria (tela de inspeções hoje é mock) |
| POST | `/api/v1/quality/gate/pieces` | data: {piece: linha de quality_pieces (status 'idle')} — 200 (não 201) | 1º passo do fluxo do gate (criar peça) sem nenhuma UI — tablet/kiosk assume que a peça já existe (OCR/identify também sem UI) |
| POST | `/api/v1/quality/gate/pieces/<piece_id>/identify` | data: {piece} | transição idle→identified (leitura OCR/manual do nº da peça) sem UI; tablet só reage ao evento |
| POST | `/api/v1/quality/gate/pieces/<piece_id>/result` | data: {piece} | ninguém chama hoje (nem worker, nem front — só test_gate_routes.py) MAS é o único caminho que avança a state machine após a inferência (ok: v1→v2→waiting_bench_b→v3→approved + Wiser + torre; nok: rework_vN + quality_reworks); o worker só publica em Redis e o socket_bridge não tem handler para quality:gate_result:. O design precisa decidir quem chama (worker/backend ou UI do operador) — por isso GAP e não ÓRFÃO. Está quebrado: routes.py:1667-1676 passa 8 posicionais para GateService.process_inspection_result (gate_service.py:240-249, 7 params) → TypeError → 500 (teste usa MagicMock sem autospec). |
| PATCH | `/api/v1/quality/gate/reworks/<rework_id>/complete` | data: {rework (completed_at, duration_seconds)} | fechar retrabalho (calcula duração e acumula total_rework_time_seconds na peça) não tem UI — QualityReworkPage é só leitura |
| GET | `/api/v1/quality/gate/stations/<station_code>` | data: {station_status{station_code, station{...}, current_piece{...}\|null, cameras[]}} — bancada inexistente devolve {station_code,current_piece:null,cameras:[]} (200, não 404) | estado detalhado da bancada (peça atual) sem UI — o kiosk /tablet/:station monta estado só pelo WebSocket e não carrega snapshot inicial |
| PUT | `/api/v1/quality/gate/stations/<station_code>` | data: {station} | edição de bancada: o front TENTA editar via PATCH (QualityConfigPage.tsx:121) mas a rota é PUT → 405; a capacidade existe, a UI atual está quebrada |
| GET | `/api/v1/quality/gate/stats/overview` | data: {stats{pieces_today,pieces_approved,pieces_nok,nok_rate,rework_count}} | KPIs do dia do gate sem UI (dashboard/summary cobre parte; este inclui rework_count) |
| GET | `/api/v1/quality/inspections` | data: {inspections[]: quality_inspections.* + camera_name, total, page, per_page, pages} | wrapper qualityService.getInspections sem chamador — QualityInspectionsPage (rota /quality/inspections) é 100% mock local (makeInspections); listagem real de inspeções é tela central do módulo |
| POST | `/api/v1/quality/inspections/<inspection_id>/create-training-job` | data: {job_id, status:'queued'} — 201 | é o endpoint que o botão 'criar job' do AnnotationWorkspace DEVERIA chamar (hoje chama POST /training/jobs sem body → 400); ninguém chama este |
| GET | `/api/v1/quality/inspections/summary` | data: {total, ok, nok, ok_rate, nok_rate, pending_feedback, confirmed, rejected, retrain_requested, cep_alerts_count, defect_distribution{categoria:n}, shift} | só useShiftMetrics/ShiftMetricsBar/DefectPareto (nenhum importado por página roteada); métricas de turno + pareto são capacidade de produto |
| GET | `/api/v1/quality/reference-snapshots/<camera_id>` | data: [ {id,camera_id,production_order,r2_key,captured_at} ] (array direto, últimos 10) | wrapper qualityService.getReferenceSnapshots sem chamador; snapshots de referência (setup da OP) são capacidade de produto |
| GET | `/api/v1/quality/reports/shift` | data: {shift, date, total_ok, total_nok, total, nok_rate, defect_pareto[]:{defect_class,count,pct}, generated_at} | wrapper qualityService.getShiftReport sem chamador; relatório de turno é capacidade de produto |
| GET | `/api/v1/quality/reports/shift/pdf` | bytes PDF (reportlab; tabela Total/OK/NOK/Taxa OK). 501 se reportlab ausente. | getShiftReportPdfUrl (wrapper sem chamador) monta URL sem camera_id e sem Authorization → 400/401; exportar PDF de turno é capacidade de produto |
| GET | `/api/v1/quality/training/jobs` | data: [ {id,name,status,source_type,frames_extracted,frames_annotated,metrics,error_message,active,created_at,updated_at} ] (array direto, sem paginação) | só QualityTrainingPage.tsx, que NÃO está roteada (QualityLayout.tsx:83 usa a TrainingPage genérica) — histórico de jobs do módulo é capacidade de produto |
| GET | `/api/v1/quality/training/jobs/<job_id>` | data: linha completa de quality_training_jobs (flat) | wrapper qualityService.getTrainingJob sem chamador; detalhe do job (métricas/erro) é capacidade de produto |
| POST | `/api/v1/quality/training/models/<model_id>/activate` | data: {model_id, cameras_updated} | só QualityTrainingPage.tsx (não roteada), e com body errado ({camera_id} → 400); ativar modelo treinado em câmeras é capacidade central de produto |

### A.9 Edge / frota — enrollment, heartbeat, comandos, eventos, monitoring (13)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| GET | `/api/v1/edge/commands` | data {commands[]: {id, command_type, payload, status, command_id, created_at, dispatched_at, completed_at}, count} | Console de comandos do site (histórico/status dos comandos enviados ao box) não tem UI; agente usa só /pending e PATCH |
| POST | `/api/v1/edge/commands` | 201: data {command{id,status,created_at}, command_id, created:true} \| 200: data {command_id, created:false, reason:'duplicate'} | Envio manual de comando ao box (ex.: update_camera_config) sem UI; monitoring/snapshot criam comandos por repo direto, não por esta rota |
| POST | `/api/v1/edge/devices/<device_pk>/revoke` | data {revoked:true, device_id, revoked_at} | Revogar device (corte imediato: heartbeat passa a 403) sem UI |
| POST | `/api/v1/edge/enrollment-tokens/<token_id>/revoke` | data {revoked:true, token_id} | Gestão de tokens de enrollment sem UI |
| GET | `/api/v1/edge/events` | data {events[]: {id, device_id, camera_id, module, event_type, payload, evidence_r2_key, occurred_at, received_at, dedup_key}, count} | Timeline de eventos do box (detection/camera_offline/model_loaded…) sem UI; hoje tabela vazia no DEV porque o produtor está quebrado (ver findings) |
| POST | `/api/v1/edge/sites` | data {site{id, tenant_id, name, description, location, deployment_mode, status, created_at, created_by}} | Criar site edge (passo 1 do onboarding de um cliente/planta) não tem UI |
| GET | `/api/v1/edge/sites/<site_id>` | data {site{…_serialize_site, device_count, derived_health (offline\|healthy\|degraded\|critical), last_heartbeat_at}} | Página de detalhe do site (cabeçalho com saúde + nº devices) sem UI; o painel atual monta detalhe só com heartbeats/summary |
| GET | `/api/v1/edge/sites/<site_id>/devices` | data {devices[]: {id (pk p/ revoke), device_id, device_name, revoked, last_seen_at, enrolled_at}} (sem public_key/fingerprint — C-05) | Lista de devices do site (com revogar) sem UI tenant-scoped; só o /monitoring superadmin mostra devices |
| GET | `/api/v1/edge/sites/<site_id>/enrollment-tokens` | data {tokens[]: {id, created_at, expires_at, used_at, used_by_device_id, status ∈ {active,used,expired}}} (sem hash/plaintext) | Gestão de tokens de enrollment por site sem UI |
| POST | `/api/v1/edge/sites/<site_id>/enrollment-tokens` | data {token (plaintext, exibido UMA vez), token_id, site_id, expires_at (+24h), used_at:null} | Gerar token one-time para enrolar o box só existe via curl de runbook (docs/edge/DIAGNOSTICO_OBSERVABILIDADE_2026-07-21.md:128) |
| GET | `/api/v1/site-gateways/<site_id>` | data {gateway{id, kind, model, wg_public_key, wg_endpoint, lan_subnet, status, last_seen, config{}, created_at, updated_at}} | Configuração de rede do site (MikroTik/WireGuard, ADR-0020) sem UI; tabela vazia no DEV |
| PUT | `/api/v1/site-gateways/<site_id>` | data {gateway{id, kind, status, created_at, updated_at}} (parcial — não devolve os campos enviados) | Cadastro/edição do gateway do site sem UI |
| PATCH | `/api/v1/site-gateways/<site_id>/status` | data {gateway{id, status, last_seen}} | Marcar status do gateway na tela de rede do site; docstring original previa o edge como chamador, mas exige JWT de usuário (device não consegue) — hoje sem consumidor |

### A.10 Eventos, alertas, notificações, feedback, verificação, vídeos, storage, retenção (18)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| GET | `/api/v1/feedback` | data: {feedback[]: {id,module,camera_id,detection_ref,frame_r2_key,verdict,corrected_class,created_by,created_at}, count} | Flywheel de feedback do operador (migration 059) sem UI; tabela com 0 linhas no DEV |
| POST | `/api/v1/feedback` | data: {feedback: {id, verdict, created_at}} | Botão 'detecção correta/errada' no evento/alerta não existe no front atual |
| GET | `/api/v1/feedback/summary` | data: {summary[]: {module, verdict, count}} | Painel de qualidade do modelo (taxa de acerto por módulo) sem UI |
| GET | `/api/v1/notifications/channels` | data: {channels[]: {id,type,recipients[],enabled,created_at,updated_at} (config omitido), count} | Configuração de canais de notificação (whatsapp/telegram/email/webhook) sem UI; tabela vazia no DEV |
| POST | `/api/v1/notifications/channels` | data: {channel: {id,type,recipients,enabled,created_at}} | Tela admin de canais de notificação não existe |
| DELETE | `/api/v1/notifications/channels/<channel_id>` | data: {deleted: true} | Tela admin de canais de notificação não existe |
| PATCH | `/api/v1/notifications/channels/<channel_id>` | data: {channel: {id,type,recipients,enabled,updated_at}} | Tela admin de canais de notificação não existe |
| GET | `/api/v1/tenant/retention` | data: {tenant_id, default_retention_days(override\|null), plan_retention_days, effective_retention_days, allowed_tiers:[1,7,30,90]} | Configuração de retenção padrão do tenant sem UI; o front usa a variante /api/cameras/tenant/retention (dead code em adminService) e AdminRetentionPage grava via PUT admin/tenants |
| PUT | `/api/v1/tenant/retention` | data: {tenant_id, default_retention_days} | Tela de retenção do tenant (admin do cliente) não existe |
| DELETE | `/api/v1/videos/<video_id>` | data: {deleted:true, video_id, already_gone?:true} | Gestão de vídeos de treino enviados (excluir) sem UI no pipeline v1 |
| POST | `/api/v1/videos/<video_id>/extract` | data: {video_id, status:'extracting'} | Disparo de extração após upload multipart (/upload) — par do fluxo A do pipeline v1, sem UI |
| POST | `/api/v1/videos/<video_id>/retry-extraction` | data: {video_id, status:'extracting'} | Ação 'tentar novamente' para vídeo com status error — sem UI |
| GET | `/api/v1/videos/<video_id>/status` | data: {video: {id,user_id,filename,original_filename,file_size,duration_seconds,status,frame_count,frames_expected,error_message,created_at,module_code,progress_percent}, frames: {<quality_status>: n}} | Tela de progresso da extração (poll) do pipeline v1 — sem UI |
| POST | `/api/v1/videos/<video_id>/upload-complete` | data: {video_id, status:'queued'} | Passo 3 do fluxo B (presigned PUT direto no R2) — sem UI |
| GET | `/api/v1/videos/storage` | data: {used_bytes, limit_bytes(5GB fixo), used_formatted, limit_formatted, percentage} | Indicador de cota de armazenamento de treino — sem UI |
| POST | `/api/v1/videos/upload` | data: {id,user_id,filename(storage key raw-videos/<user>/<id>/<nome>),original_filename,file_size,status:'uploaded',...} | Fluxo A do pipeline v1 (upload via API) sem UI; front usa o legado POST /api/training/videos |
| POST | `/api/v1/videos/upload-url` | data: {upload_url (presigned PUT R2, TTL 900s), video_id, storage_key} | Passo 1 do fluxo B (upload direto ao R2) — sem UI |
| GET | `/api/verification/queue/count` | data: {count} | Badge de pendências na navegação ('Verificação') — o sidebar atual não mostra contagem; além disso o endpoint está quebrado (sempre 0) |

### A.11 Dashboard, relatórios, contagem, operações, abastecimento, chat, monofatura, health (7)

| Método | Path | O que o back oferece (resposta) | Por que é gap |
|---|---|---|---|
| PATCH | `/api/counting/sessions/<session_id>/plate` | data: {session_id, plate_text(normalizada), plate_confidence, plate_review, plate_manual, plate_format('mercosul'\|'antiga')} | LPR (task-050): registrar/corrigir placa com flag de revisão — nenhuma tela usa (FuelingValidationPage edita truck_plate via PATCH genérico, não plate_text) |
| GET | `/api/counting/sessions/plates` | data.sessions[]: {id,tenant_id,camera_id,module_code,status('running'\|'stopped'),total_counts{},started_at,ended_at,bay_id,truck_plate,direction,expected_count,divergence,video_clip_url,manual_count,acceptance_status,plate_text,plate_confidence,plate_review,plate_manual} + camera_name (plate_text IS NOT NULL; LIMIT 200) | fila de revisão de placas OCR (review_only) sem tela |
| GET | `/api/operations/<int:operation_id>/results` | data.results[]: {id, operation_id, result_json{}, evaluated_at}, data.operation_id | histórico de avaliações da operação (populado pelo worker OperationsEngine) sem nenhuma tela que o exiba |
| GET | `/api/reports/compliance` | data: {summary{compliance_rate,total_violations,top_cameras[]{camera_id,count},trend_by_hour[]{hour,count}}, pdf_url (pré-assinada R2, TTL 3600s), period{period,from,to}} | relatório de compliance EPI com PDF (gerado on-demand e diariamente pelo Celery beat generate_daily_compliance_reports) sem nenhuma tela para disparar/listar/baixar |
| POST | `/api/v1/monofatura/pieces/<piece_id>/scan` | data.session: {id,piece_id,stage,status('open'\|'completed'),camera_id,started_at,finished_at,result{},evidence_r2_key,created_at} | inbound 'peça bipada' da integração monofatura (ADR-0053/task-108) — sem consumidor no repo; contrato real do cliente pendente, mas uma UI/tablet de bipagem é necessidade de produto |
| POST | `/api/v1/monofatura/pieces/<piece_id>/stages/<stage>/complete` | data.session: {id,piece_id,stage,status('open'\|'completed'),camera_id,started_at,finished_at,result{},evidence_r2_key,created_at} (status='completed') | fechamento de etapa com resultado por atributo + evidência; sem consumidor no repo |
| GET | `/api/v1/monofatura/sessions` | data.sessions[]: {id,piece_id,stage,status('open'\|'completed'),camera_id,started_at,finished_at,result{},evidence_r2_key,created_at} | consulta de sessões de inspeção por peça sem tela |

