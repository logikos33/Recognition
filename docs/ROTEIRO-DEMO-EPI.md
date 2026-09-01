# Roteiro de demo — EPI (quarta 02/09)

**Objetivo:** Mostrar o módulo EPI (front novo) para a RVB Isolantes — público de segurança do
trabalho, **não técnico**. Um roteiro só, que funciona tanto se a câmera ao vivo pegar um evento
fresco quanto se não pegar. Nada de decidir na hora, na frente do cliente.

**Base:** https://frontend-desenvolvimento-be93.up.railway.app (front novo sob `/novo/` até o
FLIP; pós-flip as mesmas rotas valem sem `/novo/`). Login: `/login` (fora do `/novo/`).

**Login da demo:** `vitor@logikosvision.com.br` — é conta **admin do tenant**, não superadmin.
Isso importa: só assim a tela de confiança mostra a leitura em linguagem de gente (ver Passo 3).
Se por engano a sessão ativa for de superadmin, o card de confiança vai mostrar um número cru
("94%") em vez do texto honesto — **não entrar nessa conta antes da demo**.

---

## O ponto de bifurcação (decidir ANTES de entrar na sala, não durante)

A pista **SEMANA-CLIENTE** está trabalhando para ligar a captura ao vivo no box do cliente. O
critério é objetivo e é checado na véspera/manhã, nunca na frente do cliente:

> Abra `/novo/epi/live`. Alguma câmera mostra uma caixa de detecção sobre um evento capturado
> **nos últimos 15–20 minutos**?

- **SIM até ~18h da véspera → Cenário A.** A demo abre em Ao Vivo, com um evento de verdade na
  tela.
- **NÃO (ou incerto) → Cenário B.** A demo NEM ABRE Ao Vivo — não se arrisca mostrar um feed que
  pode estar parado na frente do cliente. Abre direto no Dashboard, que hoje mostra o painel
  vazio-honesto com o botão de 30 dias.

**Estado medido agora (31/08, será reconferido na véspera):** o último alerta do RVB é de
**25/08 13h41** (`SELECT max(created_at) FROM public.alerts WHERE tenant_id=…` — banco DEV, hoje).
Seis dias sem evento novo. Se a pista SEMANA-CLIENTE não entregar a tempo, **Cenário B é o que vai
acontecer** — o roteiro abaixo foi escrito para isso ser normal, não um imprevisto.

A partir do Passo 2 (Dashboard) os dois cenários **convergem** — é o mesmo roteiro dali em diante.

---

## Passos da demo

### 1. Abertura — [BIFURCA AQUI]

**Cenário A — ao vivo confirmado**
- **URL:** `/novo/epi/live`
- **Mostrar:** o mosaico de câmeras. Apontar a câmera com o evento fresco — a caixa de detecção
  aparece sobre a pessoa, em tempo real.
- **Dizer:** "Isso que vocês estão vendo é agora — a câmera aqui do fundo, ao vivo. Quando alguém
  passa sem um equipamento, o sistema já marca na hora."
- **Se não funcionar** (câmera parou de transmitir entre a checagem e a demo, tela mostra
  CONECTANDO ou OFFLINE): não insistir clicando de novo. Uma frase e seguir: "A câmera caiu agora,
  isso acontece com qualquer link de internet — o que já foi capturado está tudo aqui", e ir
  direto para o Passo 2.

**Cenário B — sem confirmação de ao vivo (o esperado, dado o estado de hoje)**
- Pular Ao Vivo inteiramente. Ir direto para o Passo 2.
- **Dizer** (antes de abrir o Dashboard): "A câmera ao vivo desse site ainda está em instalação —
  o que vou mostrar agora é o histórico real, dos últimos 30 dias de operação."

**Verifiquei:** `curl -o /dev/null -w '%{http_code}' https://frontend-desenvolvimento-be93.up.railway.app/novo/epi/live`
→ `200`. Rota registrada em `RotasNovas.tsx:125`. Comportamento ONLINE/CONECTANDO/OFFLINE e a regra
"só o playback real decide o estado" estão documentados no cabeçalho de `AoVivo.tsx` (linhas 39-45)
— não é a tela que inventa "online", é o próprio carregamento do vídeo.

---

### 2. Dashboard

- **URL:** `/novo/epi/dashboard`
- **Mostrar:** os 4 cartões do topo — **Score de conformidade**, **Eventos hoje**, **Ações
  abertas**, **Câmeras ativas**. Hoje (sem evento novo) o placar mostra **100** e "Câmeras ativas:
  19 · Cadastradas e ativas". Descer para os painéis "Eventos por hora" e "Violações por
  tipo de item": **Cenário B** — os dois vêm vazios, com o botão **"Ver últimos 30
  dias →"**; clicar nele. **Cenário A** — se o evento de hoje já entrou no agregado, aparece 1
  barra; clicar nela também leva para a lista de eventos, só que estreita (1 hora) — depois, no
  Passo 3, alargar para 30 dias do mesmo jeito.
- **Dizer:** "Esse número aqui, 100, é o placar das últimas 24 horas — quanto menos gente sem
  equipamento, mais perto de 100. Não é nota de prova, é hora-câmera sem ocorrência." Para "Ações
  abertas" (mostra "—/Indisponível"), só se perguntarem: "esse aqui a gente decidiu não inventar
  número — o plano de ação por item ainda não existe no sistema, é o próximo passo depois de
  fechar EPI."
- **Se não funcionar** (painel de erro, "Não foi possível carregar"): clicar em "Tentar
  novamente" uma vez; se persistir, pular para o Passo 3 direto pela URL
  `/novo/epi/eventos` e narrar de lá — o dado é o mesmo, só a entrada muda.

**Verifiquei:** código lido em `Dashboard.tsx` (KPIs linhas 777-886; CTA "Ver últimos 30 dias"
linhas 493-499 e 552-558; a fórmula do score no tooltip, linhas 796-799). Rota testada
`curl … /novo/epi/dashboard` → `200`. Banco confirma os números que a tela vai mostrar: 19/29
câmeras ativas, zero alertas nas últimas 24h (nenhum desde 25/08) → score 100.

---

### 3. Eventos (o catálogo, a repetição, a régua "em observação")

- **URL:** `/novo/epi/eventos` — se veio do CTA, o filtro de período já chega em **30 dias**; se
  não, trocar manualmente. A tela abre em **"hoje"** por padrão, que fica **vazia** (não há evento
  novo desde 25/08) — trocar para "30 dias" antes de mostrar qualquer coisa. A tela também abre
  com o filtro de tipo fixo em **"Violações"** (`kind='violation'` é o default do código,
  `Eventos.tsx:190,308` — não é escolha do presenter): ⛔ não prometa ver vermelho, verde e cinza
  já na abertura — é preciso trocar o seletor de tipo manualmente para ver conformidade e "não
  definida".
- **Mostrar:** a lista. Cada linha tem uma etiqueta colorida: **vermelho** = violação de verdade,
  **verde** = equipamento em uso (conformidade), **cinza** = "não definida". Usar o filtro de tipo
  de evento para passar pelas três: "Violações", "Conformidade", e "Não definida (ninguém
  classificou)".
- **Mostrar (julgar uma detecção — com o filtro em "Conformidade"):** cada linha ainda não revisada
  mostra dois botões, **"Procedente"** e **"Falso positivo"** (`Eventos.tsx:663-679`, condicionados
  a `veredito === 'nao-revisado'`). Clicar chama o **mesmo endpoint**
  `POST /api/verification/<id>/review` que a fila de Verificação usaria — mesma verdade gravada,
  aqui é só onde ela aparece clicável hoje (ver Passo 4).
- **Dizer (catálogo com dois níveis de confiança):** "O sistema não trata toda falta de
  equipamento do mesmo jeito. Pra luva e pra máscara, a régua de acerto já é firme, e essas duas
  ACUSAM — entram na lista como violação de verdade. Pro jeito de usar a máscara e pro protetor de
  ouvido, o sistema ainda está no período de aprendizado: ele REGISTRA o que viu, mas não acusa
  ninguém — fica com a etiqueta cinza. É de propósito: a gente prefere mostrar menos avisos de
  verdade do que acusar quem está cumprindo."
- **Óculos — pode citar, a inconsistência foi CORRIGIDA em 01/09 (ADR-0071).** "Sem Óculos" era
  contada como violação por um item do catálogo GLOBAL do sistema, enquanto o selo da linha a
  pintava de cinza — filtro e etiqueta se contradizendo. A polaridade do catálogo global passou a
  `NULL` ("o catálogo não decide, o tenant decide"), e agora as 23 ocorrências saem do filtro
  "Violações" e ficam **em observação**, coerentes com o selo.
  Serve, inclusive, como bom exemplo do parágrafo acima: o sistema mediu 3 acertos em cada 10
  avisos de óculos e **tirou a classe do gatilho sozinho**, em vez de continuar acusando.
- **Dizer (se o cliente estranhar a lista comprida/repetitiva):** "Reparem que a mesma pessoa
  aparece várias vezes seguidas em poucos segundos — é a câmera registrando de novo enquanto a
  situação continua, não é o sistema contando errado. Pela própria regra do produto (mesma câmera e
  mesmo item dentro de 60 segundos = a mesma situação), **estas 66 linhas de violação são 2
  situações**, ambas de uma câmera só, num intervalo de dois minutos. Hoje cada registro ainda vira
  uma linha própria — é o próximo ajuste da lista, já identificado."

  > ⚠️ **Apresentador — o número MUDA com o recorte da tela.** Medido em 01/09 (pós-ADR-0071) com a
  > janela de 60s do produto: **Violações 66 linhas → 2 situações** (é aqui que a tela abre) ·
  > Observação 55 → 28 · Conformidade 302 → 120.
  > ⛔ Nunca usar o número do "Todos os tipos" com a lista de **Violações** na tela: erra por ordem
  > de grandeza e desmonta o próprio argumento — "66 linhas = 2 situações" é a prova da repetição;
  > um número próximo de 66 soaria como se não houvesse repetição nenhuma.
- **Dizer (sobre a coluna de confiança, se perguntarem "o que quer dizer esse número/aquela
  frase"):** hoje, com este login, a coluna mostra **"precisão ainda não medida"** — não mostrar
  isso como se fosse a resposta final. A resposta é falada, com o número que já medimos por fora:
  "pra luva, de cada 10 avisos, quase 7 são reais; pra máscara, 6 em cada 10." **Não apontar para a
  tela dizendo "aqui está a precisão"** — a tela ainda não expõe esse número calculado, o
  presenter é quem sabe a conta.
- **Se não funcionar** (lista vazia mesmo em 30 dias — não deveria acontecer, mas): abrir
  diretamente um evento por ID conhecido, `/novo/epi/eventos/<id>`, usando qualquer ID copiado
  do banco antes da demo.

**Verifiquei (reconferido 01/09 — os números do Passo 3 estavam errados numa rodada anterior,
corrigidos aqui):** código lido em `Eventos.tsx` (três eixos e paletas, linhas 8-19; filtro "Não
definida", linhas 473-483; botões de julgar, linhas 663-679; `kind` default, linhas 190 e 308).
A polaridade real que a tela usa NÃO é `yolo_classes.is_violation` puro — é
`AlertRepository._nomes_por_polaridade` (linhas 125-146), que UNE o catálogo GLOBAL
(`module_classes`, casado por `class_name` OU `display_name`) com as classes do tenant, SEM
subtração. `module_classes` tinha `no_glasses` (`display_name='Sem Óculos'`) com
`is_violation=TRUE` globalmente — então, mesmo com o tenant marcando `NULL`, ela continuava
contando como violação pela união, e o filtro contradizia o selo da linha.
**Corrigido em 01/09 (ADR-0071)**: a polaridade global de `no_glasses` passou a `NULL` — "o
catálogo não decide, o tenant decide". Reproduzi a classificação real (mesmo predicado
`_IS_COMPLIANCE_SQL`/`_IS_VIOLATION_SQL` do código, união global+tenant) sobre os 423 alertas:
**violação 66** (Sem Luvas 33 + Sem mascara 33) · **observação 55** (Sem Óculos 23 + Sem protetor
de ouvido 22 + Uso incorreto de mascara 10) · **conformidade 302** — bate 66+55+302=423.
Precisão das violações: **66,7%**. Houve um momento intermediário em que a medição deu 89/32: era o
estado com o TRUE global ainda em pé, antes da ADR-0071. "Sem botas" está no catálogo do tenant como violação
(`is_violation=TRUE`) mas **arquivada** (`archived_at` 22/08) e **zero alertas reais** têm essa
classe — não citar como exemplo ativo. A frase "precisão ainda não medida" vem de
`confidenceDisplay.ts` (linha 42) — nenhuma tela hoje passa o parâmetro de precisão medida por
classe (grep confirma zero call sites), então é isso que vai aparecer, não um percentual.
`curl … /api/v1/events/timeline` sem token → `401` (rota existe, exige login).

---

### 4. Corrigir uma caixa (no detalhe do evento — a Verificação dedicada é parada opcional, ver
   abaixo)

- **URL:** `/novo/epi/eventos/<id>` — clicar em qualquer linha da lista do Passo 3 abre o detalhe.
- **Mostrar:** a lupa (roda do mouse ou pinça = zoom, arrastar = mover a imagem) e o botão
  "Corrigir caixa" (`EventoDetalhe.tsx:765`) — arrastar a caixa se ela pegou a pessoa errada. Se
  ainda não tiver julgado nenhum item no Passo 3, o mesmo par de botões **"Procedente"/"Falso
  positivo"** existe aqui também; **rejeitar** pede um motivo antes de salvar (dropdown: "O EPI
  está presente" / "Não dá para ver a pessoa" / "O sistema confundiu com outra coisa" / "Outro
  motivo").
- **Dizer:** "Aqui a pessoa da segurança bate o olho na imagem que gerou o evento. Pode dar zoom,
  pode arrastar a caixinha se ela pegou meio torto. E se ela disser que o sistema errou, a gente
  pede o motivo — isso é o que alimenta o sistema aprender a não errar de novo."
- **Se não funcionar:** voltar para a lista de Eventos e abrir outra linha — o mecanismo é o mesmo
  em qualquer evento com caixa desenhável.

**Verifiquei:** código lido em `EventoDetalhe.tsx` (correção de caixa, linhas 197-530; botão
"Corrigir caixa", linha 765). `curl -X POST … /api/verification/<id>/review` sem token → `401`
(rota existe).

---

### 4b. Verificação dedicada (opcional, ~10 segundos — hoje mostra fila zerada, e está certo)

- **URL:** `/novo/epi/verificacao`.
- **Mostrar (só se sobrar tempo ou o cliente perguntar "onde vocês revisam"):** a tela abre em
  **"Fila zerada"** — e isso é o estado certo hoje, não um imprevisto para contornar. **⛔ Nunca
  prometer que vai aparecer um item.**
- **Dizer (o porquê, medido no banco agora):** "essa fila junta só o que ainda está em dúvida — ela
  deixa de fora, de propósito, o que o sistema já considera equipamento em uso. O Vitor acabou de
  revisar os 121 alertas que estavam em dúvida nesta calibração; o que sobra no banco (302
  registros) é tudo conformidade, então a fila fica vazia. É a régua funcionando, não travando."
- **Se o cliente quiser ver o mecanismo de julgar de qualquer forma:** voltar para Eventos (Passo
  3), filtrar por "Conformidade" — lá tem itens ainda não revisados de verdade, com os mesmos
  botões.

**Verifiquei (reconferido 01/09 — meça de novo antes de apresentar, o Vitor pode ter julgado mais
itens entre agora e a demo):** código lido em `verification_service.py`
(`_candidatos_sql`, linhas 102-138: `verification_verdict IS NULL AND NOT
_IS_COMPLIANCE_SQL`). Reproduzi o predicado exato no banco DEV para o tenant RVB: fila
(`verdict IS NULL AND NOT compliance`) = **0 itens**. `verdict IS NULL` sozinho = **302 linhas**,
e as 302 são **100% conformidade** — bate com a fila vazia. `curl -X POST …
/api/verification/<id>/review` sem token → `401` (rota existe). Fallback confirmado:
`EventoDetalhe.tsx` (Passo 4) usa o mesmo mecanismo de lupa/correção de caixa —
`Verificacao.tsx:91` afirma no próprio comentário que `PATCH /alerts/<id>/violations` "é o MESMO
endpoint de `EventoDetalhe.tsx`".

---

### 5. Ações (o que já foi feito com cada evento)

- **URL:** `/novo/epi/acoes`
- **Mostrar:** o cartão de um evento com dois botões: **Reconhecer** (verde/âmbar — "alguém viu")
  e o **veredito** (cinza — "a detecção procede ou não"). Clicar no cartão (fora dos botões) abre
  o detalhe completo do evento.
- **Dizer:** "Duas coisas diferentes ficam registradas aqui: se alguém já olhou o alerta, e se a
  detecção estava certa. São perguntas distintas — dá pra ter olhado o alerta e discordar do que o
  sistema viu, ou o contrário."
- **Se não funcionar** (miniatura sem imagem — evidência sem URL assinada ainda carregada):
  esperar entrar na tela (a miniatura só busca a imagem quando aparece na tela) ou clicar direto
  no cartão para abrir o detalhe, que sempre traz a imagem.

**Verifiquei:** código lido em `Acoes.tsx` (RECONHECIMENTO × VEREDITO como dois eixos com botão e
cor próprios, linhas 13-22). `curl -o /dev/null -w '%{http_code}' … /novo/epi/acoes` → `200`.
`curl -X POST … /api/alerts/<id>/acknowledge` sem token → `401` (rota existe).

---

## NÃO PROMETER (setembro)

- Contar como "1 situação" as linhas repetidas da mesma câmera+item dentro da janela de 60s de
  rajada (medido em 01/09: 423 alertas → 150 situações no total (pré-ADR-0071 o recorte de violação era outro); e, no recorte que a tela abre,
  66 violações → 2 situações — ver Passo 3) — hoje cada repetição é uma linha própria (achado já
  registrado, não entrou nesta rodada).
- Mostrar o percentual de acerto medido por item diretamente na tela — hoje a coluna diz
  "precisão ainda não medida" para qualquer login que não seja superadmin; o número é falado pelo
  apresentador, não lido da tela.
- Fila de "Classificar" do Estúdio de anotação — é ferramenta interna de treino do modelo, não
  faz parte deste roteiro para o cliente.
- Plano de ação por item (título/responsável/prazo) na tela de Ações — não existe endpoint; o
  cartão mostra o controle desabilitado, com aviso.
- "Câmeras online" — o sistema não tem heartbeat por câmera ainda; o que existe é "cadastrada e
  ativa", que é o que a tela mostra.

---

**Congela terça 01/09 às 18h (checagem do ponto de bifurcação) · branch `ux2/b4` · dúvidas:**
este arquivo mesmo — os números têm timestamp de consulta, reconferir no banco DEV se o embarque
atrasar mais de um dia.
