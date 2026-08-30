# Paridade: o que o front novo ainda não faz

> **Pergunta que este documento responde:** se apagarmos as telas antigas hoje,
> o que o usuário perde?
>
> **Resposta curta: não dá para apagar.** 22 funções de operação diária só
> existem nas telas velhas.
>
> Enquanto os dois fronts convivem — o novo sob `/novo`, o antigo em tudo o
> mais — **nada está quebrado para o usuário**. Esta conta só é cobrada no dia
> do tombamento.

## Como estes números foram obtidos

Sete agentes independentes compararam, função por função, cada tela antiga com
sua substituta: cada endpoint, filtro, ordenação, ação, estado tratado,
permissão consultada e dado exibido. Depois, **um cético independente por
achado** recebeu a alegação com a instrução de REFUTÁ-LA — procurar a função no
front novo pelo mesmo nome, pelo nome em português, dentro de componentes
importados, ou resolvida de outro jeito.

| | |
|---|---:|
| perdas alegadas | 42 |
| **confirmadas** após refutação | **22** |
| refutadas (a função existe, achada pelo cético) | 20 |

Quase metade das alegações caiu. É por isso que a etapa de refutação existe:
sem ela, este documento mandaria alguém caçar 20 funções que já estão lá.

---

**Não dá para apagar o front antigo hoje: quatro funções de operação diária (ajuste de câmera, correção da caixa, montagem da parede e a fila de verificação) só existem nas telas velhas, e apagá-las tira do cliente coisas que ele usa — não é polimento, é função que some.**

Hoje nada está quebrado para o usuário: as duas versões convivem (a nova mora sob `/novo`). A conta abaixo só é cobrada no dia do tombamento. Total estimado para zerar tudo: cerca de 900 a 1.000 linhas.

---

## 1. Ajustar a câmera: FPS, qualidade do vídeo e resolução da coleta de treino — e ver a saúde do equipamento

**O que se perde:** ninguém mais consegue dizer "esta câmera roda a 5 quadros por segundo em qualidade média e coleta frames de treino no stream principal" — e ninguém mais vê GPU, memória, fila, latência e temperatura da câmera, nem a simulação "se você mudar isso, vai para ~N fps".
**Importa:** **bloqueia.** É o único lugar do produto que grava a resolução dos frames que entram no dataset de treino, e o único freio contra sobrecarregar o mini PC do cliente. Sem isso, ajustar uma câmera vira chamado para o suporte mexer no banco.
**Conserto:** ~60 linhas, se a tela nova apenas reaproveitar o painel que já existe e funciona (450 linhas prontas) numa aba. Refazer no visual novo custaria ~450.

*(Aparecia em dois lugares: aba "Desempenho" da tela de monitoramento e na tela de Câmeras. É a mesma peça.)*

## 2. Corrigir a caixa da detecção no frame

**O que se perde:** quando a IA marca a caixa no lugar errado, o operador não tem mais como redesenhá-la — nem arrastando sobre a imagem, nem digitando as coordenadas —, e some também a linha "caixa corrigida por Fulano em tal dia".
**Importa:** **bloqueia.** É o gesto que transforma erro da IA em dado bom, e o caminho digitado é o acessível para quem não usa mouse com precisão. O backend continua pronto e esperando; só não tem mais quem chame.
**Conserto:** ~200 linhas (portar o desenho por arrasto, os quatro campos numéricos e a linha de autoria).

## 3. A fila de verificação mente sobre o que ainda falta julgar

**O que se perde:** um alerta que saiu da fila por fora (outro operador já revisou, ou o alerta foi resolvido em outra tela) nunca some da tela — continua contando em "N restantes" e é apresentado para julgar. Pior: o veredito é aceito e **sobrescreve em silêncio** o que o outro operador já tinha decidido.
**Importa:** **bloqueia.** Não é incômodo visual, é dado de auditoria sendo trocado sem ninguém saber. Com dois revisores trabalhando ao mesmo tempo, acontece no primeiro dia.
**Conserto:** ~20 linhas na tela (recarregar substituindo a fila em vez de só acumular, preservando o que o próprio operador já julgou) + ~5 linhas no servidor, se quisermos recusar veredito sobre item que já saiu da fila.

## 4. Montar a parede de câmeras do jeito do operador

**O que se perde:** escolher qual câmera fica em qual quadrinho ("Portaria sempre no canto superior esquerdo"), arrastar para trocar de posição, remover uma da grade — e salvar tudo isso com nome ("Portaria + Estoque") para recarregar depois. A tela nova mostra as câmeras na ordem em que o servidor devolveu, e nem o layout escolhido é lembrado ao recarregar a página.
**Importa:** **bloqueia** para uso de painel de parede com 28 câmeras. O operador decora posição, não nome; sem posição fixa ele varre a tela toda a cada alerta.
**Conserto:** ~250 a 300 linhas. É o item mais caro porque a tela nova não tem o conceito de "quadrinho com dono" — precisa voltar antes dele; o mecanismo de salvar presets já existe pronto e vem quase de graça depois.

## 5. Ranking "câmeras com mais alertas" no painel

**O que se perde:** a lista das 10 câmeras que mais dispararam no período. A tela de Relatórios mostra só a campeã, sem a 2ª à 10ª.
**Importa:** **incomoda muito.** É por esse ranking que o gestor decide onde treinar equipe e onde a câmera está mal posicionada.
**Conserto:** ~40 linhas. O gráfico já existe pronto (87 linhas) e os dados já chegam na tela nova — só não são usados.

## 6. Painel "taxa de uso por área" (EPI em uso × violações × % por área)

**O que se perde:** a tabela que responde "na Doca Norte, 82% das passagens estão com EPI". O que restou são percentuais globais da planta inteira.
**Importa:** **incomoda muito** — e vira bloqueio se esse número for o que o cliente apresenta na reunião de segurança. Agravante: o filtro "Conformidade" continua na tela nova, mas sem o painel que o tornava útil.
**Conserto:** ~80 linhas. O cálculo já está pronto no servidor; falta só a tabela na tela.

## 7. Modelo de IA por câmera: voltar ao detector padrão e ver o que está rodando

**O que se perde:** duas coisas do mesmo painel que não foi portado — (a) tirar o modelo específico de uma câmera e devolvê-la ao detector padrão; (b) ver qual arquitetura de detector está atribuída e a precisão (mAP) de cada modelo na hora de escolher.
**Importa:** **incomoda.** Reverter uma atribuição ruim passa a exigir suporte, e escolher modelo pelo nome, sem ver a precisão, é escolher no escuro.
**Conserto:** ~120 linhas para o painel inteiro; ~10 linhas se for só mostrar a arquitetura no seletor (o dado já chega na tela).

## 8. Tela cheia da parede de câmeras

**O que se perde:** o modo painel de parede — a grade ocupando o monitor inteiro, sem menu e sem barra do navegador.
**Importa:** **incomoda.** É o uso previsto do monitor na sala de operação; o desenho novo até prevê um "Modo TV", que não foi construído.
**Conserto:** ~15 linhas (é um botão e uma chamada nativa do navegador).

## 9. Coluna "Confiança" na lista de eventos

**O que se perde:** ver, na lista de 20 eventos, quais a IA marcou com 51% e quais com 98%, para atacar os duvidosos primeiro. Hoje só abrindo um por um.
**Importa:** **incomoda.** Existe saída pelo Excel — a exportação CSV ainda traz a coluna —, mas triar fora da tela é retrabalho.
**Conserto:** ~5 linhas. O dado já vem; só não é desenhado.

## 10. "Logs ao vivo" da câmera (as últimas detecções com hora, classe e confiança)

**O que se perde:** a lista rolante que provava, na hora da instalação, que a IA está enxergando — inclusive as detecções corretas, que não viram alerta. A tela nova mostra no máximo 5 alertas já gravados, só violações, sem confiança.
**Importa:** **incomoda.** É a ferramenta de conferência de instalação e de ajuste fino; sem ela, "a câmera está detectando?" vira suposição.
**Conserto:** ~60 linhas (hoje cada detecção nova apaga a anterior; precisa guardar as últimas 50).

## 11. Aviso de que a conexão ao vivo caiu

**O que se perde:** o selo "Ao vivo / Desconectado". Se a ligação de detecções cair, a tela nova continua mostrando tudo ONLINE e simplesmente para de desenhar caixas — sem avisar.
**Importa:** **incomoda**, com risco: o operador acha que não há violação quando, na verdade, não há informação chegando.
**Conserto:** ~10 linhas.

## 12. Buscar câmera pelo nome na parede e esconder os rótulos

**O que se perde:** achar "Doca 3" digitando, em vez de varrer 28 quadrinhos com o olho; e desligar os nomes sobre a imagem para a parede ficar limpa.
**Importa:** **incomoda.** A busca é a mais sentida: a caixa de busca geral do sistema até se anuncia como "buscar câmeras", mas hoje só encontra telas — digitar o nome de uma câmera devolve "nada encontrado".
**Conserto:** ~20 linhas para ligar as câmeras à busca geral; ~15 linhas para o botão de esconder rótulos.

## 13. Local e módulo no próprio quadrinho da parede

**O que se perde:** saber onde a câmera fica sem clicar nela. Hoje aparece só o nome.
**Importa:** **dá para viver**, se os nomes das câmeras já disserem o local (é o caso da RVB hoje). Volta a doer em cliente com mais de um módulo na mesma parede.
**Conserto:** ~10 linhas. Os dados já estão na tela, só não são mostrados.

## 14. "Assumir contexto" a partir da parede (só administrador Logikos)

**O que se perde:** quando um superadministrador abre a tela sem cliente selecionado, ele via um botão para entrar no contexto certo com um clique. Agora cai numa tela vazia dizendo "sem dados".
**Importa:** **dá para viver** — atinge a nossa equipe, não o cliente, e há o caminho normal de trocar de cliente pelo menu.
**Conserto:** ~5 linhas (o componente existe pronto, é montá-lo na tela nova).

## 15. Fabricante da câmera no painel de detalhe

**O que se perde:** ver a marca da câmera sem abrir a tela de edição — que só administrador pode abrir. Operador, analista e visualizador deixam de ter acesso ao dado.
**Importa:** **dá para viver.** Foi decisão do desenho novo, não descuido.
**Conserto:** ~3 linhas.

---

### Como eu leria isso

- **Antes de apagar as telas antigas, obrigatório:** itens 1 a 4 (~530 linhas). São função de operação, não conforto.
- **Barato demais para deixar passar** (juntos, ~90 linhas para 6 itens): 5, 9, 11, 13, 14, 15.
- **Itens 6, 7, 10 e 12** valem uma decisão sua: são funções reais, mas dá para tombar sem elas e repor na semana seguinte, desde que alguém avise o cliente.
- **Item 4 é o único que exige desenho antes de código** — os demais são reposição do que já existe.

---

## Detalhe por tela — todas as perdas confirmadas

### EPI Relatórios — src/pages/ReportsPage.tsx (antigo, rota /epi/reports) vs src/app/epi/Relatorios.tsx (novo)
_Nenhuma perda sobreviveu à refutação._
### EPI — Detalhe do Alerta (`pages/epi/AlertDetailPage.tsx`, rota `/epi/alerts/:alertId`) → substituta `app/epi/EventoDetalhe.tsx`, rota `/epi/eventos/:id`
_Nenhuma perda sobreviveu à refutação._
### Fila de Verificação EPI — antigo `src/pages/VerificationQueuePage.tsx` (rota `/verification`) → novo `src/app/epi/Verificacao.tsx` (rota `/novo/epi/verificacao`)
_Nenhuma perda sobreviveu à refutação._
### EPI Ao Vivo — antigo `apps/frontend/src/pages/MonitoringPage.tsx` → novo `apps/frontend/src/app/epi/AoVivo.tsx` (`/novo/epi/live`)
_Nenhuma perda sobreviveu à refutação._
### EPI Dashboard — antiga: apps/frontend/src/pages/epi/EpiDashboard.tsx · nova: apps/frontend/src/app/epi/Dashboard.tsx (/novo/epi/dashboard)
_Nenhuma perda sobreviveu à refutação._
### EPI · Câmeras — antigo /Users/vitoremanuel/Logikos-mutirao/wt-consertos/apps/frontend/src/pages/epi/EpiCameras.tsx (wrapper de 23 linhas) cuja implementação real é /Users/vitoremanuel/Logikos-mutirao/wt-consertos/apps/frontend/src/pages/CamerasPage.tsx → novo /Users/vitoremanuel/Logikos-mutirao/wt-consertos/apps/frontend/src/app/epi/Cameras.tsx
_Nenhuma perda sobreviveu à refutação._
### EPI — Alertas/Eventos (antiga: src/pages/epi/EpiAlerts.tsx → wrapper de src/pages/AlertsHistoryPage.tsx · nova: src/app/epi/Eventos.tsx)
_Nenhuma perda sobreviveu à refutação._

---

## Atualização 30/08/2026 — sessão F5-LEVE (carimbo das 6 telas)

Resolvido e mergeado na develop:

| item | onde | PR |
|---|---|---|
| §1 ajustar câmera + saúde | 5ª aba "Desempenho" em `app/epi/Cameras.tsx` | #576 |
| §2 corrigir a caixa | `app/epi/EventoDetalhe.tsx` (arrasto + 4 campos px + autoria) | #578 |
| §3 fila honesta | `app/epi/Verificacao.tsx` (substitui, preserva o que EU julguei) | #579 |
| §4 parede do operador | `app/epi/AoVivo.tsx` (por site, montar, layouts nomeados máx 10) | #575 |
| §5 ranking | widget no `app/epi/Dashboard.tsx` | #573 |
| §9 confiança · §15 fabricante | Eventos / Câmeras | #581 |
| §11 sem-sinal · §13 local/módulo | AoVivo | #582 |
| §14 assumir contexto | JÁ COBERTO — SeletorTenant global no Shell (Shell.tsx:143) | — |

**Adiados por decisão de 30/08** (regra deste doc: "dá para tombar sem elas e
repor na semana seguinte, desde que alguém avise o cliente"): **§6** taxa de uso
por área · **§7** modelo por câmera (reverter/precisão) · **§10** logs ao vivo ·
**§12** busca na parede + esconder rótulos. Dono: pista F5-LEVE; prazo: semana
de 07/09; aviso ao cliente: RELATORIO-SEGUNDA + onboarding de 02/09.

Nota de consistência: as linhas "_Nenhuma perda sobreviveu à refutação_" no
"Detalhe por tela" contradiziam a lista numerada (Eventos e Ao Vivo tinham
perdas confirmadas na síntese). **A lista numerada é a autoridade** — os
carimbos das 6 telas citam este bloco.
