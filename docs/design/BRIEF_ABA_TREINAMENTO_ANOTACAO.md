# Brief de design — Estúdio de Treinamento de Modelos (Recognition)

> Cole este brief no Claude Design. Descreve **o que o ambiente precisa fazer e por quê**.

---

# 🔴 LEIA ISTO PRIMEIRO — a aba "Dados" É a tela de anotação

**O design atual tratou "Dados" como um navegador de arquivos. Não é.**

**Clicar num frame na aba Dados abre aquele frame no anotador**, em tela cheia, para desenhar as caixas.
A galeria não é um catálogo para consultar — **é a porta de entrada do trabalho**. Todo o resto do
produto depende de alguém conseguir clicar numa imagem e marcar onde está o capacete.

Se essa ligação não estiver óbvia no design, o ambiente inteiro não serve para nada.

---

## O que é este ambiente

**Recognition** é um SaaS de visão computacional sobre CFTV. A proposta central: **cada cliente treina
o próprio modelo** — não existe detector universal.

O Estúdio é onde esse modelo nasce. **Um ciclo, não uma lista de telas:**

```
   DADOS ──clique──▶ ANOTAÇÃO ──▶ DATASET ──▶ TREINO ──▶ MODELO
     ▲                                                      │
     └──────── o modelo aponta o que anotar em seguida ◀─────┘
```

Cliente âncora: **RVB Isolantes** — 8 câmeras, módulo EPI (capacete, óculos, luva, colete).

**Quem usa:** o fundador agora; depois, o técnico de segurança do cliente. **Não é cientista de dados.**
⛔ Zero jargão de ML na interface.

## 🔴 A restrição que manda em todo o design

**500 imagens numa sequência de sessões.**

Cada clique a mais é multiplicado por 500. Cada meio segundo de hesitação vira quatro minutos.

**O alvo real: menos de 10 segundos por imagem.** Uma tela que exige três cliques e um menu suspenso
por imagem transforma um dia de trabalho em três.

**Otimize para a milésima repetição, não para a primeira visita.**

---

# Tela 1 · DADOS — a galeria

## Filtros (barra fixa no topo)

| Filtro | Por quê |
|---|---|
| 🔴 **Câmera** | anotar a CAM-03 em sequência é muito mais rápido — o olho se acostuma com o enquadramento, a luz e o que é EPI naquele posto |
| **Status** | não anotado · anotado · proposta pendente · em dúvida · excluído |
| **Classe** | já tem capacete · já tem colete · sem nenhuma |
| **Data / sessão de coleta** | separa a encenação combinada da captura de operação real — isso tem implicação jurídica, não é só organização |
| **Tipo** | imagem · vídeo |

Combinam entre si. Sempre com **contagem visível**: `134 frames · CAM-03 · não anotados`.

⚠️ Hoje as câmeras são `CAM-01`…`CAM-08`. **Preveja renomear pela própria tela** — o filtro só serve
com nome de lugar ("Portaria", "Embarque"), não com número de canal.

## Seleção múltipla

- **Clique** seleciona · **Shift+clique** intervalo · **Ctrl/Cmd+clique** avulso
- **Selecionar todos os visíveis** (respeitando o filtro) e **limpar**
- **Barra de ação fixa** com `12 selecionados` + ações em lote. ⛔ Não pode empurrar o conteúdo

## Ações em lote

- **Anotar em sequência** — 🔴 a mais importante: abre o anotador percorrendo a seleção inteira,
  **sem voltar à galeria entre uma imagem e outra**
- **Excluir da coleta** (ver abaixo)
- **Marcar "em dúvida"** — tira da fila sem descartar
- **Rodar anotação automática** (Tela 4)

## ⚠️ Excluir — reversível por padrão

- É **excluir da coleta**: sai da fila e do dataset, **continua recuperável**
- **"Desfazer" depois da ação** por alguns segundos — ⛔ não um diálogo antes
- Filtro **"excluídos"** para revisar e restaurar

*O acervo é pequeno e insubstituível. Frame apagado por engano num lote de 30 não volta — refazer
significa remarcar pessoas dentro da fábrica.*

## O que cada card mostra

- Miniatura **grande o bastante para julgar** se dá para anotar
- 🔴 **Selo de procedência** — o dado mais importante da tela:

| Selo | Significado | Entra no treino? |
|---|---|---|
| **Humana** | uma pessoa desenhou | ✅ |
| **Aprovada** | máquina sugeriu, pessoa confirmou | ✅ |
| **Proposta** | máquina sugeriu, **ninguém conferiu** | ❌ |
| **Rejeitada** | descartada | ❌ |

⛔ **Proposta não pode parecer anotação humana.** Se a diferença não for óbvia a três metros da tela,
o dataset é envenenado sem ninguém perceber.

- Câmera, data e hora · quantas caixas já tem
- **Progresso permanente:** `37 de 500 anotados`

---

# Tela 2 · ANOTAÇÃO — o coração do produto

É aqui que se ganha ou se perde o dia. **Teclado antes de mouse, sempre.**

## O fluxo que precisa existir

```
abre → desenha caixa → tecla da classe → desenha outra → tecla → [D] próxima
                                                                     ↑
                                                          salva sozinho, sem clique
```

- **Imagem grande**, ocupando o máximo da tela
- **Salvamento automático** com sinal claro. ⛔ Nunca um botão "salvar" para lembrar 500 vezes
- **Avanço automático** ao passar para a próxima — sem confirmar, sem voltar à galeria
- **Fila lateral** mostrando as próximas imagens da seleção, com quantas faltam

## Recursos que vêm da natureza do CFTV

🔴 **Copiar as caixas do frame anterior.** Frames sequenciais da mesma câmera são quase idênticos — a
pessoa andou meio metro. **Copiar e ajustar é 5× mais rápido que redesenhar.** É o atalho de maior
impacto do ambiente inteiro.

**Ajuste de brilho e contraste na visualização.** Imagem de CFTV é escura e contrastada. Sem isso, não
se enxerga o EPI em cena noturna. ⚠️ Ajusta **só a exibição**, nunca o arquivo.

**Zoom com lupa no cursor.** O capacete pode ter 20 px. Sem zoom não há julgamento possível.

**Atributos por caixa:** `ocluído` · `truncado` (cortado na borda) · `difícil`. É convenção do padrão
COCO e serve para excluir casos ruins do treino depois, sem perder a marcação.

## Controles

- Desenhar, mover, redimensionar por alças, apagar
- 🔴 **Classe por tecla numérica.** ⛔ Menu suspenso é a ação mais repetida da tela — não pode ter menu
- **Esconder/mostrar caixas** para conferir a imagem limpa
- **"Pular / em dúvida"** sempre à mão. Sem saída, o usuário trava numa imagem difícil e perde o ritmo
- **Desfazer e refazer**
- **Legenda de atalhos** discreta, e um `?` que abre a lista completa

## 🔴 As diretrizes de anotação vivem DENTRO da tela

O maior destruidor de dataset não é falta de imagem — **é critério inconsistente**. Anotar a pessoa
inteira em 200 frames e só a cabeça em 300 produz um modelo confuso, e **não dá para corrigir sem
reanotar tudo**.

Precisa haver um **painel de diretrizes sempre acessível** (tecla `G`), com:

- O que exatamente se marca em cada classe
- Os casos de borda **com exemplo visual**: pessoa cortada na borda · pessoa longe demais para julgar ·
  EPI ocluído · várias pessoas na cena · reflexo em vidro ou monitor
- **Versão e data** — é documento vivo, muda conforme aparecem casos novos

---

# Tela 3 · CLASSES — um lugar só

**Pedido explícito: um único lugar para editar as classes.**

- **Criar, renomear, arquivar** classe · **cor fixa** por classe, usada em toda a interface
- **Ordem = tecla numérica.** Reordenar muda o atalho — mostre o número ao lado do nome
- **Contagem de uso por classe**, ao vivo
- ⚠️ **Renomear é seguro; apagar não.** Classe usada em 80 caixas não pode sumir — **arquivar**, e
  avisar quantas caixas dependem dela
- É possível **criar classe dentro do anotador** sem perder o contexto — mas o registro nasce aqui
- 🔴 **Alerta de desbalanceamento:** se `capacete` tem 400 caixas e `luva` tem 12, **isso precisa
  gritar na tela**. Classe rara é a causa silenciosa nº 1 de modelo que parece bom e falha em produção

---

# Tela 4 · FERRAMENTAS DE IA

⚠️ **São duas coisas diferentes. ⛔ Não junte num botão só.**

## A · "Ache imagens parecidas com esta"

Parte de um frame **já anotado** e procura semelhantes no acervo.

- Acionada a partir de um frame selecionado — **a origem tem que estar visível na tela**
- O usuário escolhe **quantas**: 10 · 25 · 50 · 100
- Mostra quantas existem disponíveis **antes** de rodar
- Resultado: **N propostas** para a fila de aprovação. ⛔ Nada entra direto

## B · "Descreva o que você quer encontrar"

Campo de texto livre: *"pessoa sem capacete"*, *"trabalhador com colete refletivo"*.

- **Com exemplos visíveis** — ninguém sabe o que escrever numa caixa vazia
- Roda no frame aberto **ou** num lote selecionado
- ⚠️ **Isto erra bastante.** A tela comunica que é ponto de partida para o humano corrigir, não
  resultado. Sem prometer o que não entrega — a marca é *prova, não promete*
- Resultado: também **propostas**

## Fila de aprovação — a tela que faz a diferença entre 450 propostas úteis e 450 inúteis

- **Uma proposta por vez**, ocupando a tela
- 🔴 **Aprovar / rejeitar por tecla**, com a próxima entrando sozinha
- **Corrigir a caixa antes de aprovar** — "quase certa" é o caso mais comum
- **Aprovar em lote** o que estiver visivelmente bom
- **Motivo da rejeição** em um clique — alimenta o ajuste da ferramenta
- Contador de quanto falta

---

# Tela 5 · DATASET — antes do treino

## 🔴 A divisão treino / validação / teste — e a armadilha do CFTV

O padrão é **70 / 15 / 15**. Mas **como dividir importa mais que a proporção**:

> ⛔ **NUNCA dividir aleatoriamente por imagem.**
> Frames da mesma câmera no mesmo dia são quase idênticos. Dividindo por imagem, cópias quase iguais
> caem no treino **e** no teste — o modelo "acerta" porque já viu aquela cena. **A métrica mente**, e
> o modelo falha em produção sem aviso.

**Divida por câmera e por dia.** O conjunto de teste tem que conter cenas que o modelo **nunca viu**.

A tela precisa deixar isso explícito e permitir escolher o critério — e avisar quando a divisão está
correlacionada.

## O que mais precisa aparecer

- **Distribuição por classe** e **por câmera**, com aviso de desbalanceamento
- **Versão do dataset** com histórico — "modelo v3 foi treinado no dataset v2" é pergunta de contrato,
  não de engenharia
- **Duplicatas e quase-duplicatas** sinalizadas
- **Prévia da augmentation** — o que o modelo vai ver de verdade
- **Quantas imagens são suficientes?** Uma referência honesta na tela ajuda a decidir quando parar

---

# Tela 6 · TREINOS e MODELOS

- **Treinos:** fila e histórico · progresso com tempo estimado · curvas de perda e métrica ·
  **qual dataset e qual versão** originou cada treino · custo
- **Modelos:** desempenho **por classe** e **por câmera** (é onde se descobre que a CAM-05 não funciona)
  · comparar duas versões · promover para produção · voltar atrás
- 🔴 **Onde o modelo erra** — a ponte que fecha o ciclo, abaixo

## O ciclo que transforma o ambiente num estúdio profissional

Depois do primeiro modelo, **parar de anotar no aleatório.**

O modelo aponta as imagens em que ele está **menos seguro**, e são essas que valem anotar. É o mesmo
esforço humano rendendo muito mais — chamado *active learning*.

**Na tela:** um botão em Modelos — **"anotar onde o modelo erra"** — que devolve o usuário para a
galeria já filtrada por essas imagens.

⚠️ Com uma ressalva: só incerteza concentra o dataset numas poucas situações parecidas. **Misture com
variedade** — câmeras diferentes, horários diferentes.

---

# Atalhos de teclado — entregar como mapa

| Tecla | Ação |
|---|---|
| `D` / `→` | próxima imagem |
| `A` / `←` | anterior |
| `1`–`9` | escolher classe |
| 🔴 `C` | **copiar caixas do frame anterior** |
| `Del` | apagar caixa selecionada |
| `Ctrl+Z` / `Ctrl+Shift+Z` | desfazer / refazer |
| `Esc` | cancelar desenho |
| `F` | marcar "em dúvida" e avançar |
| `H` | esconder/mostrar caixas |
| `B` | ajuste de brilho |
| `+` / `−` | zoom |
| `G` | abrir diretrizes |
| `Enter` / `Backspace` | aprovar / rejeitar (fila de propostas) |
| `?` | ajuda |

---

# Estados que não podem faltar

- **Vazio** — diga o que fazer, não só "nada aqui"
- **Carregando** — miniaturas chegam aos poucos; ⛔ nunca a tela toda em branco
- **Imagem que não carrega** — ⚠️ acontece hoje. Aviso claro no card, não tela quebrada
- **Processando IA** — progresso real, e **o usuário continua anotando enquanto roda**
- **Erro ao salvar** — ⛔ tem que ser impossível não perceber. Anotação perdida em silêncio é o pior
  defeito possível deste ambiente
- **Treino falhou** — com motivo legível por quem não é engenheiro

---

# Marca — LOGIKOS

Dark-first. Proporção **70% preto · 20% branco-cinza · 10% acento**.

```css
--lk-preto:          #0A0A0F;  /* fundo */
--lk-grafite:        #14141C;  /* cards, superfícies, inputs */
--lk-branco-sinal:   #F4F6F8;  /* texto principal */
--lk-cinza-nevoa:    #8A8F98;  /* texto secundário, labels, bordas */
--lk-ciano-visao:    #00E5FF;  /* acento INTERATIVO: foco, seleção, links */
--lk-ciano-profundo: #0091AD;  /* hover / pressed */
```

**Tipografia:** *Space Grotesk* — títulos e números grandes · *Inter* — texto e botões ·
**JetBrains Mono** — contagens, timestamps, resoluções, métricas.

**Regras rígidas:**

- ⛔ Ciano **nunca** como fundo de página, e **nunca** como significado de estado
- ⛔ **Zero magenta** — existe só no glitch de marca, que não entra em UI operacional
- **Estado sempre com cor + ícone + palavra**, nunca só cor — procedência é o caso crítico
- Contraste mínimo **AA (4.5:1)**
- ⚠️ **As cores das classes são exceção** e não saem da paleta de marca: precisam ser distinguíveis
  entre si sobre imagem de CFTV escura. Trate como sistema à parte, com contraste verificado
- Movimento **curto e seco**, terminando em repouso. Sem animação contínua
- **Tom:** frases curtas, número quando há número, sem hype. "Proposta da máquina", não
  "inferência com score 0.87"

---

# ⛔ O que não fazer

- **Tratar "Dados" como navegador de arquivos.** É a porta da anotação
- **Menu suspenso para escolher classe** — a ação mais repetida da tela
- **Botão "salvar" manual** — alguém vai esquecer e perder trabalho
- **Diálogo de confirmação em ação reversível** — multiplique por 500
- **Voltar à galeria entre uma imagem e outra**
- **Proposta da máquina parecida com anotação humana**
- **Divisão aleatória do dataset** — mente sobre a qualidade do modelo
- **Bloquear a tela enquanto a IA processa**
- **Exclusão definitiva sem volta** no fluxo do dia a dia

---

# Entregáveis, em ordem de prioridade

1. 🔴 **Dados → Anotador**, com a ligação explícita e o fluxo "anotar em sequência"
2. 🔴 **Anotador completo** — caixas, classe por tecla, copiar do anterior, zoom, brilho, diretrizes
3. 🔴 **Mapa de atalhos** do fluxo inteiro
4. **Galeria** com filtros, seleção múltipla e barra de lote
5. **Classes** — o lugar único, com alerta de desbalanceamento
6. **Ferramentas de IA** + fila de aprovação
7. **Dataset** — divisão, balanço, versões
8. **Treinos e Modelos** + o botão "anotar onde o modelo erra"
9. **Os estados**

**1, 2 e 3 são o caminho crítico.** Sem eles as 500 imagens não saem do lugar.
