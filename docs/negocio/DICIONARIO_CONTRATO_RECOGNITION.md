# Recognition — Dicionário técnico e operacional para elaboração do contrato

**De:** Vitor Emanuel — Logikos · **Para:** assessoria jurídica · **Data:** 2026-08-03
**Cliente do contrato:** RVB Isolantes (Blumenau/SC)

> **Como ler este documento.** As seções 1 a 5 respondem "o que é e como funciona" — é o dicionário pedido.
> As seções 6 a 8 vão além: são os pontos onde a tecnologia cria risco jurídico que precisa de cláusula.
> A seção 9 lista o que ainda precisa de decisão.
>
> Escrito por quem constrói o sistema, não por advogado. Os fatos técnicos são precisos; a qualificação jurídica
> deles é da assessoria.

---

## ⚠️ Correção de uma premissa antes de tudo

A mensagem inicial menciona *"o armazenamento das imagens no servidor físico que fica no cliente"*.
**Não é assim que funciona, e a diferença é relevante para o contrato.**

O equipamento instalado no cliente **processa** as imagens, mas **não é o destino de armazenamento**. Ele tem
128 GB, ocupados por sistema operacional e aplicação. O armazenamento de evidências é **em nuvem**.

Consequência jurídica: as cláusulas de guarda, retenção, segurança e eventual **transferência internacional** de
dados precisam olhar para a nuvem, não para o equipamento no chão de fábrica. Detalhe na seção 4.

---

## 1. O que o sistema é, em linguagem simples

O **Recognition** é um sistema de visão computacional que assiste às câmeras de segurança que o cliente **já tem**
e identifica situações de interesse — por exemplo, uma pessoa circulando sem óculos de proteção.

Três características que definem o produto e aparecem em várias cláusulas:

1. **Não é um detector pronto.** Cada cliente tem um modelo treinado com as imagens da própria operação. Um sistema
   treinado para a RVB não serve para outra fábrica sem novo treinamento.
2. **O processamento é local.** Um computador instalado na fábrica analisa o vídeo ali mesmo. A internet é usada
   para enviar resultados e evidências, não o vídeo contínuo.
3. **É uma ferramenta de apoio, não um substituto da fiscalização humana.** Isto não é ressalva de marketing — é
   fato técnico com consequência jurídica direta (seção 6.1).

---

## 2. Glossário — termo por termo

### 2.1 Equipamentos e infraestrutura física

| Termo | O que é | Por que aparece no contrato |
|---|---|---|
| **Edge** (ou "servidor de borda", "caixa") | O computador instalado na fábrica que processa o vídeo. Modelo: **NVIDIA Jetson Orin NX Super 16GB**. Fisicamente pequeno — cabe numa caixa de sapato. | É o bem objeto da **venda** ao cliente. Precisa de cláusula de garantia, substituição e instalação. |
| **Roteador / firewall** | Equipamento **MikroTik** que cria o túnel seguro de comunicação entre a fábrica e a Logikos. | Também vendido. Define o limite da rede sob responsabilidade de cada parte. |
| **Câmeras IP** | Câmeras de rede do cliente (marcas Hikvision e Intelbras na RVB). **São do cliente e normalmente já existem.** | A Logikos não fornece nem garante as câmeras. O posicionamento adequado é condição de funcionamento. |
| **NVR / gravador** | Equipamento **do cliente** que grava e armazena o vídeo das câmeras 24h. Já existia antes do Recognition. | O Recognition **lê** deste equipamento. Se ele falhar ou for desligado, o sistema não funciona — e a falha não é da Logikos. |
| **VLAN de câmeras** | Segmento de rede isolado onde vivem as câmeras. | Isolamento exigido por segurança: câmeras expostas à internet são alvo de ataque e travam sozinhas por proteção contra tentativas de invasão. |
| **VPN / WireGuard** | Túnel criptografado pelo qual a Logikos acessa o equipamento remotamente para manutenção. Sempre iniciado **de dentro da fábrica para fora** — a Logikos não "entra" na rede do cliente sem que o equipamento local abra a conexão. | Base para a cláusula de acesso remoto e de segurança da informação. |

### 2.2 Software e nuvem

| Termo | O que é | Por que aparece no contrato |
|---|---|---|
| **Plataforma / painel** | O site onde o cliente vê alertas, câmeras, relatórios. Acessado por navegador, com login. | É o serviço licenciado (SaaS). |
| **Nuvem** | Servidores onde a plataforma roda (provedor **Railway**) e onde as imagens ficam guardadas (**Cloudflare R2**). | Define onde o dado está fisicamente — e se há transferência internacional (seção 4.3). |
| **Multi-tenant / isolamento por cliente** | Cada cliente tem sua área separada no banco de dados. Um cliente não enxerga dado de outro, por construção técnica. | Sustenta a cláusula de confidencialidade e sigilo entre clientes. |
| **White-label** | A plataforma pode exibir a marca do cliente. | Se aplicável, gera cláusula de licença de uso de marca. |

### 2.3 Inteligência artificial — os termos que mais confundem

| Termo | O que é | Por que aparece no contrato |
|---|---|---|
| **Modelo** | O "cérebro" treinado que reconhece os itens. Tecnicamente é um arquivo com números — não contém imagens. | **Ativo central da Logikos.** Objeto da cláusula de propriedade intelectual. |
| **Dataset** | O conjunto de imagens usadas para ensinar o modelo. Aqui **são imagens de trabalhadores da RVB**. | É dado pessoal. Núcleo da cláusula de LGPD. |
| **Anotação** | O trabalho humano de marcar, em cada imagem, onde está o item (ex.: desenhar um quadrado sobre o óculos). | É trabalho intelectual, feito por pessoas. Quem faz e de quem é o resultado precisa estar definido. |
| **Treinamento** | O processo de usar o dataset anotado para produzir o modelo. Roda em servidores de GPU alugados (provedor **RunPod**). | Envolve **enviar as imagens do cliente a um terceiro**. Precisa constar na cadeia de subcontratados. |
| **Inferência** | O ato de o modelo analisar uma imagem e dizer o que vê. É o que roda 24h no equipamento da fábrica. | É a prestação de serviço em si. |
| **Shadow mode** (modo sombra) | Fase em que o sistema observa e registra, **mas não emite alerta**. Serve para medir a qualidade antes de confiar nele. | **A RVB está nesta fase.** Determina a partir de quando as obrigações de desempenho passam a valer (seção 6.2). |
| **Falso negativo** | O sistema **deixa de detectar** algo que existia — por exemplo, não identifica um trabalhador sem protetor auricular. | **A cláusula mais importante do contrato.** Seção 6.1. |
| **Falso positivo** | O sistema aponta uma irregularidade que não existia. | Gera desgaste operacional e desconfiança, mas não risco de acidente. |
| **Acurácia / precisão / revocação** | Medidas de quanto o sistema acerta. Nenhum sistema de visão computacional chega a 100%. | Base de qualquer meta de desempenho que se queira contratar. |

### 2.4 Operação

| Termo | O que é |
|---|---|
| **Evento** | Um registro de que algo foi identificado (data, hora, câmera, o que foi visto). |
| **Alerta** | Notificação enviada a um responsável quando um evento viola uma regra configurada. |
| **Evidência / clipe** | Trecho de vídeo de ~20 a 30 segundos ao redor do evento, guardado como comprovação. |
| **Regra por zona** | Configuração do que é exigido em cada área. A mesma detecção gera ou não violação conforme o local. |
| **Módulo** | Conjunto de funcionalidades por finalidade. Na RVB: **EPI/Segurança**, **Qualidade** e **Pátio/Estacionamento**. |
| **Retenção** | Por quanto tempo cada tipo de dado é guardado antes de ser apagado. |

---

## 3. Como o processo funciona, do início ao fim

**Etapa 1 — Instalação.** Instala-se o equipamento e o roteador na fábrica, conectados à rede das câmeras. As
câmeras e o gravador já são do cliente.

**Etapa 2 — Aprendizado (shadow mode).** O sistema coleta imagens de situações reais da operação. **Nesta fase não
há alerta e não há garantia de detecção** — o sistema está aprendendo.

**Etapa 3 — Anotação.** Pessoas marcam manualmente, nas imagens coletadas, onde está cada item de interesse. É
trabalho humano e é a etapa mais demorada.

**Etapa 4 — Treinamento.** As imagens anotadas são processadas em servidores de GPU alugados de terceiro
(**RunPod**), produzindo o modelo. **As imagens do cliente saem da infraestrutura da Logikos nesta etapa.**

**Etapa 5 — Validação.** O modelo roda em paralelo à operação e compara-se o que ele viu com o que um humano viu.
Só depois de atingir qualidade aceitável ele é promovido.

**Etapa 6 — Operação.** O sistema analisa o vídeo 24h no equipamento local, gera eventos, aplica as regras por zona
e emite alertas. Evidências sobem para a nuvem.

**Etapa 7 — Melhoria contínua.** Erros identificados voltam para anotação e alimentam um novo treinamento.

> **Onde a RVB está hoje:** entre as etapas 2 e 3. **Ainda não existe modelo treinado.** É um fato que precisa
> estar refletido no contrato (seção 6.2).

---

## 4. Onde o dado fica, de quem é, e por quanto tempo

Esta seção é a base das cláusulas de LGPD.

### 4.1 O que é coletado

- **Imagens e vídeo de trabalhadores identificáveis**, no ambiente de trabalho. É **dado pessoal**.
- Metadados: data, hora, câmera, o que foi detectado.
- Dados de usuários da plataforma (nome, e-mail, perfil de acesso).

### 4.2 Onde fica

| Dado | Onde | Observação |
|---|---|---|
| Vídeo contínuo 24h | **NVR do cliente**, na fábrica | Nunca sai dali. Não é da Logikos. |
| Processamento em tempo real | **Equipamento na fábrica** | Transitório: a imagem é analisada e descartada. |
| Imagens de evidência e de treino | **Nuvem — Cloudflare R2** | ⚠️ **É aqui que a premissa inicial estava invertida.** |
| Eventos, alertas, configuração | **Nuvem — banco de dados (Railway)** | |
| Imagens durante o treinamento | **RunPod** (GPU de terceiro) | Passagem temporária, mas é saída de dado pessoal para terceiro. |

### 4.3 Pontos que precisam de decisão jurídica

1. **Transferência internacional.** Os provedores de nuvem são estrangeiros. Precisa-se determinar a região de
   armazenamento e o enquadramento na LGPD. *A Logikos consegue configurar a região — a assessoria diz qual.*
2. **Papéis LGPD.** A leitura mais provável: o cliente é **controlador** das imagens dos próprios empregados; a
   Logikos é **operadora**. Isso tem consequência direta na seção 7.
3. **Cadeia de suboperadores.** Railway, Cloudflare e RunPod precisam estar listados e autorizados no contrato.
4. **Base legal e informação aos trabalhadores.** Monitoramento por imagem em ambiente de trabalho tem exigências
   próprias. **A obrigação de informar os empregados e de tratar o tema com o sindicato/CIPA é do empregador**, não
   da Logikos — mas o contrato deve dizer isso com todas as letras.
5. **Retenção.** Hoje: evidências por 14 dias em acesso rápido, depois arquivamento. **Prazo comercial a definir.**
6. **Direitos do titular.** Se um trabalhador pedir acesso ou exclusão da própria imagem, o pedido chega ao
   empregador. O contrato precisa definir o prazo e a forma como a Logikos auxilia.

---

## 5. Divisão de responsabilidades

| Item | Logikos | Cliente |
|---|---|---|
| Equipamento de borda e roteador | Fornece (venda) e configura | Compra; fornece local, energia e tomada de rede |
| Câmeras e gravador | — | **Fornece, mantém e é dono** |
| Posicionamento e ângulo das câmeras | Orienta | **Executa e custeia** |
| Internet na fábrica | — | **Fornece e mantém** |
| Energia elétrica e proteção | — | **Fornece** |
| Software e atualizações | Fornece | — |
| Treinamento do modelo | Executa | Disponibiliza acesso e apoio operacional |
| Anotação das imagens | Executa *(a confirmar se há participação do cliente)* | — |
| Definição do que é violação, por zona | Configura | **Define o critério** (é conhecimento do cliente) |
| Ação diante de um alerta | — | **É do cliente. A Logikos não atua na operação.** |
| Fiscalização de segurança do trabalho | — | **É do empregador, por lei. Indelegável.** |
| Informar trabalhadores sobre o monitoramento | Apoia com informação técnica | **É do empregador** |

---

## 6. Os três riscos que precisam de cláusula específica

*Esta é a parte que vai além do dicionário.*

### 6.1 🔴 Responsabilidade por falso negativo — o ponto mais importante do contrato

O sistema **vai errar**. Nenhum sistema de visão computacional acerta 100%. Vai haver situações em que um
trabalhador circule sem o EPI exigido e o sistema não detecte.

**O risco:** ocorrendo acidente de trabalho, alguém pode alegar que a empresa confiou no sistema e que o sistema
falhou — tentando trazer a Logikos para a cadeia de responsabilidade de um acidente.

**O que o contrato precisa deixar inequívoco:**
- O Recognition é **ferramenta auxiliar de monitoramento**, e **não substitui** a fiscalização presencial, o
  trabalho da CIPA, o SESMT, nem qualquer obrigação de segurança do trabalho do empregador.
- As obrigações decorrentes das Normas Regulamentadoras **são do empregador e são indelegáveis**. Contratar o
  sistema não transfere nenhuma delas.
- O sistema **não garante detecção de 100% das ocorrências**, e essa limitação é inerente à tecnologia — não é
  defeito.
- O cliente declara ciência de que deve manter seus procedimentos de segurança **integralmente**, independentemente
  do sistema.
- Limitação de responsabilidade da Logikos, com teto, e exclusão expressa de responsabilidade por acidente de
  trabalho.

> Sem esta cláusula bem escrita, o contrato é inviável para uma empresa do porte da Logikos. É o item que eu
> pediria para a assessoria escrever primeiro.

### 6.2 🟠 Obrigação de desempenho num sistema que ainda não foi treinado

**Hoje não existe modelo treinado para a RVB.** O sistema está coletando imagens para aprender.

Um contrato "definitivo desde o início" com metas de desempenho válidas desde a assinatura colocaria a Logikos em
descumprimento no primeiro dia. É preciso, no mesmo contrato:

- descrever uma **fase de implantação e aprendizado**, com prazo, durante a qual **não há obrigação de detecção**;
- definir o **critério objetivo** que encerra essa fase e inicia a operação com obrigações (ex.: percentual mínimo
  de acerto medido em amostra, validado em conjunto);
- deixar claro que a duração dessa fase **depende de fatores do cliente** — posicionamento de câmera, volume de
  situações reais disponíveis para aprendizado, disponibilidade de pessoas para validar critérios.

### 6.3 🟠 Venda do equipamento × interrupção do serviço por inadimplência

O cliente **compra** o equipamento, mas o software é **licenciado**. Se o contrato de serviço terminar ou houver
inadimplência, o sistema para de funcionar — e o cliente fica com um equipamento que comprou e não pode usar.

Isso é contestável se o contrato não separar as coisas com clareza:
- A **venda** é do equipamento (bem físico). A propriedade é do cliente a partir da entrega.
- O **software embarcado** é licenciado, com prazo vinculado à vigência do contrato de serviço.
- O término da licença **cessa o funcionamento do software**, sem que isso configure defeito, vício ou apropriação
  do bem.
- Definir também: **garantia** do equipamento (prazo, o que cobre), quem substitui em caso de queima, e o que
  acontece com o equipamento no encerramento (fica com o cliente, inutilizado? há opção de recompra?).

---

## 7. ⚠️ Ponto de atenção sobre o uso das imagens do cliente

**Decisão informada:** uso das imagens da RVB para melhorar modelos de outros clientes, **sem restrição**.

Preciso registrar, com honestidade, que **esta é a decisão de maior risco entre as quatro**, por três motivos:

1. **LGPD.** Se a Logikos é *operadora* dos dados, ela não pode reaproveitá-los para finalidade própria — ao fazer
   isso, torna-se *controladora* daquele tratamento e precisa de base legal própria. Sobre imagem de trabalhador
   identificável, isso é difícil de sustentar sem consentimento, que em relação de emprego é frágil.
2. **Comercial.** É a cláusula que mais trava assinatura em cliente industrial. Um cliente maior que a RVB
   provavelmente recusará.
3. **Concorrencial.** Um cliente pode alegar que suas imagens ajudaram a construir a solução vendida ao concorrente
   dele.

**A alternativa que provavelmente entrega o que você quer, sem o risco:** você já escolheu que **a Logikos é dona
do modelo treinado**. Isso significa que o aprendizado acumulado **já é seu** — o modelo melhora e o ativo é da
Logikos. Não é preciso reivindicar uso irrestrito das *imagens* para obter esse benefício.

Um desenho mais defensável seria:
- **Imagens brutas:** permanecem do cliente, uso restrito à finalidade contratada;
- **Modelo, pesos e artefatos derivados:** de propriedade da Logikos, livremente reutilizáveis;
- **Dados agregados e estatísticos, sem identificação:** livres para a Logikos.

**Sugestão:** levar as duas opções à reunião do dia 6 e decidir com a assessoria, ouvindo o risco de cada uma.
A decisão é comercial e é sua — mas deve ser tomada sabendo que "sem restrição" provavelmente não sobrevive a uma
diligência de LGPD.

---

## 8. Escopo de câmeras — o que o sistema enxerga e o que ele processa

Durante a instalação verificamos que a rede de CFTV da RVB contém **mais equipamento do que o escopo
pretendido para esta contratação**. Essa diferença precisa estar escrita, porque **capacidade técnica de
acesso e autorização contratual são coisas distintas**.

| Situação | Equipamento |
|---|---|
| **Escopo contratado nesta data** | 8 câmeras, correspondentes aos **canais 1 a 8 do gravador Intelbras iNVD 3032** instalado na planta |
| **Fora do escopo nesta data** | 2 gravadores adicionais (modelo **iMHDX 3132**) e **~21 câmeras** a eles conectadas, existentes na mesma rede |

**O sistema Recognition não acessa, não transmite e não processa imagem de câmera que não esteja listada no
anexo de escopo.** A visibilidade técnica desses equipamentos na rede não implica autorização de uso.

**O que o contrato precisa prever:**

- **Anexo de escopo** listando câmera por câmera: canal, local de instalação e módulo contratado. É esse
  anexo, e não a capacidade do equipamento, que define o objeto.
- **Cláusula de ampliação por aditivo ou ordem de serviço simples.** Incluir uma câmera nova não deve exigir
  renegociação do contrato inteiro — a expectativa é de crescimento.
- Se o preço for **por câmera**, o anexo de escopo é também a **base de faturamento**, e sua atualização
  precisa ter forma e prazo definidos.
- **Compromisso expresso da Logikos de não acessar equipamento fora do anexo**, com a mesma força das demais
  obrigações de confidencialidade.

*A ampliação futura para os demais gravadores é desejada pela Logikos e deve ficar prevista como
possibilidade, mas não está contratada nesta data.*

---

## 9. Acesso da Logikos às imagens do cliente

O sistema permite que um administrador da Logikos **assuma o contexto de um cliente** e visualize as imagens
e os registros daquele cliente. É recurso necessário para suporte técnico e, sobretudo, para a fase de
treinamento dos modelos, em que a Logikos precisa examinar as imagens coletadas.

**Como esse acesso funciona, tecnicamente:**

- **Limitado no tempo** — a sessão expira automaticamente em 30 minutos
- **Identificado** — o registro guarda qual pessoa da Logikos acessou em nome de qual cliente
- **Sinalizado** — enquanto o acesso está ativo, a tela exibe aviso permanente
- **Auditado** — toda a atividade sob esse acesso fica registrada em log de auditoria

**O que o contrato precisa prever:**

- **Finalidade** — para que esse acesso pode ser usado, com vedação expressa de qualquer outra finalidade
- **Quem** — pessoas nomeadas ou cargos autorizados, e o procedimento no desligamento de um funcionário
- **Auditoria** — se o cliente pode solicitar o registro de acessos e em que prazo
- **Enquadramento LGPD** — é acesso do operador a dado pessoal do titular e deve constar do acordo de
  tratamento de dados

*Complementa "Acesso remoto" da seção 10: aquele trata do acesso à infraestrutura, este trata do acesso às
imagens.*

---

## 10. Outras cláusulas que a tecnologia exige

- **Acesso remoto.** Definir quem da Logikos acessa, com qual credencial, registro de acesso, e o que acontece no
  desligamento de um funcionário.
- **Segurança da informação e incidentes.** Prazo de comunicação de incidente e responsabilidades de cada parte.
- **Disponibilidade.** O sistema depende da internet do cliente, da energia e das câmeras dele. O indicador de
  disponibilidade deve **excluir** indisponibilidade causada por fatores do cliente.
- **Manutenção e atualização.** O software é atualizado remotamente. Janela, aviso prévio e direito de recusar.
- **Encerramento.** O que acontece com as imagens armazenadas, prazo de exportação para o cliente, prazo de
  exclusão definitiva, e comprovação da exclusão.
- **Confidencialidade.** Imagens de processo produtivo podem revelar segredo industrial — sobretudo no módulo de
  Qualidade, que filma a linha de produção.
- **Uso de imagem para demonstração comercial.** Se a Logikos quiser usar imagens ou resultados da RVB em
  apresentação de venda, precisa de autorização expressa. *(Vale checar: já há material de apresentação com
  conteúdo da RVB.)*
- **Suporte.** Canal, horário e prazo de resposta por severidade.

---

## ⚠️ 11. Visibilidade técnica × escopo contratual

*Complementa a seção 8 (anexo de escopo): aqui, o risco jurídico e as cláusulas decorrentes da visibilidade além do escopo.*

**Fato técnico descoberto em 2026-08-04:** a VLAN de câmeras contém dispositivos ONVIF além do escopo mapeado (iNVD 3032 com 8 câmeras confirmadas). A sondagem passiva por WS-Discovery identificou 2 gravadores adicionais (modelo iMHDX 3132) e aproximadamente 21 câmeras ONVIF não mapeadas, cuja titularidade ainda não foi confirmada com o cliente.

**Implicação para o contrato:**

O que o Recognition **consegue ver** (via descoberta ONVIF passiva) não é o mesmo que o que ele **está autorizado a processar** (conforme o contrato). Há três categorias de riscos jurídicos se essa distinção não ficar explícita:

1. **Segurança da informação:** se houver dispositivos na rede sem consentimento do cliente ou de propriedade de terceiros, uma cláusula que autorize "monitoramento de tudo o que está no subnet" transfere a Logikos a responsabilidade por dispositivos fora do escopo.

2. **Privacidade (LGPD):** imagens de áreas não autorizadas para monitoramento (ex.: escritório de terceiros, vestiário, refeitório) são dado pessoal tratado além da finalidade contratada.

3. **Operacional:** se o cliente autorizar apenas câmeras mapeadas (ex.: 8 do pátio, 12 da linha de produção), mas a configuração do Recognition tentar processar 40 câmeras, o sistema falha ou fornece alertas para áreas não contratadas.

**O contrato precisa deixar inequívoco:**

- **Escopo:** "O Recognition processa exclusivamente as câmeras mapeadas em anexo, conforme módulos: EPI (8 câmeras, modelo iNVD 3032, canais 1-8), Qualidade (...), Contagem (...)."
- **Descoberta:** "A Logikos realiza descoberta ONVIF na VLAN apenas para fins de onboarding e diagnóstico de conectividade. A existência de dispositivos ONVIF adicionais na rede não implica processamento ou coleta de dados deles."
- **Revalidação:** "Caso o cliente adicione novos dispositivos à rede, a Logikos comunicará a descoberta. O processamento deles requer autorização escrita prévia."

**Documentação:** os achados de descoberta de 2026-08-04 estão registrados em `docs/edge/ENDPOINTS_VLAN_NAO_CATALOGADOS.md`.

---

## 12. O que ainda precisa ser definido antes da reunião do dia 6

**Comercial (Vitor):**
1. Preço: setup, valor do equipamento, mensalidade — e se a mensalidade varia por câmera ou por módulo.
2. Prazo de vigência e condições de renovação/rescisão.
3. Quantidade contratada de câmeras e módulos — hoje há **8 câmeras disponíveis** no gravador; ver o anexo
   de escopo da seção 8 (**validar conforme descoberta de 2026-08-04**).
4. Prazo de retenção das evidências.
5. A decisão da seção 7 (uso das imagens).
6. O anexo de escopo de câmeras (seção 8), e se a ampliação para os demais gravadores fica prevista como
   possibilidade futura.
7. **Confirmar com a RVB** a titularidade dos 2 gravadores iMHDX 3132 e ~21 câmeras adicionais descobertas. Incluir no escopo se forem do cliente.

**Técnico (a Logikos confirma até a reunião):**
8. Região de armazenamento na nuvem — define se há transferência internacional.
9. Se a anotação será feita só pela Logikos ou com participação do cliente.
10. Critério objetivo que encerra a fase de aprendizado (seção 6.2).
11. **Revalidar teto de capacidade do Orin** considerando todas as câmeras a processar (revisão contra 8, conforme achado de 2026-08-04).

**Jurídico (assessoria):**
12. Redação da cláusula de limitação de responsabilidade e exclusão de responsabilidade trabalhista (6.1).
13. Enquadramento LGPD: papéis, base legal, transferência internacional, suboperadores.
14. Redação da cláusula de acesso da Logikos às imagens do cliente (seção 9): finalidade, pessoas
    autorizadas e direito de auditoria.
15. Separação entre venda de bem e licença de software, com o efeito da rescisão (6.3).
16. Tratamento fiscal: venda de equipamento e prestação de serviço têm regimes distintos.
17. **Cláusula de escopo:** exclusividade de câmeras mapeadas no contrato e procedimento para novas câmeras (seções 8 e 11, acima).

---

*Documento técnico preparado para subsidiar a elaboração contratual. Os fatos técnicos aqui descritos refletem o
estado real do sistema em 03/08/2026. Atualizado em 04/08/2026 com achados de descoberta de rede. A qualificação jurídica é da assessoria.*
