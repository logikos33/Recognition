# Pacote para o design — o que falta desenhar

> **Este documento é para ser colado inteiro numa sessão do Claude Design.**
> Ele não pressupõe conhecimento do código. Cada item diz o que aconteceu, o que
> foi feito no lugar, o que precisamos desenhado, e **qual rota do backend já
> existe** — para o design não desenhar no vácuo.
>
> Gerado em 2026-08-29. Todas as rotas citadas foram conferidas contra os
> blueprints reais do backend nesta data.

---

## Contexto em 5 linhas

1. O shell Logikos Vision e as 8 telas do módulo EPI estão **no ar no DEV**, sob
   o prefixo `/novo`, convivendo com o front atual — que segue inteiro e não
   mudou de comportamento.
2. Desde o handoff de 23/08 o produto ganhou coisas que o desenho não previa:
   badge de procedência, motivo do veredito, polaridade de 3 estados, aba de
   escopo por câmera e fila por incerteza. Todas foram preservadas na migração.
3. A comparação função-a-função entre cada tela antiga e sua substituta achou
   **42 perdas alegadas, 22 confirmadas** por um revisor independente.
4. Por isso **o front antigo não pode ser apagado**: 6 telas estão marcadas
   `SUBSTITUIDA` (têm substituta, mas ela não faz tudo) e só 1 é removível.
5. Faltam ainda as fases F2 (Kiosk), F4 (Qualidade/Carga), F5 (Estúdio/TV/Admin/
   Acesso) e F6 (Mobile) — **154 arquivos** do front atual ainda sem migrar.

---

## Como isto foi decidido

**Tela sem desenho não se inventa.** Onde faltou desenho, implementamos o mínimo
seguindo o Manual Logikos e os tokens `--lk-*`, e o item entrou nesta lista.
Implementar seguindo a identidade **não** dispensa o desenho oficial.

**Zero dado inventado em tela de produto.** Onde o backend não serve o dado que o
desenho previa, a tela não o exibe — e também não fica explicando ao operador o
que falta. Isso é assunto desta lista.

---

# 🔴 BLOQUEIA FASE — sem desenho, o front antigo não sai

## 1. Ajustar a câmera + saúde do equipamento

**O que se perde sem isto:** ninguém consegue dizer "esta câmera roda a 5 quadros
por segundo em qualidade média e coleta frames de treino no stream principal", e
ninguém vê GPU, memória, fila, latência e temperatura. É o **único lugar do
produto que grava a resolução dos frames que entram no dataset de treino**, e o
único freio contra sobrecarregar o mini PC do cliente.

**Backend pronto:** `GET /api/cameras/<id>/health-context` (há alias em
`/api/v1/cameras/<id>/health-context`) devolve
`gpu_pct`, `gpu_mem_pct`, `cpu_pct`, `queue_depth`, `inference_fps`,
`inference_latency_ms`, `gpu_temp_c`, `decode_pct` + a demanda de FPS do site.
Gravação pelo update da câmera (FPS 1/5/10/15/30 · qualidade `low`/`medium`/`high`
· coleta `Principal (máxima)` / `Substream (704×480)`).

**Já rascunhado** — artboard `Main.dc.html` em `docs/design/handoff-v2/`.

## 2. Corrigir a caixa da detecção

**O que se perde:** quando a IA marca a caixa no lugar errado, o operador não tem
como redesenhá-la — nem arrastando, nem digitando —, e some a linha "caixa
corrigida por Fulano". É o gesto que transforma erro da IA em dado bom, e o
caminho digitado é o acessível para quem não usa mouse com precisão.

**Backend pronto:** `PATCH /api/alerts/<id>/violations` com
`{correcoes: [{index, bbox}]}`; `bbox` é `[x, y, largura, altura]` em **pixels do
frame original**, canto superior esquerdo. Devolve `violations` e
`correcao_ultima` (com `.por` — a autoria).

**Já rascunhado** — artboard `CorrigirCaixa.dc.html`.

## 3. Montar a parede de câmeras

**O que se perde:** escolher qual câmera fica em qual quadrinho ("Portaria sempre
no canto superior esquerdo"), arrastar para trocar, e salvar com nome. Com 28
câmeras o operador **decora posição, não nome** — sem posição fixa ele varre a
tela inteira a cada alerta.

**Backend:** `GET /api/cameras` lista as câmeras. **O layout NÃO tem endpoint** —
hoje vive no navegador de quem salvou (máximo 10). É a pergunta aberta do item.

**Já rascunhado** — artboard `ParedeCameras.dc.html`.

## 4. As 10 telas vivas que o handoff nunca desenhou

Estas rotas existem, têm gente usando, e ficaram fora do handoff. Enquanto não
houver desenho elas seguem no shell antigo — o que significa que **o produto tem
duas caras** para quem navega entre elas.

| Rota | O que faz | Backend |
|---|---|---|
| `/modules` | seleção de módulo — a primeira tela após o login de quem tem mais de um | `GET /api/modules` |
| `/epi/cameras/triagem` | triagem de câmeras | `GET /api/cameras` |
| `/epi/cameras/:id/operations` | operações da câmera (motor em produção) | `GET`/`POST /api/cameras/<id>/operations` |
| `/epi/cameras/:id/scenario` | editor de cenário — região sobre o vídeo | `/api/v1/scenarios` |
| `/epi/health` | saúde de streams | `/api/streams` |
| `/epi/sites-health` | saúde por site | `/api/v1/edge` |
| `/epi/sites` | sites do tenant | `/api/v1/edge` |
| `/epi/edge-observability` | observabilidade do edge (o Jetson no cliente) | `/api/v1/edge` |
| `/epi/investigation` | investigação | `/api/v1/events` |
| `/monitoring` | monitoramento do edge | `/api/v1/edge` |

**O que precisamos:** sua priorização entre as 10 — quais valem desenho próprio e
quais podem ser variação de telas que você já desenhou.

**Atualização 31/08 — proposta da pista F5-LEVE:** 4 destas 10 rotas
(`/epi/health`, `/epi/sites-health`, `/epi/edge-observability` — parte de
telemetria — e `/monitoring` — parte de leitura) têm rascunho em
`docs/design/handoff-f5/Saúde da Operação.dc.html`. É **proposta aguardando
refino oficial do design**, não prancha aprovada — a pista gerou porque não
veio desenho oficial no lote e a regra manda propor em vez de implementar no
vácuo. Medido contra `services/api/app/api/v1/edge/routes.py` (sites/health,
overview, heartbeats, heartbeat-summary, devices) + `streams/routes.py`
(`/api/streams/status`, fora do envelope padrão) — de-para completo das 4
rotas na aba "Mapa de conexões" do próprio arquivo. As 4 viram **uma tela**
("Saúde da Operação", visão de frota tenant-scoped), não 4 telas separadas.
Achado: `/epi/edge-observability` e `/monitoring` hoje cobrem mais coisa do
que saúde de frota (curvas de treino do Estúdio; console de comando ao vivo)
— só a fatia de saúde se sobrepõe à proposta, o resto fica onde está.

---

# 🟡 NASCEU SEGUINDO SÓ A IDENTIDADE — merece desenho oficial

Estas telas/controles não existiam e foram construídos seguindo o Manual e os
tokens, porque a operação precisava deles. Funcionam, mas ninguém os desenhou.

## 5. Seletor de cliente na topbar (superadmin)

**Por que nasceu:** um superadmin nasce no tenant dele — que no DEV está vazio —
enquanto os dados estão no RVB. A tela abria vazia e parecia quebrada. O
auto-assume existente desiste quando há mais de um cliente (e há três), e o banner
global só aparece **depois** de já haver contexto: mostrava a saída, nunca a
entrada.

**Como está:** botão âmbar "Escolher cliente" na topbar, só para superadmin e só
sem contexto assumido; ao escolher, volta na mesma tela. **Ainda em PR aberto**
(#553) — pode mudar antes de entrar, mas o problema que ele resolve não muda.

**Backend pronto:** `GET /api/v1/admin/tenant-context/tenants` ·
`POST /api/v1/admin/tenant-context/tenants/<id>/assume`.

**O que precisamos:** o desenho oficial deste momento — é a primeira coisa que um
superadmin vê e hoje é um botão que eu desenhei.

## 6. White-label do shell escuro

**O que aconteceu, medido:** ligamos as superfícies do shell novo ao tema do
tenant. Aberto com o RVB, o shell escuro virou **fundo branco com texto azul**
(`#0080ff`) e borda azul. Não era bug — são os valores de white-label reais
daquele cliente, escolhidos para o shell **claro** antigo.

**Como está:** só a **cor de marca** (`--color-primary`) vem do tenant. As
superfícies ficam nos valores do desenho. Estado (verde/âmbar/vermelho) e o
magenta do loader ficam fora de propósito — o primeiro é semântica de segurança,
o segundo é assinatura da Logikos.

**Backend pronto:** `GET /api/v1/tenant/branding`.

**O que precisamos:** (a) quais tokens o cliente pode trocar no shell escuro e
quais são intocáveis; (b) **piso de contraste** por token aberto — hoje um cliente
pode escolher uma cor de marca que some no fundo escuro e nada impede; (c) o que
acontece com um logo claro sobre fundo escuro.

## 7. Estados do banner de contexto assumido

O handoff especifica 42px com faixa âmbar de 2px. O banner que existe é mais
antigo, tem lógica cara em volta (TTL de 30 min, renovação, expiração,
"Reassumir") e é global — restilizá-lo agora mudaria o front antigo junto.

**O que precisamos:** o desenho dos **estados**, não só do banner parado —
contexto ativo, contexto expirado com "Reassumir", e o momento da renovação. Hoje
o primeiro é vermelho e o segundo âmbar por decisão de implementação.

## 8. Ranking das câmeras com mais eventos

**O que se perde:** a lista das 10 câmeras que mais dispararam. A tela nova de
Relatórios mostra só a campeã. É por esse ranking que o gestor decide onde treinar
equipe e onde a câmera está mal posicionada.

**Backend pronto:** `by_camera` em `GET /api/v1/events/summary`.

**Já rascunhado** — artboard `RankingCameras.dc.html`.

## 9. Texto dos estados vazios

Cada tela precisa dizer algo quando não há dado, e o handoff não traz esses
textos. Foram escritos na implementação:

| Tela | Texto atual |
|---|---|
| Dashboard | "Sem dados para este módulo — nenhuma câmera está atribuída ao EPI ainda." |
| Eventos | "Nenhum evento no período — bom sinal, ou filtro demais." |
| Verificação | "Fila zerada — as decisões de hoje já alimentam o próximo treino." |
| Ações | "Nenhuma ação aberta — ações nascem de eventos." |
| Relatórios | "Sem dados no período selecionado — amplie o intervalo." |
| Câmeras | "Nenhuma câmera cadastrada" |

**O que precisamos:** sua revisão do tom. O estado vazio é a tela que o operador
mais vê quando tudo está bem. E note: "nenhum evento" pode significar *nada
aconteceu* ou *o filtro está apertado demais* — a diferença importa para quem
opera.

## 10. Modelos por câmera (escopo de detecção)

**O que aconteceu, medido:** `CameraModelScope.tsx` — e a cópia dele em
`app/epi/Cameras.tsx` (aba "Escopo") — nasceram sem desenho: é `<table>` com um
`<tr>` por câmera e checkbox **nativo** por classe em `flex-wrap`. Com as 14+
câmeras de um tenant real (28 no RVB) a tabela vira scroll infinito, e não há
como aplicar o mesmo modelo/escopo em várias câmeras de uma vez — hoje é um
salvamento manual por câmera.

**Como está:** proposta em
`docs/design/handoff-f5/Modelos por Câmera.dc.html` — chips em grade fluida
agrupados por par presença↔ausência (Capacete/Sem Capacete etc., confirmado em
`public.module_classes`: EPI tem 8 classes, não 13), linha de câmera
colapsável, seletor de modelo com alias + data + métrica curta (`— (ainda não
medido)` quando o número não existe, nunca `0,0%`), razão escrita ao lado do
Salvar quando ele está desabilitado, e o fluxo completo de **aplicar em massa**
(escolher origem → destinos → pré-visualizar o que muda, com badge por câmera
de "sem mudança"/"muda escopo"/"muda modelo"/"muda os dois" → aplicar, câmera
por câmera, com o que acontece se uma falhar). **É proposta da pista aguardando
refino oficial do design** — a régua desta lista manda propor em vez de
implementar no vácuo quando não veio desenho oficial no lote.

**Backend pronto:** `GET /api/cameras/model-config?module=<m>` (deployments
ativos, tenant-escopado, 1 chamada por módulo) · `GET /api/v1/models` (alias
legado `GET /api/training/models`, já devolve `map50` — a tela é a primeira a
mostrar esse número, não é dado novo) · `GET /api/v1/models/<id>` (classes que
o modelo de fato reconhece) · `POST /api/cameras/<id>/model-config` (salva
modelo + escopo de **uma** câmera; upsert, sempre grava histórico) ·
`GET/POST .../model-config/history` e `/rollback` (existem, fora do desenho
desta prancha).

**O que falta no backend:** aplicar em massa **não existe** — é o Pedido 1 da
prancha (`POST /api/cameras/model-config/bulk`, sucesso/erro por câmera).
Também não existe um jeito de "desligar" sem trocar de modelo, e a tela não
tem como confirmar que o equipamento do site aplicou o recorte por câmera
(vale hoje só na nuvem — issue #519). De-para completo na aba "Mapa de
conexões" do próprio arquivo; os 3 pedidos numerados estão na aba "Pedidos ao
backend".

---

## 15. Arquitetura de administração — o admin do cliente tem a chave e não tem a porta

**Como está, medido em 31/08:** o produto tem **dois papéis administrativos** e só um tem
painel. O papel `admin` do tenant já possui `admin:users`, `admin:roles` e `branding:write`
(`services/api/app/core/permissions.py`) — pode gerir a própria equipe, os papéis e a marca.
Mas a única porta administrativa é gateada por `admin:panel`, que é **superadmin-only**, e no
blueprint admin há **59 rotas `@require_superadmin` e zero `@require_admin`**.

Isso explica o relato de "dois admins convivendo": o cliente não tem onde administrar a própria
casa, e o superadmin vê tudo. Não é vazamento de menu por papel (o menu já respeita `admin:panel`)
— era vazamento por **link**: três `href` absolutos para o front antigo, corrigidos nesta rodada.

**Proposta da pista:** `docs/design/handoff-f5/Arquitetura de Administração.dc.html` +
`… — Conexões.dc.html` — quem vê o quê, como se troca de chapéu (assumir contexto com o banner
âmbar sempre visível), o princípio de nenhum menu vazado, e o de-para completo elemento × endpoint
× existe/insuficiente/não-existe. **É proposta da pista aguardando refino oficial.**

**Pedidos ao backend, nesta ordem:**
- **P1 (BLOQUEIA a tela Equipe)** — rotas de usuário passam a aceitar `admin:users` e, nesse caso,
  respondem apenas com gente do tenant do token. Cross-tenant → **404**, nunca 403.
- **P2** — auditoria escopada ao próprio tenant (`audit:read` é superadmin-only hoje; o cliente não
  vê quem desativou uma câmera na casa dele).
- **P3 (registro, não pedido)** — marca e papéis **já aceitam** admin de tenant (`/v1/roles`,
  `PUT /v1/admin/branding`): é só construir a tela. Anotado para ninguém criar endpoint por engano.

## 16. Catálogo de modelos — a métrica que existe não é a que a tela mostra

**Como está, medido em 31/08 no DEV:** os **8 modelos** do RVB têm `map50`, `precision` e `recall`
iguais a **zero literal** (nunca gravados — por isso o guard `!= null` da rodada #1 os deixava
passar como "0,0%"), e **7 dos 8** estão sem `display_name`, então o cliente lê
"RF-DETR - Job 3091cfc9".

**O que mudou nesta rodada:** passou a existir uma métrica real — **121 vereditos humanos** na
fila de verificação. Ela mede o que o supervisor quer saber ("quantos avisos valeram a pena"),
não o que o treino registrou. Precisão global medida: **48,8%** (59 confirmados / 62 falsos); por
classe vai de 69,7% (Sem luvas) a 30,4% (Sem óculos).

**Proposta da pista:** `docs/design/handoff-f5/Catálogo de Modelos.dc.html` — o card diz
"de cada 10 avisos, ~5 são reais" com o `n` ao lado, quebra por classe, três estados
(em produção × em observação × disponível), linhagem e dataset, e "—" com dignidade onde ninguém
julgou. **É proposta da pista aguardando refino oficial.**

**Pedidos ao backend:**
- **P1 (é o número central do card)** — precisão por classe/modelo agregada a partir de
  `alerts.verification_verdict`. O cálculo já existe fora da API em
  `scripts/ops/calibracao_classes.py`; falta promover a endpoint.
- **P2** — "o que mudou" entre versões (delta de imagens/classes). Sem ele o card entrega alias +
  data e nada de inventado.
- **P3** — o job de treino gravar métrica real, e o backend distinguir NULL de 0.

---

# ⚪ POLIMENTO — não bloqueia fase nenhuma

## 11. Chat flutuante

Existe um botão de chat flutuante vindo do produto atual. Aparece por cima das
telas novas, não está em nenhum desenho — e, medido, ele sozinho põe 3.136px² de
ciano em **todas** as telas novas.

**O que precisamos:** ele fica? Onde, e com que aparência no shell novo?

## 12. Relatórios — o que o backend não serve

O desenho prevê quatro coisas que **não existem na API**: digest diário por
e-mail, seleção de conteúdo do export, ações corretivas vencidas, e taxa de
conformidade medida sobre detecções totais (o que a API devolve é heurística).
Nenhuma foi para a tela.

**O que precisamos:** confirmar se são requisito (viram trabalho de backend) ou se
saem do desenho.

## 13. Perfis: o desenho supõe 4, o produto tem 6

O backend tem `superadmin`, `admin`, `operator`, `analyst`, `trainer`, `viewer`.
A navegação é derivada de **permissão**, não de nome de perfil, e há teste que
confere cada chave contra o registro real.

Verificado em navegador: **`trainer` vê 3 itens** (Dashboard, Ao Vivo, Câmeras) —
não vê Eventos, Verificação, Ações nem Relatórios, porque só tem `cameras:read`.
**`viewer` vê 6**, tudo menos Verificação.

**O que precisamos:** sua leitura do `trainer`. Um perfil que não enxerga evento
nem relatório tem pouco o que fazer no módulo EPI. Pode estar certo (o trabalho
dele é no Estúdio), mas **ninguém tomou essa decisão de propósito** — ela caiu da
matriz de permissões.

## 14. Fila de Propostas — sugestões da IA como caminho principal

**O que aconteceu, medido:** `TrainingGallery.tsx` trata as propostas do modelo
como só mais um chip de status ("Propostas pendentes", sem contador — a faceta
não conta essa dimensão). Medido hoje: `GET /api/training/images?
pending_review=true` devolve **281 imagens / 349 propostas** para o tenant RVB
— o dado existe e é grande, mas a tela não trata isso como o passo "sugestões
do modelo" da demo. Bug medido junto: combinar `source=upload` +
`pending_review=true` zera a grade em silêncio (proposta de IA nasce só de
`nvr`/`auto`, nunca de upload manual) — esse estado-vazio-que-revela-o-filtro
já está sendo corrigido em paralelo, fora deste desenho.

**Como está:** proposta em
`docs/design/handoff-f5/Fila de Propostas.dc.html` — chip de propostas
promovido a banner com contador (não mais um filtro qualquer), CTA "Confirmar
sugestões" em lote com preview de consequência, selo de proposta + % de
confiança por card, contagem separada de caixas humanas × sugestões da IA,
ordenação leiga "onde a IA tem mais dúvida" (o motor já ordena por incerteza —
o cliente nunca vê o número cru), um modo "Revisar em sequência" com barra de
progresso honesta (nunca promete total fechado — a coleta do NVR não para) e o
gesto do Enter explicado a quem chega novo. **É proposta da pista aguardando
refino oficial do design**, mesma régua do item 10.

**Backend pronto:** `GET /api/training/images?pending_review=true` (grade +
total) · `GET /api/training/images?ordenar=incerteza` (o motor já ordena pela
proposta mais perto do ponto de maior dúvida — a galeria hoje não manda esse
parâmetro, é fiação de front) · `POST /api/training/frames/<id>/accept-
suggestions` (confirmar 1 frame) · `POST /api/training/frames/<id>/pre-
annotation-review` (rejeitar 1 frame) · `POST /api/training/frames/curation`
(dúvida/excluída em lote, já batched).

**O que falta no backend:** confirmar/rejeitar **em lote** (N frames de uma
vez) não existe — só por frame, um de cada vez — e é o que bloqueia o CTA
"Confirmar sugestões (N)" da barra de seleção. Confiança agregada por card
também não existe na listagem (só por anotação, uma chamada por frame) — sem
ela o selo "IA XX%" da grade não tem de onde vir. Os 3 pedidos numerados
(P1–P3) estão na aba "Pedidos ao backend" do próprio arquivo, com o de-para
completo na aba "Mapa de conexões".

---

## Perguntas curtas, de responder por mensagem

1. Das 10 telas sem desenho (§4), quais 3 você desenha primeiro?
2. O layout salvo da parede (§3) é por **usuário** ou por **site**? Isso decide se
   precisa de endpoint novo.
3. No white-label do shell escuro (§6): o cliente troca só a cor de marca, ou
   superfície também? Se também, qual o piso de contraste?
4. O chat flutuante (§11) fica?
5. Os quatro itens de Relatórios (§12) são requisito ou saem do desenho?
6. `trainer` (§13): navegação filtrada por permissão como está, ou merece recorte
   próprio?
7. Modelos por câmera (§10): a proposta de ação em massa serve de base, ou você
   prefere desenhar o gesto do zero?

---

# Pedidos-ao-backend abertos pela implementação (29/08)

Registrados aqui porque saíram de **construir a tela**, não de ler o desenho.

| # | o quê | por que trava | fase |
|---|---|---|---|
| B1 | **Pausar/Retomar operação** — com caminho HUMANO e **auditoria de quem/quando/por quê** | `PUT /api/operations/<id>` aceita só `name` e `config`; `status` é escrito **só pelo worker** (`update_live_value`). Não existe caminho humano — a ação central do desenho de Operações não tem rota. | ✅ **ACEITO** — próxima rodada de backend |
| B2 | **Avaliação humana de operação** (OK/NOK + nota + autor) | Não há tabela nem rota. `/operations/<id>/results` é outra coisa: o que a operação MEDIU, não o que a pessoa JULGOU. | ✅ **ACEITO** — entra na fila junto com o ciclo **R5** |
| B3 | **Criação de operação pela tela** | `POST` existe, mas o formulário (módulo, tipo, config, zona) não foi desenhado. | precisa de desenho antes de backend |
| B4 | **Config de parede do kiosk por site** | DECISÃO v2 item 2. Endpoint novo, pequeno, tenant-escopado, 404 cross-tenant. | autorizado na rodada |
| B5 | **Taxa de conformidade sobre detecções totais** | DECISÃO v2 item 5 — substitui a heurística atual. | requisito, fila |
| B6 | **Digest por e-mail + ações vencidas** | DECISÃO v2 item 5 — Fase 1. | setembro |
| B7 | **Seleção de conteúdo do export** | DECISÃO v2 item 5. | fase seguinte |
| B8 | **Pendência por módulo** em `/api/modules/` | A tela `/modules` do desenho mostra "3 NOK aguardam revisão" por módulo; só existe `alerts_today`. Hoje mostro só o que existe. | polimento |
| B9 | **Aviso de clamp no admin** + campo **logo-para-fundo-escuro** | DECISÃO v2 item 3. O clamp já está implementado no front; falta o cliente SABER que a cor dele foi ajustada, e o logo alternativo. | acompanha B4 |

## Pedido-ao-backend do módulo Qualidade — setembro, pista paralela

**O ciclo NC → retrabalho → recaptura → CONFORME não tem rota que o feche.**

`PATCH /gate/reworks/<id>/complete` grava a hora de fim e soma a duração na
peça — só isso. Não re-inspeciona, não aprova, não devolve a peça ao fluxo. O
desenho promete um ciclo que o backend não completa, e por isso a tela mostra o
botão com o rótulo do que a rota **faz** ("Concluir retrabalho"), nunca
"recapturada · conforme".

Falta uma rota que re-inspecione a peça e decida o veredito. Nasce na fase de
desenvolvimento da Qualidade (setembro, pista paralela) — **não agora**.

Junto, o que a mesma tela precisa para ficar como desenhada: JOIN peça↔retrabalho
na própria rota, `COUNT(*)` real para paginação, filtro de data (o repository já
suporta, a rota não passa) e filtro por estação (não existe em camada nenhuma).

## Resolvidos em 29/08

- ~~`quality:*` não existe no registry~~ → **`quality:read` e `quality:write`
  criadas**, no padrão de `counting:*`, com teste de contrato que cruza cada
  `can()` do front contra o catálogo real. "Concluir retrabalho" ganhou o gate.
- ~~`online: True` e `shift_stats` fixos em `gate_repository`~~ → **`online`
  virou `None` honesto** (não há coluna de heartbeat em `quality_stations`) e
  **`shift_stats` passou a ser medido** das inspeções do turno das câmeras da
  bancada.

## Aceites do Vitor em 29/08

**B1 e B2 são pedidos-ao-backend reais e aceitos.** B1 exige caminho humano de
pausa **com auditoria** (quem pausou, quando, por quê) — o operador precisa poder
pausar uma operação, e essa ação precisa deixar rastro. B2 se conecta ao ciclo
R5 e entra na fila com ele.

**Até lá, os controles desabilitados-dizendo-por-quê ficam** — confirmado como o
padrão certo. Não escondê-los é o que mantém a lacuna visível para quem decide.

## Decisão registrada, sem código

**`trainer`** (DECISÃO v2 item 6): navegação por permissão **como está**, decisão
consciente — `trainer` é a persona do Estúdio e o home dele chega na F5. Medido
em navegador: ele vê 3 itens (Dashboard, Ao Vivo, Câmeras), porque só tem
`cameras:read`. Mudar isso é rodada de papéis, não de tela.
