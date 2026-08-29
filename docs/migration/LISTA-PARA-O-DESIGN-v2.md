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

---

# ⚪ POLIMENTO — não bloqueia fase nenhuma

## 10. Chat flutuante

Existe um botão de chat flutuante vindo do produto atual. Aparece por cima das
telas novas, não está em nenhum desenho — e, medido, ele sozinho põe 3.136px² de
ciano em **todas** as telas novas.

**O que precisamos:** ele fica? Onde, e com que aparência no shell novo?

## 11. Relatórios — o que o backend não serve

O desenho prevê quatro coisas que **não existem na API**: digest diário por
e-mail, seleção de conteúdo do export, ações corretivas vencidas, e taxa de
conformidade medida sobre detecções totais (o que a API devolve é heurística).
Nenhuma foi para a tela.

**O que precisamos:** confirmar se são requisito (viram trabalho de backend) ou se
saem do desenho.

## 12. Perfis: o desenho supõe 4, o produto tem 6

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

---

## Perguntas curtas, de responder por mensagem

1. Das 10 telas sem desenho (§4), quais 3 você desenha primeiro?
2. O layout salvo da parede (§3) é por **usuário** ou por **site**? Isso decide se
   precisa de endpoint novo.
3. No white-label do shell escuro (§6): o cliente troca só a cor de marca, ou
   superfície também? Se também, qual o piso de contraste?
4. O chat flutuante (§10) fica?
5. Os quatro itens de Relatórios (§11) são requisito ou saem do desenho?
6. `trainer` (§12): navegação filtrada por permissão como está, ou merece recorte
   próprio?

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
