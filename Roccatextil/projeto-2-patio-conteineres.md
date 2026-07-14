# Projeto 2 — Pátio de Contêineres

**Documento de descoberta** · Atualizado em 10/06/2026 · Estágio: levantamento inicial · **Executa após o Projeto 1 (expedição RoccaTextil)**

---

## 1. Visão geral

Sistema de visão computacional para um depósito de contêineres com três objetivos centrais:

1. **Entrada** — detectar e registrar automaticamente a chegada de contêineres no depósito
2. **Movimentação** — rastrear quando um contêiner é movido dentro do pátio
3. **Localização** — saber a posição exata de cada contêiner a qualquer momento

Cada contêiner possui um identificador único ("CPF" do contêiner), que será a chave de rastreamento — provavelmente lido por OCR a partir das câmeras.

**Diretriz estratégica:** montar uma estrutura para **reduzir ao máximo o trabalho humano** — a solução deve acontecer de forma automatizada, com reconhecimento de contêiner e controle da logística das cargas. Visão de longo prazo ("modo utópico"): **drones** sobrevoando a área e **robôs humanoides para segurança patrimonial**.

**Ativos reutilizáveis:** recognition já existente + módulo de carregamento (mesma base do Projeto 1).

## 2. O que já se sabe

| Item | Status |
|---|---|
| Estágio | Levantamento inicial, sem proposta fechada |
| Identificação | Cada contêiner tem código único ("CPF") |
| Infraestrutura de câmeras | Inexistente — projeto inclui especificar e instalar do zero |
| Cliente | RoccaTextil |
| Tipos de contêiner | 20 pés e 40 pés |
| Equipamentos de pátio | 2 empilhadeiras + 2 handstack (reach stacker); ponte rolante pórtica em avaliação |
| Empilhamento máximo | 9 contêineres por norma, mas limitado na prática pelo alcance dos equipamentos |
| Horário de operação | Possivelmente 24/7 — **não confirmado** |

## 3. Premissas (a validar)

- O "CPF" é visível externamente no contêiner e legível por câmera (verificar se segue padrão ISO 6346/BIC ou é código interno).
- A movimentação é feita por equipamentos (empilhadeira/reach stacker/caminhão) — relevante para escolher pontos de captura.
- O depósito tem zonas/posições definíveis (mapa de pátio) para expressar "localização".
- Haverá energia e rede (ou possibilidade de instalar) nos pontos de câmera.

## 4. Perguntas em aberto (para o levantamento)

### Operação
- Qual o tamanho do pátio (m², nº de posições) e quantos contêineres em média/pico?
- Quantos portões de entrada/saída? Volume diário de movimentações?
- ~~Contêineres são empilhados? Quantos níveis?~~ → **Respondido:** até 9 por norma; na prática limitado pelo equipamento. Levantar altura real praticada por zona.
- ~~Operação é 24/7?~~ → **Parcial:** possivelmente 24/7, aguardando confirmação do cliente.
- Como o controle é feito hoje (planilha, sistema, papel)? Há sistema (ERP/WMS) para integrar?

### Identificação
- Como é o "CPF": formato, tamanho, onde fica pintado/afixado no contêiner, padrão de fonte?
- Estado de conservação dos códigos (ferrugem, tinta gasta) — afeta acurácia do OCR.
- O código é visível de quais faces (portas, laterais, teto)?

### Infraestrutura
- Há rede elétrica e de dados nos pontos candidatos a câmera? Postes/estruturas para fixação?
- Internet no local (banda disponível)? Processamento pode ser em nuvem ou precisa ser local (edge)?
- Restrições de orçamento para câmeras/servidor?

### Requisitos
- ~~Precisão de localização: zona ou slot exato?~~ → **Respondido: o cliente precisa do local EXATO do contêiner** (slot + nível na pilha). Tecnologia em aberto: visão computacional pura, ou híbrido com IoT/RFID — decisão adiada para depois do levantamento.
- Latência aceitável: tempo real ou consolidação periódica?
- Quem usa o sistema e como (painel web, app, alertas, relatórios)?
- Requisitos de retenção de vídeo/evidências?

## 5. Arquitetura técnica preliminar (hipótese)

**Pipeline:** câmeras IP → ingestão de vídeo (RTSP) → detecção de contêiner (YOLO ou similar) → OCR do código ("CPF") → tracking/associação → mapa de pátio + banco de dados → painel/API.

**Pontos de captura prováveis:**
- **Portão (gate):** câmeras dedicadas para entrada/saída — melhor ponto para OCR confiável (distância e ângulo controlados)
- **Pátio:** câmeras panorâmicas para tracking de movimentação e localização por zona
- Alternativa/complemento: câmera embarcada na empilhadeira para registrar pega/solta com posição

**Componentes:**
- Câmeras IP (resolução e lente conforme distância de leitura do código)
- Servidor de processamento (GPU local/edge ou nuvem, conforme banda)
- Banco de dados de eventos (entrada, movimentação, posição atual)
- Interface: painel de pátio + histórico por contêiner

## 6. Fluxo de entrada (gate) e recomendação de posicionamento

**Processo quando o motorista chega ao pátio:**

1. **Pesagem** do contêiner
2. **Validação do estado** — inspeção de avarias/condição geral
3. **Classificação limpo/sujo**
4. **Grau de empilhamento** — quanto peso suporta em cima (contêiner mais velho suporta menos)
5. **Recomendação do sistema:** com base nos itens acima, o sistema indica **para onde encaminhar o contêiner e o melhor posicionamento na pilha**

**Lógica de posicionamento (a refinar):**
- Contêiner velho/com avarias → base não, topo da pilha ou zona de menor empilhamento
- Contêiner novo/íntegro → pode ir para a base de pilhas altas
- Limpo vs. sujo → provável segregação por zona (validar regra com cliente)
- Peso aferido na pesagem entra no cálculo de quem aguenta quem
- **Contêiner vazio** também precisa de encaminhamento próprio (zona/regra específica para vazios)
- Segregação por tamanho: **20 pés vs. 40 pés** (pilhas separadas; não se empilha 40 sobre 20 desalinhado)

**Equipamentos de movimentação:**
- 2 empilhadeiras
- 2 handstack (reach stacker)
- Em avaliação: ponte rolante pórtica (RTG/portêiner) — se entrar, muda o layout do pátio e os pontos de câmera; a recomendação de slot precisa considerar o alcance de cada equipamento

**Implicações técnicas:**
- Integração com balança (a pesagem alimenta o sistema automaticamente?)
- O gate vira o ponto central do sistema: OCR do "CPF" + inspeção de avarias + classificação limpo/sujo numa mesma passagem
- Motor de recomendação de slot: cruza estado do contêiner, peso, mapa do pátio e ocupação atual das pilhas
- Saída para o operador: indicação clara de destino (ex.: tela/impresso/app para o motorista ou empilhadeira)

**Perguntas em aberto:**
- Qual a altura máxima de empilhamento por equipamento (empilhadeira vs. handstack vs. futura ponte)?
- Há zonas atendidas só por um tipo de equipamento?
- Vazios têm zona dedicada? Qual a regra de encaminhamento de vazios hoje?
- Proporção 20 vs. 40 pés no pátio? Pilhas separadas por tamanho?
- A balança já existe? Tem interface digital (protocolo/porta) para integração?
- Quem decide hoje onde o contêiner vai? Qual regra informal é usada?
- "Limpo/sujo" é só visual externo ou inclui interior (abrir portas no gate)?
- Quais são os "graus" de empilhamento usados? Existe tabela por idade/estado?
- A recomendação é sugestão (operador confirma) ou ordem (sistema decide)?

## 7. Serviço à parte — Avaliação de avarias e capacidade de empilhamento

> Demanda separada do escopo principal, prestada como serviço adicional.

**Contexto:** um contêiner roda no máximo ~5 anos por conta da degradação da capacidade de empilhamento.

**Objetivo:** a partir das avarias visíveis do contêiner (amassados, corrosão, danos estruturais), **estimar quanta carga ele ainda suporta em cima** — ou seja, classificar a capacidade residual de empilhamento.

**Implicações técnicas (hipótese):**
- Inspeção visual por câmera (possivelmente no gate, aproveitando a mesma infra): detecção e classificação de avarias por face do contêiner
- Modelo de severidade: avaria detectada → estimativa de capacidade de carga residual (provavelmente exige critério de engenharia estrutural ou histórico de inspeções para calibrar)
- Vincular laudo/score ao "CPF" do contêiner, com histórico ao longo da vida útil

**Perguntas em aberto:**
- Existe critério/norma usado hoje para condenar um contêiner (ex.: CSC/IICL)? Quem faz essa avaliação atualmente?
- Há histórico de inspeções/laudos que sirva de base para treinar/calibrar o modelo?
- A estimativa precisa ser quantitativa (toneladas) ou classificatória (apto a empilhar N níveis / restrito / condenado)?
- Avarias internas/no piso contam? Câmera só vê o exterior.

## 8. Riscos identificados

- **OCR em campo aberto:** chuva, sol direto, sujeira e códigos desgastados degradam leitura — gate controlado mitiga.
- **Oclusão no pátio (ponto crítico):** com empilhamento de até 9 unidades (~22 m de altura), pilhas altas criam "paredes" que bloqueiam completamente a visão de corredores e pilhas vizinhas. Precisa ser estudado a fundo na visita técnica. Estratégias possíveis:
  - Câmeras em postes/mastros altos (acima da altura máxima de pilha) com visão de topo/diagonal
  - Câmeras por corredor, em vez de panorâmicas
  - Localização por inferência de eventos: rastrear o movimento no gate e nas pontas de corredor (entrou no corredor X, posição estimada por última detecção) em vez de visão contínua de cada slot
  - Câmera embarcada nos equipamentos (empilhadeira/handstack) registrando pega/solta — independe de oclusão do pátio
  - Se a ponte rolante pórtica for adquirida: câmera no trolley da ponte vê de cima, eliminando boa parte da oclusão
  - **IoT/RFID como complemento (em aberto):** como o requisito é localização EXATA, tag RFID/beacon por contêiner + leitores no pátio/equipamentos resolve a localização independente de oclusão, deixando a visão computacional para gate, avarias e validação. Decisão de tecnologia adiada — comparar custo (tag por contêiner + leitores) vs. câmeras adicionais no levantamento.
- **Operação 24/7 (não confirmado):** se confirmar, exige iluminação adequada ou câmeras com IR/baixa luz nos pontos de leitura, e infra sem janela de manutenção.

## 9. Visão de longo prazo ("modo utópico")

Registrado para exploração futura, sem compromisso no escopo atual:

- **Drones** sobrevoando o pátio — inventário aéreo, verificação de topo de pilha (onde a câmera fixa não alcança)
- **Robôs humanoides para segurança patrimonial** — rondas autônomas
- Operação com mínima intervenção humana: do gate à alocação, tudo automatizado

## 10. Próximos passos

1. Visita técnica ao depósito: fotos do pátio, dos códigos nos contêineres, dos portões e da infra existente
2. Responder as perguntas da seção 4 com o cliente
3. Definir tecnologia de localização exata (visão pura vs. híbrido IoT/RFID)
4. Esboçar planta de câmeras com quantidade e posicionamento estimados
5. Montar proposta técnica/comercial com fases (sugestão: Fase 1 = gate/entrada; Fase 2 = pátio/localização)
