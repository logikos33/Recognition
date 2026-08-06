# Análise LGPD — Colheita retroativa de frames do NVR (RVB Isolantes)

**Para:** Vitor Emanuel (Logikos), como insumo para a assessoria jurídica
**Sobre:** proposta de extrair retroativamente frames da gravação contínua do NVR da RVB (trabalhadores reais,
operação real) para treinar o modelo de EPI do próprio cliente — em contraste com o lote de 679 frames de
**encenação** já coletado em 31/07/2026.
**Natureza deste documento:** análise técnica-jurídica preparatória. **Não é a decisão** — é o que a decisão
precisa considerar. A decisão é do Vitor, com a assessoria.

Fontes primárias usadas: `DICIONARIO_CONTRATO_RECOGNITION.md` (citado por linha), `docs/security/LGPD_PRIVACIDADE_CFTV.md`,
ADR-0028/0033/0034/0045/0047, `docs/PROTOCOLO_ENCENACAO_LOTE1_RVB.md`, `docs/FLYWHEEL_VOLTA_1_PROPOSTA.md`,
`docs/REGISTRO_DE_DECISOES.md` (D-11, D-16, D-31, D-33, D-37, D-38, D-39), e verificação direta no código
(`services/api/app/constants.py`, `services/api/app/infrastructure/queue/tasks/training.py`).

---

## 1. O que muda da encenação para a colheita retroativa

Em ambos os casos, o dado é o mesmo tipo: **imagem de pessoa identificável em ambiente de trabalho — dado
pessoal, "núcleo da cláusula de LGPD"** (dicionário, linha 71: *"Dataset... aqui são imagens de trabalhadores da
RVB... É dado pessoal."*). Isso não muda. O que muda é a **relação do titular com o ato de captação**.

**Encenação (31/07/2026, `docs/PROTOCOLO_ENCENACAO_LOTE1_RVB.md`):** uma pessoa foi especificamente convocada,
sabia a finalidade ("responder: em quantos pixels de cabeça cada item de EPI vira anotável"), caminhou
deliberadamente diante de 1 câmera, em rodadas cronometradas e registradas manualmente (A/B/C — concha, plug,
sem EPI), trocando de equipamento a pedido, com horário de início/fim anotado. Isso é uma **amostra pequena e
artificial** (679 frames, 1 câmera, poses), mais próxima de participação ativa e informada numa atividade
específica — sem ser, formalmente, um "consentimento LGPD" documentado (não há termo assinado; foi combinado
operacionalmente).

**Colheita retroativa proposta:** trabalhadores fazendo o trabalho normal deles, sem pose, sem saber que aquele
frame específico (entre milhares gravados) foi selecionado para entrar num dataset de treino de IA. A única base
preexistente é o monitoramento de CFTV que a RVB já opera por conta própria — e mesmo essa base tem lacuna de
transparência hoje (seção 5 abaixo). A expectativa razoável de quem trabalha sob CFTV industrial é "estou sendo
filmado para segurança geral", não necessariamente "meus frames viram dataset de IA, processados numa GPU
alugada de terceiro" (dicionário, linhas 73/105/138 — ver achado crítico na seção 4).

**Consequência direta:** a encenação não precisa de uma base legal tão robusta porque a interação com o titular
foi próxima, informada e específica. A colheita retroativa **precisa de base legal própria**, porque não há
esse elo — é sobre gente que nunca interagiu com a decisão de virar dado de treino.

---

## 2. Base legal candidata

**(a) O monitoramento CFTV em si** já é do cliente/controlador, preexistente ao Recognition — legítimo interesse
do empregador em segurança patrimonial e do trabalho (dicionário, linha 144: *"o cliente é controlador das
imagens dos próprios empregados; a Logikos é operadora"*; `LGPD_PRIVACIDADE_CFTV.md`, linha 21, já aponta essa
leitura). A Logikos não decide essa base — ela é dada, e a Logikos entra como operadora sobre ela.

**(b) O USO das gravações para TREINAR o modelo** é finalidade adicional, distinta da finalidade original do
CFTV (vigilância geral). Pelo princípio da finalidade (LGPD art. 6º, II), isso não herda automaticamente a base
do CFTV — precisa de fundamento próprio:

| Base | Avaliação para este caso |
|---|---|
| **Legítimo interesse do controlador** (art. 7º, IX) | Candidata mais forte. Finalidade (segurança do trabalho / verificação de EPI) é legítima e mensurável; `LGPD_PRIVACIDADE_CFTV.md` linha 21 já sinaliza essa leitura como "normalmente". Exige **LIA (relatório de legítimo interesse)** documentado — hoje inexistente (o próprio RIPD é `⟨TODO⟩` em vários pontos, ver seção 6). |
| **Obrigação legal** (NRs de segurança do trabalho) | Fraca **especificamente para o treino**. Nenhuma NR exige "treinar um modelo de IA com imagens dos trabalhadores" — a obrigação legal está em ter e fiscalizar o uso de EPI, não no meio tecnológico escolhido para isso. Pode sustentar o CFTV/fiscalização em si, não o treino de IA como ato isolado. |
| **Consentimento individual** | Frágil, e mais frágil ainda no caso retroativo (ver abaixo). |

**Teste de 3 etapas do legítimo interesse, aplicado:**
1. **Legitimidade da finalidade** — sim. Verificação de uso de EPI é finalidade legítima, com benefício direto
   à segurança dos próprios titulares.
2. **Necessidade** — a favor: a própria motivação técnica da encenação reconhece que pose artificial não cobre
   a variedade real de postura, distância e oclusão que o modelo vai enfrentar em produção (o protocolo já
   compara "8 frames em 40 min de espera real" vs. pose deliberada — `PROTOCOLO_ENCENACAO_LOTE1_RVB.md`, linhas
   9-12). Frames de operação real são necessários para o modelo funcionar de verdade; a amostragem proposta
   (esparsa, filtrada por pessoa, ~500 frames) é proporcional a essa necessidade, não excessiva.
3. **Balanceamento com os direitos do titular** — a favor: não é dado sensível de saúde per se (é
   presença/ausência de item, não diagnóstico); minimização técnica já aplicada (seção 3). Contra: câmera de
   segurança com IA pode intensificar a sensação de vigilância — mitigado com aviso claro e escopo restrito
   (seções 3 e 5).

**Por que consentimento individual é frágil em relação de emprego:**
- Assimetria de poder — é difícil sustentar que a recusa de um trabalhador em "participar do dataset" seria
  isenta de qualquer custo informal (constrangimento, percepção de resistência a política de segurança).
- Revogação impraticável — retirar o consentimento de UM trabalhador de um dataset já usado para treinar um
  modelo não é trivial: apagar o frame do storage é possível, mas o modelo já treinado não "esquece" o que
  aprendeu daquele exemplo. Isso é reconhecido implicitamente no próprio projeto: D-39 exige que **toda anotação
  carregue procedência desde o primeiro registro** porque *"retroagir procedência em anotação já feita é
  impossível"* (`docs/REGISTRO_DE_DECISOES.md`, linha 171-172) — o mesmo problema estrutural se aplica ao frame
  bruto.

**Recomendação de leitura:** legítimo interesse do controlador (RVB), com LIA documentado, complementado por
transparência robusta (seção 5) — não consentimento individual coletado ad hoc.

---

## 3. Finalidade e minimização

**O que o pipeline já minimiza (argumento a favor):**
- **Amostragem esparsa** (1 frame a cada 30-60s) — não é vídeo contínuo, reduz volume e densidade de captação
  por pessoa.
- **Filtro por presença de pessoa** — só grava quando há alguém no quadro (evita acúmulo de frames vazios sem
  propósito).
- **Só frame estático, não clipe** — a arquitetura de evidência operacional (alertas/verificação) já usa clipes
  de 20-30s (ADR-0033); a colheita de **treino** é deliberadamente mais restrita (frame único), escolha de
  minimização a favor do titular.
- **Sem áudio.**
- **Sem reconhecimento facial / sem identificação nominal automatizada** — o modelo detecta classe de objeto
  (presença/ausência de item de EPI), não identifica quem é a pessoa. Reduz o risco de perfilamento individual
  automatizado, mesmo que a imagem, tecnicamente, ainda permita reconhecimento visual por um humano.
- **Escopo de câmera já restrito**: hoje 8 canais mapeados (canais 1-8 do iNVD 3032); os 2 gravadores extras e
  as ~21 câmeras adicionais descobertas na rede estão **fora de escopo** (D-11, `docs/REGISTRO_DE_DECISOES.md`,
  linha 38; dicionário, seções 8 e 11) e não devem ser tocados pela extração retroativa.

**O que ainda falta fazer (lacunas a fechar antes de colher):**
- **Excluir áreas de descanso/vestiário/refeitório/banheiro.** Já reconhecido como necessário em
  `LGPD_PRIVACIDADE_CFTV.md`, linha 27 (*"evitar áreas de intimidade"*), mas como diretriz geral — ainda não
  como filtro técnico aplicado à extração. Se qualquer uma das 8 câmeras em escopo enquadra essas áreas, precisa
  exclusão explícita (por câmera) antes de rodar a extração retroativa.
- **Prazo de retenção específico do dataset de treino.** O campo técnico existe (`retention_days` por câmera/
  tenant, migration 079) mas está sem valor definido para evidência (`LGPD_PRIVACIDADE_CFTV.md`, linha 36:
  *"⟨TODO: definir — mercado típico 15-90 dias⟩"*) — e um **dataset de treino tende a viver mais** que evidência
  de alerta (é reaproveitado a cada retreino). Precisa de prazo próprio, justificado, não herdar por omissão.
- **Revogabilidade por origem.** Cada frame extraído retroativamente deveria carregar uma tag de
  sessão/origem (ex.: `collection_session_id`) que separe claramente "encenação 31/07" de "retroativo agosto/
  2026" de "coleta contínua operacional" — o mesmo princípio que o projeto já aplicou à **anotação** (D-39: toda
  anotação carrega procedência humana/proposta/aprovada/rejeitada), estendido ao **frame bruto**. Sem isso, um
  pedido de exclusão (de um titular, ou uma decisão de descontinuar o lote) não tem como ser atendido em lote —
  viraria busca manual frame a frame.

---

## 4. O que precisa mudar/entrar no `DICIONARIO_CONTRATO`

**a) Cláusula explícita de leitura retroativa do NVR.** O dicionário hoje descreve captura de frames "ao vivo"
(seção 3, etapa 2 — "o sistema coleta imagens de situações reais da operação") e cita o mecanismo técnico já
desenhado para acesso a gravação histórica só na ADR-0034 (cadastro de gravador → busca de timeline → extração
de frames), que **não está referenciado no dicionário**. É preciso adicionar cláusula que autorize expressamente
a Logikos a **ler o histórico já gravado pelo NVR do cliente** (não só capturar frames novos daqui para frente)
para fins de dataset — hoje isso é uma lacuna, não uma autorização implícita.

**b) 🔴 Suboperador de GPU — achado crítico, precisa correção antes de assinar.** O dicionário nomeia RunPod como
o provedor de GPU nas linhas 73, 105 e 138 (*"Treinamento... roda em servidores de GPU alugados... (RunPod)"*,
*"As imagens do cliente saem da infraestrutura da Logikos nesta etapa"*, *"Imagens durante o treinamento | RunPod
(GPU de terceiro)"*). **Essa informação está desatualizada e é o exato ponto que a cadeia de suboperadores do
contrato (linha 146: "Railway, Cloudflare e RunPod precisam estar listados") depende.** A investigação nos
registros do próprio projeto mostra o oposto:
- `docs/REGISTRO_DE_DECISOES.md`, D-16→D-31: *"Provedor de GPU do modelo de visão é Vast.ai (código); RunPod é
  outro sistema (LLM)"* — e a entrada de correção datada de 04/08 (mesma página, linhas 174-190) documenta que
  Vitor havia afirmado verbalmente "usamos RunPod", isso foi aceito sem verificação, e a checagem de código
  mostrou o contrário: `vast_client.py` fala com `console.vast.ai` de verdade; a conexão RunPod existente é do
  **fine-tune do assistente de chat (LLM)**, sistema diferente, fora do pipeline de visão.
- Confirmado agora, nesta análise, direto no código: `services/api/app/constants.py` define
  `GpuProvider.VAST_AI` como provedor de treino de visão; `services/api/app/infrastructure/queue/tasks/training.py`
  (linhas 7, 78, 808) traz o comentário **"GPU de terceiro (pode ser RunPod por baixo, investigação em
  curso)"** — ou seja, mesmo a engenharia trata isso como **não resolvido**.
- Isso importa duplamente porque D-33 registra a própria razão pela qual RunPod foi cogitado: *"a Vast.ai é
  marketplace de GPU — datacenter, empresa e país desconhecidos, **suboperador impossível de nomear em
  contrato**"* (`docs/REGISTRO_DE_DECISOES.md`, linhas 78-80). Se o dispatch real de treino ainda usa Vast.ai (o
  que o código confirma hoje), **o contrato não tem hoje como nomear com precisão quem processa a imagem do
  trabalhador durante o treino** — nomear "RunPod" seria descrever errado a realidade técnica.

**Recomendação:** não fechar a cláusula de suboperador de GPU com o texto atual do dicionário. Resolver a
investigação de código (qual provedor está de fato ligado no dispatch de treino de visão) **antes** de escrever
o nome no contrato — e antes de autorizar qualquer treino real com os frames da colheita retroativa.

**c) Transferência internacional.** Já reconhecida como pendência (dicionário, linha 142-143: *"região de
armazenamento a definir"*). A colheita retroativa não muda a arquitetura de armazenamento (R2, ADR-0028/0045),
mas **aumenta o volume** de dado pessoal de operação real sujeito a essa transferência. Reforçar no contrato a
cláusula de garantia adequada (cláusulas-padrão ou equivalente) e confirmar região antes de subir o lote.

**d) Vedação de reuso cross-cliente.** O dicionário já identifica isso como o maior risco entre as decisões
propostas (seção 7, linhas 230-256) e sugere o desenho: *"imagens brutas permanecem do cliente, uso restrito à
finalidade contratada; modelo, pesos e artefatos derivados são da Logikos; dados agregados sem identificação são
livres"*. Essa decisão **ainda está em aberto** ("levar as duas opções à reunião do dia 6" — hoje). Ela precisa
estar fechada **antes** de autorizar a colheita retroativa, não depois: agora, pela primeira vez, as imagens são
de trabalhadores reais em operação real (não posando por acordo), o que torna qualquer reuso cross-cliente mais
sensível — maior verossimilhança de identificação, maior expectativa de privacidade se descoberto.

**e) Direitos dos titulares via controladora.** O dicionário já prevê que o pedido de acesso/exclusão chega ao
empregador e que o contrato precisa definir prazo e forma de apoio da Logikos (linha 151-152). Com a colheita
retroativa isso fica mais concreto: como localizar e expurgar, tecnicamente, os frames de UM trabalhador dentro
de um dataset parcialmente usado em treino? A resposta técnica é a tag de sessão/origem (seção 3); ela precisa
virar SLA contratual (prazo de atendimento) e o contrato deve dizer com honestidade que **expurgar do storage é
possível; "desaprender" de um modelo já treinado não é** — a forma prática de atender isso é reexecutar o treino
sem aquele lote.

---

## 5. Aviso aos trabalhadores

É **obrigação da RVB** (controladora), com apoio técnico da Logikos — dicionário, linha 148 (*"a obrigação de
informar os empregados... é do empregador, não da Logikos, mas o contrato deve dizer isso com todas as
letras"*) e linha 171 (*"informar trabalhadores sobre o monitoramento — é do empregador"*). O RIPD-scaffold
(`LGPD_PRIVACIDADE_CFTV.md`, seção 5) ainda tem essa transparência como `⟨TODO⟩` — ou seja, **hoje não há
confirmação de que existe aviso adequado na planta**.

Antes de autorizar a colheita retroativa, a Logikos deveria obter confirmação por escrito da RVB de que:
1. Existe aviso de monitoramento por CFTV visível nas áreas cobertas pelas 8 câmeras em escopo.
2. Esse aviso cobre, especificamente, a finalidade nova — "as imagens também alimentam um sistema de IA de
   verificação de EPI" — porque o princípio da finalidade não se satisfaz com um aviso genérico de "área
   monitorada por segurança" quando a finalidade real passou a incluir "treinar um modelo, processado por um
   operador terceiro, possivelmente numa GPU de outro terceiro".
3. O tema foi tratado com CIPA/sindicato onde aplicável (dicionário, linha 148).

**Minuta curta de texto de aviso** (ponto de partida para a assessoria, não redação final):

> *"ÁREA MONITORADA POR CÂMERAS DE SEGURANÇA. As imagens desta área são gravadas para fins de segurança
> patrimonial e segurança do trabalho, incluindo verificação do uso de Equipamentos de Proteção Individual
> (EPI). Parte das imagens pode ser utilizada para treinar sistema de inteligência artificial de apoio à
> fiscalização de EPI, operado em nome da RVB Isolantes pela empresa Logikos. Em caso de dúvidas sobre o
> tratamento de suas imagens, procure [CIPA / SESMT / RH / encarregado de dados]."*

---

## 6. Riscos residuais e mitigações

| Risco | Impacto se não mitigado | Mitigação |
|---|---|---|
| Base legal do treino ainda não formalizada (sem LIA escrito) | Tratamento sem base legal defensável se questionado | Redigir e assinar o LIA (teste de 3 etapas, seção 2) antes de autorizar a extração |
| Suboperador de GPU não identificável hoje (código trata como "investigação em curso"; Vast.ai é marketplace anônimo) | Cláusula de suboperador nomeado fica imprecisa ou factualmente errada; imagem pode ir a datacenter/país desconhecido | Resolver no código qual provedor está de fato no dispatch de treino antes de nomear no contrato; represar o treino real até resolvido |
| Aviso ao trabalhador não confirmado na planta | Quebra do princípio da finalidade/transparência; risco de reclamação individual ou coletiva | RVB confirma por escrito aviso existente e o atualiza para cobrir a finalidade de treino de IA (seção 5) |
| Câmeras fora de escopo (21 adicionais) ou áreas de descanso dentro das 8 em escopo | Coleta além da finalidade e do escopo contratado | Restringir extração às 8 câmeras do anexo (D-11); excluir manualmente qualquer câmera das 8 que aponte para área de descanso |
| Frames sem tag de sessão/origem | Impossibilidade prática de atender pedido de exclusão por titular ou por lote | Implementar `collection_session_id` no frame ANTES de rodar a extração (seção 7) |
| Retenção do dataset de treino sem prazo definido | Guarda por tempo indeterminado — viola princípio de necessidade | Definir prazo específico do dataset (distinto da evidência operacional) e aplicar expurgo automático |
| Decisão de reuso cross-cliente ainda em aberto (dicionário seção 7) | Se resolvida "sem restrição" depois da colheita, dado real de trabalhador vira insumo de risco concorrencial | Fechar essa decisão antes de autorizar a colheita, não depois |
| Transferência internacional (R2) sem região/salvaguarda confirmada | Transferência sem enquadramento LGPD válido | Confirmar região de armazenamento e mecanismo de transferência antes de subir volume adicional de imagens reais |

---

## 7. Recomendação técnica (não jurídica) — para tornar a decisão reversível

Antes de rodar a extração retroativa, o pipeline deveria implementar:

1. **Tag de origem/sessão em cada frame extraído** (ex.: `collection_session_id`), separando claramente
   "encenação 31/07", "retroativo [data]" e "coleta contínua operacional" — permite expurgo em lote, e é a
   mesma lógica de proveniência que o projeto já decidiu para anotação (D-39), estendida ao frame bruto.
2. **Exclusão de câmeras sensíveis**: checar as 8 câmeras em escopo (canais 1-8 do iNVD 3032) e confirmar que
   nenhuma aponta para vestiário/banheiro/área de descanso; se alguma apontar, excluir da extração ou mascarar a
   região de interesse.
3. **Janela de horário**: considerar restringir a extração a horário de expediente/operação, evitando trocas de
   turno ou horários de refeição mesmo em câmeras de área operacional.
4. **Represar o treino real até a cláusula de suboperador estar resolvida** — preparar/anotar o dataset dentro do
   perímetro Logikos (self-hosted, ADR-0047/0048, sem envio a SaaS de terceiro) e só disparar o treino em GPU
   externa depois que ficar definido, no código e no contrato, qual provedor recebe a imagem.
5. **Registrar a extração como evento auditável** (quem disparou, de qual câmera, qual intervalo, quantos
   frames) — mesmo padrão de auditoria já usado para impersonação (D-37).
6. **Manter os frames brutos, identificados por sessão, sem anotar/treinar com eles** até a base legal (seção 2)
   estar documentada — assim, se a assessoria concluir que ainda não está madura, o lote inteiro pode ser
   apagado pela tag de sessão sem ter contaminado dataset, modelo ou outros lotes.

Essas seis ações são o que torna a decisão do Vitor **reversível**: nada impede desfazer a colheita se a resposta
jurídica for "ainda não" — desde que a tag de sessão exista *antes* de colher, não depois.
