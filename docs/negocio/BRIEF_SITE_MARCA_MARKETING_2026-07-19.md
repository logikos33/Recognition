# Brief — Site, marca e plano de marketing

**Data:** 2026-07-19 · **Decisões tomadas:** Logikos como marca-mãe · Experiência gratuita = só o teste da câmera ·
Home em camadas (conformidade → personalização → custo)
**Destino:** insumo para montar o site no Claude Design, sobre o manual de marca existente.
**Benchmark analisado:** getter.ai · **Base de mercado:** `TAM_SAM_SOM_RECOGNITION_2026-07-19.md`

---

## 0. 🔴 CORREÇÕES URGENTES — antes de qualquer redesign

Estas quatro estão **no ar agora** e são erros de fato, não de estilo.

| # | O que está publicado | Problema | Ação |
|---|---|---|---|
| **C1** | *"YOLOv8 analisa cada frame a 5 FPS"* | **YOLOv8 é Ultralytics, licença AGPL.** O ADR-0043 proíbe AGPL no caminho servido, e a stack real hoje é YOLOX / RF-DETR / D-FINE (Apache). Estamos divulgando publicamente uma tecnologia que abandonamos por decisão jurídica | Remover a menção. Se citar stack, citar **"detectores de licença permissiva (Apache 2.0)"** — que aliás é argumento de venda |
| **C2** | *"DINO + SAM pré-anotam automaticamente, reduzindo 70% do tempo de anotação"* | O serviço de pré-anotação está com **flag OFF**. Prometemos um recurso que não está ativo | Remover ou mover para "em desenvolvimento" |
| **C3** | *"Mais de 12 câmeras simultâneas"* | Subestima. A campanha provou **28 em produção e 40 de teto** | Atualizar para 28–40, com a ressalva correta |
| **C4** | *"Recognition by CATH"* + e-mails e login em `epimonitor.com.br` | Três identidades no mesmo funil: Recognition, CATH, EPI Monitor — e a empresa é Logikos | Ver §1 |

**Inconsistências menores a arrumar:** latência aparece como `<3s`, `<200ms` e `<100ms` em pontos diferentes da
mesma página. Definir **uma** métrica pública e usar sempre a mesma (sugestão: latência de alerta ponta a ponta).

---

## 1. Arquitetura de marca

⚠️ **CORRIGIDO em 2026-07-20:** a Logikos **não é uma empresa de visão computacional**. É uma **integradora de
soluções industriais**. O Recognition é **uma linha** do portfólio, não o portfólio.

```
LOGIKOS · soluções para a indústria
   │
   ├── RECOGNITION — visão computacional (a linha mais madura, e a porta de entrada)
   │     ├── Recognition Safety     módulo EPI / segurança do trabalho
   │     ├── Recognition Quality    módulo inspeção visual
   │     └── Recognition Flow       módulo contagem, carga-descarga, pátio
   │
   ├── Sensorização e IIoT              sensor em máquina e processo, coleta e transmissão
   ├── Integração de sistemas           ERP, MES, PLC, SCADA e legados conversando
   ├── BI e analytics industrial        OEE, produtividade, qualidade, manutenção
   ├── Software sob medida              sistemas e portais para o processo do cliente
   ├── Agentes de IA e assistentes      assistente de operação, automação de tarefa repetitiva
   ├── Automação e retrofit             célula, robótica, modernização de máquina antiga
   ├── Infraestrutura e conectividade   rede industrial, servidor local, edge, segurança
   └── Consultoria e diagnóstico        maturidade digital, mapeamento, roadmap
```

**Consequência para o site:** a home **não pode** ser uma landing de visão computacional. Ela precisa apresentar
a Logikos como quem resolve o problema industrial, com o Recognition como a linha mais visível e madura. As três
camadas da §3 continuam válidas para a **landing do Recognition**, não para a home institucional.

*(Nomes dos módulos são proposta — o critério é que sejam substantivos de operação, não siglas técnicas.
"EPI Monitor" e "Quality Monitor" atuais são descritivos demais e não constroem marca.)*

**Por que essa arquitetura, e não a da GETTER:** eles têm cinco submarcas (Safety, Plus, Menthor, Level Up,
Copilot) e **nenhuma promessa central** — o visitante não sabe o que a GETTER é. Aqui a promessa central é a
**Logikos resolvendo o problema industrial**, e as linhas são caminhos para isso. Permite campanha segmentada
**sem diluir**, e ainda abre expansão de conta que a GETTER não tem.

**Vantagem competitiva que isso destrava:** entrar pelo Recognition (dor visível, urgência regulatória, ROI de
FAP) e **expandir para o resto do portfólio** dentro do mesmo cliente. A visão computacional é a ponta de lança;
o valor de vida do cliente está nas outras sete frentes.

### Migração necessária (não é cosmético)

| Item | Hoje | Alvo |
|---|---|---|
| Domínio institucional | — | `logikos.com.br` (ou equivalente) |
| Domínio do produto | `epimonitor.com.br` | `recognition.<dominio>` ou domínio próprio |
| Login | `app.epimonitor.com.br` | `app.<dominio-produto>` |
| E-mail de contato | `contato@epimonitor.com.br` | `contato@<dominio>` |
| Assinatura no site | "Recognition by CATH" | "Recognition · uma plataforma Logikos" |

⚠️ **Migrar com redirect 301** de tudo que já indexa, para não perder o pouco de SEO existente.

---

## 2. A fronteira da experiência gratuita

**Regra única, sem exceção:**

> A experiência gratuita é uma **demonstração de capacidade**, nunca um **acesso à plataforma**.

**Por quê, tecnicamente:** o produto exige Jetson instalado no site, modelo treinado com os dados do cliente e
configuração de cenário. **Self-service é arquitetonicamente impossível.** O CTA atual *"Começar gratuitamente"*
aponta para o app — quem clicar bate numa tela vazia e sai com a impressão de que o produto não funciona. É pior
que não ter CTA.

**O que fica:** o **teste da câmera no celular**. Ele responde, em 30 segundos, à única dúvida que o visitante
tem naquele momento — *"essa IA enxerga mesmo?"*. É prova, não amostra grátis.

**O que sai do site inteiro:**
- ❌ "Começar gratuitamente"
- ❌ "Teste grátis" / "Free trial" / "Experimente sem custo"
- ❌ Qualquer link direto para o app fora do botão **Entrar** (que é para cliente existente)
- ❌ Qualquer construção que sugira autoatendimento

**O que entra no lugar (hierarquia de CTA):**

| Prioridade | CTA | Onde |
|---|---|---|
| **Primário** | **Testar a câmera agora** | Hero e recorrente. É a prova |
| **Secundário** | **Falar com um especialista** | Fim de cada dobra e de cada página de módulo |
| **Terciário** | **Receber o diagnóstico da minha operação** | Guardado para fase 2 — ver §5 |
| Utilitário | **Entrar** | Topo, discreto. Cliente existente |

**Validação do benchmark:** a GETTER é maior e **não tem nenhum self-service**. Todo CTA deles é
*"Saiba mais"* → formulário → conversa. Com implantação de R$ 20 mil e modelo treinado por cliente, isso não é
PLG — é **venda consultiva**. O site existe para gerar **conversa qualificada**, não conversão automática.

---

## 3. Estrutura da home — as três camadas

Cada dobra fecha um argumento e passa o bastão para a próxima. Se a ordem inverter, vira catálogo de recursos.

### Dobra 1 — CONFORMIDADE · *por que agir agora*
**Trabalho:** criar urgência legítima, com data.

- **Headline** ancorada na obrigação, não na tecnologia. A NR-6 já obriga o empregador a *"exigir o uso"* e
  *"fiscalizar a utilização correta"* do EPI — hoje isso é cumprido com ronda humana e assinatura em papel.
- **Sub:** a fiscalização punitiva plena da NR-1 começou em **26/05/2026**; a Portaria MTE 104/2026 instituiu
  **reajuste anual automático** das multas da NR-28.
- **CTA primário:** Testar a câmera agora · **secundário:** Falar com especialista
- **Prova ao lado:** o teste de câmera ao vivo (já existe e funciona)

> **Ângulo que nenhum concorrente ocupa:** *não criamos uma categoria — automatizamos uma obrigação legal
> que hoje é mal cumprida.*

### Dobra 2 — PERSONALIZAÇÃO · *por que nós*
**Trabalho:** separar de GETTER, Pix Force e Quickium.

- **Tese:** cada cliente **treina o próprio modelo**. Não é um detector pronto adaptado — é um modelo que
  aprende a operação, os EPIs, os defeitos e as zonas daquele cliente.
- Mostrar o **fluxo real**: câmeras existentes → edge no site → anotação e treino com os dados do cliente →
  modelo próprio → alertas e evidência.
- **Contraste explícito com o mercado:** produtos prontos entregam o que foi treinado na fábrica deles.
- Aqui entra a credencial de licença: **detectores Apache 2.0**, sem dependência AGPL — argumento real para
  comprador técnico e jurídico, e diferencial que nenhum concorrente comunica.

### Dobra 3 — CUSTO E RISCO · *por que é seguro começar*
**Trabalho:** derrubar a objeção de investimento.

- **Usa as câmeras que você já tem.** Zero hardware de captura novo.
- **Roda no local (edge).** As imagens não precisam sair da planta — argumento forte sob **LGPD**, e a mesma
  tese pela qual a Protex AI levantou US$ 36 milhões.
- **Implantação em dias**, não meses.
- **O bloco do FAP** — ver §4. É o que transforma "custo" em "investimento com retorno auditável".

### Dobras de apoio (abaixo das três)
- **Módulos** — três cards, cada um linkando para sua landing própria
- **Setores** — construção, metalurgia, alimentos, têxtil, logística (SC é têxtil e metalmecânica pesada)
- **Prova social** — ⚠️ hoje é o maior buraco versus a GETTER. Ver §6
- **CTA final** — conversa, nunca autoatendimento

---

## 4. O bloco do FAP — o argumento que ninguém usa

Deve existir como **seção própria** na home e como página dedicada.

**A mecânica:** o RAT é 1%, 2% ou 3% da folha conforme o risco da atividade. O **FAP** multiplica isso por um
fator de **0,5 a 2,0**, conforme o desempenho acidentário da empresa versus a média do setor. A alíquota efetiva
varia de **0,5% a 6% da folha** — amplitude de **12×**.

**O exemplo que vai no site** (indústria de 300 funcionários, folha média R$ 3.000, risco grave):

| | Alíquota efetiva | Custo anual |
|---|---|---|
| FAP 2,0 — pior que a média | 6,0% | R$ 648.000 |
| FAP 0,5 — melhor que a média | 1,5% | R$ 162.000 |
| **Diferença** | | **R$ 486.000 / ano** |

**Por que funciona:** é **auditável** (o INSS publica no DOU, verificável no eSocial — não é promessa de
fornecedor), sai do **orçamento de tributos e não do de TI** (muda o interlocutor de gerente de TI para CFO), e
**nenhum concorrente pesquisado ancora a proposta de valor nisso**.

⚠️ **Cuidado de redação:** nunca prometer redução de FAP. A formulação correta é que o sistema **gera a evidência
e o dado** que sustentam a gestão do indicador. Prometer resultado tributário é exposição desnecessária.

---

## 5. Diagnóstico — a isca de fase 2

Descartado do lançamento por decisão de escopo, mas mapeado aqui porque é o próximo passo natural:

Questionário curto (nº de câmeras, setor, nº de funcionários, RAT) que devolve um **diagnóstico personalizado**:
módulos recomendados, estimativa de cobertura e a **faixa de exposição de FAP** da empresa. Captura um lead
muito mais qualificado que um formulário genérico, e alimenta a conversa comercial com dado.

Entra depois que o site base estiver no ar e convertendo.

---

## 6. Plano de marketing

### Contexto que define tudo
SOM definido no dossiê de mercado: **Vale do Itajaí / Santa Catarina** — ~1.290 indústrias endereçáveis no Vale,
~3.000 em SC. Meta base: **40 clientes em 3 anos**. Isso é **densidade geográfica**, não alcance de massa.
**Marketing aqui é geração de conversa qualificada em um território pequeno e conhecido** — não funil de volume.

### Canais, por prioridade

| # | Canal | Por quê | Custo |
|---|---|---|---|
| **1** | **Relacionamento institucional** — FIESC, ACIB, sindicatos patronais, associações setoriais | O Vale é território de relacionamento. A FIESC é o hub natural da indústria catarinense e já é fonte dos nossos dados | Baixo · alto retorno |
| **2** | **LinkedIn orgânico segmentado** — gerentes de SST, engenheiros de segurança, diretores industriais em SC | O comprador está lá e o território é pequeno o bastante para abordagem nominal | Baixo |
| **3** | **Conteúdo de conformidade (SEO)** — NR-1, NR-6, NR-12, FAP, PGR, evidência de conformidade | Intenção de busca real e recorrente. A GETTER tem blog **parado em 2023** — a janela está aberta | Médio · composto |
| **4** | **Eventos e feiras regionais** — Mercopar, feiras setoriais de SC, eventos FIESC | A GETTER investe pesado nisso e funciona. Venda consultiva se faz presencialmente | Médio |
| **5** | **Case RVB** — estudo de caso com números reais, assim que houver operação | Prova social é o nosso maior buraco. Um case local vale mais que dez logos genéricos | Baixo · **alta prioridade** |
| **6** | **Outbound direcionado** — lista construída a partir do universo mapeado (indústrias 50+ func. no Vale) | O universo é finito e conhecido: ~1.290 empresas. Dá para trabalhar nominalmente | Médio |

**O que NÃO fazer:** mídia paga de alcance amplo, Instagram de volume, qualquer coisa que otimize impressão.
O público é pequeno, identificável e compra por confiança.

### Prova social — o buraco a fechar

A GETTER tem duas paredes de logos (clientes e parceiros), Prêmio Finep 2025, WebSummit, SBT e operação em
Portugal. **Nós temos zero disso no site.** Ordem de ataque:

1. **Case RVB com números** — assim que a operação estabilizar. É o ativo mais valioso.
2. **Autorização de uso de marca** do cliente âncora.
3. **Prêmios e editais** — a Quickium ganhou o ABDI/Finep/Nestlé; existem editais setoriais e de inovação
   acessíveis. Vale mapear calendário.
4. **Selo de licença** — "detectores Apache 2.0, sem dependência AGPL" é credencial técnica verificável que
   **nenhum concorrente exibe**.

---

## 7. O que levar para o Claude Design

**Já existe:** manual de marca.

**Definido neste brief:** arquitetura de marca · hierarquia de CTA · estrutura da home em três camadas ·
conteúdo do bloco de FAP · lista de correções urgentes.

**A produzir no Claude Design:**

| Página | Prioridade |
|---|---|
| **Home** — três camadas + módulos + setores + prova + CTA de conversa | P0 |
| **Recognition Safety** — landing do módulo EPI, ancorada em NR-6 e FAP | P0 |
| **Recognition Quality** — landing do módulo de inspeção | P1 |
| **Recognition Flow** — landing de contagem e pátio | P1 |
| **Como funciona** — o fluxo técnico, edge, LGPD, licença Apache | P1 |
| **Quem somos (Logikos)** — institucional | P2 |
| **Conteúdo / blog** — base de SEO de conformidade | P2 |

**Antes da primeira tela:** aplicar as correções **C1–C4** da §0. Não faz sentido redesenhar uma página que
divulga uma stack AGPL que abandonamos.
