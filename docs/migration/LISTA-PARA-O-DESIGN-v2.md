# Para o design — o que falta desenhar

> **Como usar:** este documento é para ser colado inteiro numa conversa com o
> designer. Ele não pressupõe conhecimento do código. Cada item diz **o que
> aconteceu**, **o que foi feito no lugar** e **o que precisamos que você
> desenhe** — nessa ordem, porque a pergunta sem o contexto gera resposta que
> não cabe no produto.
>
> Gerado ao fim da migração do shell + módulo EPI (27/08/2026). O handoff
> anterior cobriu 21 telas; isto é o que a implementação encontrou **fora** dele.

---

## 0. Como isto foi decidido

Regra que seguimos: **tela sem desenho não se inventa.** Onde faltou desenho,
implementamos o mínimo seguindo o Manual Logikos e os tokens `--lk-*`, e o item
entrou nesta lista. Implementar seguindo a identidade **não** dispensa o
desenho oficial — só evita que a operação fique sem a tela enquanto ele não vem.

E: **zero dado inventado em tela de produto.** Onde o backend não serve o dado
que o desenho previa, a tela **não** o exibe. Ela não finge, e também não fica
explicando ao operador o que falta — isso é assunto desta lista, não da tela.

---

## 1. Telas vivas que o handoff não desenhou (10)

Estas rotas existem, têm gente usando e ficaram fora do handoff. Enquanto não
houver desenho, elas seguem no shell antigo — o que significa que o produto tem
**duas caras** para quem navega entre elas. É o item mais urgente da lista.

| Rota | O que faz hoje |
|---|---|
| `/modules` | Seleção de módulo — a primeira tela depois do login para quem tem mais de um |
| `/epi/cameras/triagem` | Triagem de câmeras |
| `/epi/cameras/:id/operations` | Operações da câmera (o motor de operações está em produção) |
| `/epi/cameras/:id/scenario` | Editor de cenário — desenho de região sobre o vídeo |
| `/epi/health` | Saúde de streams |
| `/epi/sites-health` | Saúde por site |
| `/epi/sites` | Sites do tenant |
| `/epi/edge-observability` | Observabilidade do edge (o Jetson no cliente) |
| `/epi/investigation` | Investigação |
| `/monitoring` | Monitoramento do edge |

**O que precisamos:** priorização sua entre as 10 — quais valem desenho próprio
e quais podem virar variações de telas que você já desenhou.

---

## 2. White-label do shell escuro — o buraco mais concreto

**O que aconteceu.** Ligamos as superfícies do shell novo (fundo, borda, texto)
ao tema do tenant, como o front antigo faz. Ao abrir com o tenant RVB no
ambiente de desenvolvimento, o shell escuro virou **fundo branco com texto azul**
(`#0080ff`) e borda azul (`#136ec9`). Não era erro de implementação: são os
valores de white-label reais daquele cliente, escolhidos para o shell **claro**
antigo.

**O que foi feito.** Só a **cor de marca** (`--color-primary`) vem do tenant. As
superfícies ficaram nos valores do desenho. Estado (verde/âmbar/vermelho) e o
magenta do loader ficaram fora do white-label de propósito — o primeiro é
semântica de segurança, o segundo é assinatura da Logikos.

**O que precisamos que você desenhe:**
1. **Quais tokens o cliente pode trocar** no shell escuro, e quais são intocáveis.
2. **Piso de contraste** para cada token aberto — hoje um cliente pode escolher
   uma cor de marca que some no fundo escuro e nada impede.
3. **O que acontece com um logo claro** sobre fundo escuro (e vice-versa).
4. Se superfície **puder** ser trocada: qual é o conjunto mínimo coerente
   (não adianta abrir o fundo e travar a borda).

---

## 3. Banner de contexto assumido

**O que aconteceu.** O handoff especifica 42px com faixa âmbar de 2px. O banner
que existe hoje é mais antigo, tem lógica cara em volta (TTL de 30 min,
renovação proativa, expiração, "Reassumir") e é montado globalmente — restilizá-lo
agora mudaria também o front antigo, que precisa seguir de pé.

**O que foi feito.** O banner atual foi mantido; o shell novo apenas desce o
espaço que ele ocupa.

**O que precisamos:** o desenho dos **estados** do banner, não só do banner
parado — contexto ativo, contexto expirado com "Reassumir", e o momento da
renovação. Hoje o primeiro é vermelho e o segundo é âmbar, por decisão de
implementação, não de desenho.

---

## 4. Chat flutuante

Existe um botão de chat flutuante no canto inferior direito, vindo do produto
atual. Ele aparece por cima das telas novas e não está em nenhum desenho do
handoff.

**O que precisamos:** ele fica? Se fica, onde e com que aparência no shell novo?
Se sai, sai do produto ou só das telas novas?

---

## 5. Relatórios — o que o backend não serve

O desenho de Relatórios prevê quatro coisas que **não existem na API hoje**:

- digest diário por e-mail (destinatários, horário de envio);
- seleção de conteúdo do export (checkboxes);
- ações corretivas vencidas;
- taxa de conformidade medida sobre detecções totais — o que a API devolve é uma
  heurística, não a mesma coisa.

Nenhuma delas foi para a tela. **O que precisamos:** confirmar se são requisitos
de produto (e então viram trabalho de backend) ou se saem do desenho.

---

## 6. Perfis: o desenho supõe 4, o produto tem 6

O handoff organiza a navegação por quatro perfis. O backend tem **seis**:
`superadmin`, `admin`, `operator`, `analyst`, `trainer`, `viewer`.

**O que foi feito.** A navegação é derivada de **permissão**, não de nome de
perfil — assim `analyst` e `trainer` não caem num vão. Cada item do menu declara
a permissão que exige, e há teste que confere cada uma contra o registro real do
backend.

**O que precisamos:** sua leitura de como `analyst` e `trainer` devem ver o
produto. Hoje eles veem o que suas permissões permitem, o que é correto mas não
foi desenhado.

---

## 7. Texto dos estados vazios

Cada tela precisa dizer alguma coisa quando não há dado, e o handoff não traz
esses textos. Foram escritos na implementação, seguindo o tom do produto:

| Tela | Texto atual |
|---|---|
| Dashboard | "Sem dados para este módulo — nenhuma câmera está atribuída ao EPI ainda. O score aparece após as primeiras detecções." |
| Eventos | "Nenhum evento no período — nenhuma detecção com os filtros atuais. Bom sinal — ou filtro demais." |
| Verificação | "Fila zerada — nenhuma detecção aguarda verificação. As decisões de hoje já alimentam o próximo treino." |
| Ações | "Nenhuma ação aberta — ações nascem de eventos. Nos últimos 30 dias não houve evento de violação para reconhecer nesta operação." |
| Relatórios | "Sem dados no período selecionado — o período selecionado não tem eventos registrados. Amplie o intervalo." |
| Câmeras | "Nenhuma câmera cadastrada" |

**O que precisamos:** sua revisão do tom. Um estado vazio é a tela que o
operador mais vê quando tudo está bem — vale ele estar escrito por quem escreve
o resto do produto. Note que "Nenhum evento" pode significar *nada aconteceu* ou
*o filtro está apertado demais*, e a diferença importa para quem opera.

---

## 8. O que foi verificado, e o que não foi

Honestidade sobre os limites desta rodada. Duas das três lacunas que estavam
aqui foram fechadas depois — ficaram registradas para você saber o que existe de
evidência por trás de cada afirmação.

**Ciano ≤10% — MEDIDO.** Foi medido com navegador de verdade, contra dado real
do RVB, com um guard que reprova a medição se a tela estiver em erro ou
carregando (a primeira tentativa mediu sete telas de erro, porque a API do DEV
só libera CORS para a porta 3000):

| tela | área ciana | maior elemento ciano |
|---|---:|---|
| Dashboard | 0,34% | — |
| Ações | 0,40% | — |
| Eventos | 0,89% | botão "Limpar filtros" |
| Verificação | 1,08% | "Voltar ao dashboard" |
| Ao Vivo | 1,34% | — |
| Câmeras | 1,69% | botão "Adicionar câmera" |
| Relatórios | 2,27% | botão "Exportar" |

A medida conta **área de fundo** ciano sobre a área da tela; borda e texto
cianos não entram, então ela é conservadora por baixo. Todas passam com folga.

Um achado de lambuja: o **chat flutuante** (§4) aparece na conta de TODAS as
telas — são 3.136px² de ciano vindos do produto antigo, em cada tela nova.

**Cada papel na tela — VERIFICADO.** Os seis papéis reais foram abertos num
navegador de verdade, e o menu de cada um foi conferido contra a matriz de
permissões gerada do backend. Confirmações que interessam ao desenho:

- **`trainer` vê 3 itens** (Dashboard, Ao Vivo, Câmeras) — não vê Eventos,
  Verificação, Ações nem Relatórios, porque só tem `cameras:read`.
- **`viewer` vê 6** — tudo menos Verificação.
- `operator` e `analyst` veem os 7, como `admin`.

O caso do `trainer` merece sua atenção: um perfil que não enxerga evento nem
relatório tem pouco o que fazer no módulo EPI. Pode estar certo (o trabalho dele
é no Estúdio), mas é uma decisão de produto que ninguém tomou de propósito — ela
caiu da matriz de permissões.

**Paridade funcional com as telas antigas — em apuração.** As novas foram
provadas renderizando com dado real; a comparação função por função com as
antigas está sendo feita em separado. É pré-requisito da rodada em que o front
antigo sai, não desta.

---

## 9. Perguntas curtas, para responder por mensagem

1. Das 10 telas sem desenho (§1), quais 3 você desenha primeiro?
2. No white-label do shell escuro (§2): o cliente troca só a cor de marca, ou
   superfície também? Se também, qual o piso de contraste?
3. O chat flutuante (§4) fica?
4. Os quatro itens de Relatórios que o backend não serve (§5) são requisito ou
   saem do desenho?
5. `analyst` e `trainer` (§6): mesma navegação dos outros, filtrada por
   permissão — ou merecem um recorte próprio?
