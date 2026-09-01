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
  não, trocar manualmente o seletor de período para "30 dias".
- **Mostrar:** a lista. Cada linha tem uma etiqueta colorida: **vermelho** = violação de verdade,
  **verde** = equipamento em uso (conformidade), **cinza** = "não definida". Usar o filtro de tipo
  de evento para mostrar as três: "Violações", "Conformidade", e "Não definida (ninguém
  classificou)".
- **Dizer (catálogo com dois níveis de confiança):** "O sistema não trata toda falta de
  equipamento do mesmo jeito. Pra luva e pra máscara, a régua de acerto já é firme, e essas duas
  ACUSAM — entram na lista como violação de verdade. Pra óculos, protetor de ouvido e o jeito de
  usar a máscara, o sistema ainda está no período de aprendizado: ele REGISTRA o que viu, mas não
  acusa ninguém — fica com a etiqueta cinza. É de propósito: a gente prefere mostrar menos avisos
  de verdade do que acusar quem está cumprindo."
- **Dizer (se o cliente estranhar a lista comprida/repetitiva):** "Reparem que às vezes a mesma
  pessoa aparece várias vezes seguidas em poucos segundos — é a câmera registrando de novo
  enquanto a situação continua, não é o sistema contando errado. São por volta de 180 situações
  reais ali dentro, só que hoje cada segundo de uma mesma situação ainda vira uma linha própria — é
  o próximo ajuste da lista, já identificado."
- **Dizer (sobre a coluna de confiança, se perguntarem "o que quer dizer esse número/aquela
  frase"):** hoje, com este login, a coluna mostra **"precisão ainda não medida"** — não mostrar
  isso como se fosse a resposta final. A resposta é falada, com o número que já medimos por fora:
  "pra luva, de cada 10 avisos, quase 7 são reais; pra máscara, 6 em cada 10." **Não apontar para a
  tela dizendo "aqui está a precisão"** — a tela ainda não expõe esse número calculado, o
  presenter é quem sabe a conta.
- **Se não funcionar** (lista vazia mesmo em 30 dias — não deveria acontecer, mas): abrir
  diretamente um evento por ID conhecido, `/novo/epi/eventos/<id>`, usando qualquer ID copiado
  do banco antes da demo.

**Verifiquei:** código lido em `Eventos.tsx` (três eixos e paletas, linhas 8-19; filtro "Não
definida", linhas 473-483). Banco DEV confirma a régua atual do catálogo do RVB — `is_violation`
em `public.yolo_classes`: **true** (acusa) em Sem Luvas / Sem mascara / Sem botas; **NULL** (em
observação) em Sem Óculos / Sem protetor de ouvido / Uso incorreto de mascara; **false**
(conformidade) em Protetor auditivo / Óculos / Botas / mascara — bate exatamente com os números do
Vitor (66 violação + 55 observação + 302 conformidade = 423). A frase "precisão ainda não medida"
vem de `confidenceDisplay.ts` (linha 42) — nenhuma tela hoje passa o parâmetro de precisão medida
por classe (grep confirma zero call sites), então é isso que vai aparecer, não um percentual.
`curl … /api/v1/events/timeline` sem token → `401` (rota existe, exige login).

---

### 4. Verificação (revisar uma detecção)

- **URL:** `/novo/epi/verificacao`
- **Mostrar:** a fila. Abrir o primeiro item. Mostrar a lupa (roda do mouse ou pinça = zoom,
  arrastar = mover a imagem) e o botão "Corrigir caixa" (arrastar a caixa se ela pegou a pessoa
  errada). Confirmar ou rejeitar o item: se **rejeitar**, a tela pede um motivo antes de deixar
  salvar (dropdown: "O EPI está presente" / "Não dá para ver a pessoa" / "O sistema confundiu com
  outra coisa" / "Outro motivo").
- **Dizer:** "Aqui a pessoa da segurança bate o olho na imagem que gerou o evento. Pode dar zoom,
  pode arrastar a caixinha se ela pegou meio torto. E se ela disser que o sistema errou, a gente
  pede o motivo — isso é o que alimenta o sistema aprender a não errar de novo."
- **Nota (verificado no banco, honesta se perguntarem "quais faltam revisar"):** hoje a fila que
  está pendente (302 itens) é toda de imagens de **conformidade** — equipamento em uso — porque as
  violações já foram todas revisadas nesta calibração. Não afeta a demonstração (o mecanismo de
  zoom/caixa/motivo é idêntico para qualquer tipo de imagem), mas não prometer "vamos revisar uma
  violação de sem-luvas" — o item que vai aparecer é de alguém usando o equipamento certo.
- **Se não funcionar** (fila mostra "Fila zerada" — improvável, mas o dado muda todo dia): usar o
  mesmo recurso dentro de um evento específico, em `/novo/epi/eventos/<id>` — é a mesma lupa e a
  mesma correção de caixa, só que dentro do detalhe do evento em vez da fila.

**Verifiquei:** código lido em `Verificacao.tsx` (lupa+correção de caixa, linhas 82-134; motivo
obrigatório ao rejeitar, linhas 543-547 e 1182-1206). Banco DEV: `verification_verdict IS NULL`
para o tenant RVB = **302 linhas**, todas com `is_violation = false` (conformidade) — as 121
alertas de violação/observação já têm veredito humano registrado. `curl -X POST …
/api/verification/<id>/review` sem token → `401` (rota existe). Fallback (`EventoDetalhe.tsx`)
testado da mesma forma: rota `/novo/epi/eventos/<id>` → `200`, mesma lupa reaproveitada (comentário
linha 94 do próprio arquivo confirma a origem compartilhada).

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

- Contar como "1 situação" as ~238 linhas repetidas da mesma câmera+item em poucos segundos —
  hoje cada repetição é uma linha própria (achado já registrado, não entrou nesta rodada).
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
