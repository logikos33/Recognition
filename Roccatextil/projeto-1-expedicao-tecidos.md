# Projeto 1 — Expedição e Recebimento de Rolos de Tecido (Roccabela)

**Documento de descoberta** · Atualizado em 11/06/2026 · **PRIORIDADE: este projeto vem primeiro**

> **Produto-base:** Recognition Carga & Descarga (evolução do módulo `fueling`) — ver `CARGA_DESCARGA.md`. Multi-tenant, configurável pelo front, caminho whitelabel. A Roccabela é o cliente âncora do produto.

---

## 1. Visão geral

Visão computacional para carga e descarga de **rolos de tecido** na RoccaTextil:

- **6 baias de expedição** — entrega dos produtos da RoccaTextil para os clientes
- **3 baias de recebimento** — chegada de produto (abastecimento)

## 2. Etapas do projeto

### Etapa 1 — Expedição (escopo inicial)

**2 câmeras por baia** (12 câmeras no total para as 6 baias de expedição):

| Câmera | Função |
|---|---|
| Câmera A | Capta os produtos **disponíveis para carregamento** na baia |
| Câmera B | Capta o que **foi carregado no caminhão** |

**Objetivo — contagem nos dois cenários:**
- Quanto foi carregado e **para quem** (vínculo com cliente/pedido)
- Quanto resta **disponível para os próximos carregamentos**

### Etapa 2 — Recebimento/abastecimento (a definir depois)

- Desafio central: os rolos de tecido chegam com **notas difíceis de ler** (OCR complexo)
- Solução ainda em aberto — pensar abordagem após a Etapa 1

## 3. Ativos existentes (reuso)

- **Recognition já existe** — reaproveitar código
- **Módulo de carregamento já existente** — usar como base

## 4. Definições já feitas

| Tema | Definição |
|---|---|
| Recognition existente | Detecção + contagem de objetos, stack Python/YOLO (treinável para rolos) |
| Contagem dos rolos | **Por tipo/SKU** — diferenciar visualmente o tipo de tecido/embalagem, além de contar |
| Vínculo com pedido | **MVP: operador informa o pedido na tela.** Hoje o cliente chega com um "papelzinho" do pedido — o sistema substitui isso digitalmente; integração/automação fica para depois |
| Câmeras das baias | Instalar do zero (12 câmeras: 2 por baia × 6 baias de expedição) |

## 5. Perguntas em aberto

### Sobre os rolos e a contagem
- Quantos tipos/SKUs distintos visualmente? Diferença é cor, estampa, largura, embalagem?
- ~~Rolos paletizados?~~ → **Respondido:** pode ocorrer paletização, mas com padrão visual padronizado e treinável — modelo trata rolo avulso e palete-padrão como classes distintas
- Quantos tipos de palete-padrão existem e quantos rolos cada um carrega? → **Sem informação no momento — detalhar APÓS a negociação.** Na proposta, tratar como premissa: "paletização com padrão visual a ser mapeado na implantação"
- Há dataset de imagens dos rolos para treinar, ou começamos a coletar na instalação?

### Sobre infraestrutura
- Energia/rede disponíveis nas baias? Servidor local ou nuvem?
- Iluminação das baias e do interior do caminhão (fundo do baú é escuro — pode exigir iluminação dedicada)

### Sobre o resultado
- Divergência entre o pedido informado e o carregado gera alerta em tempo real ou relatório?
- Quem consome a informação (conferente, expedição, faturamento)?
- O módulo de carregamento existente cobre qual fluxo? O que falta para o cenário das baias?

## 6. Esboço da solução (Etapa 1) — alinhado ao produto Carga & Descarga

**Conceito central: SESSÃO de carga/descarga** — a unidade de tudo: baia + caminhão (placa) + direção (carga|descarga) + total de rolos + início/fim + clipe de vídeo. Abre quando o caminhão atraca, acumula contagem, fecha quando sai. Campos `esperado`/`divergencia` já existem no modelo, nulos na Fase 1 (plug da conferência futura).

**Fluxo por baia:**
1. Caminhão atraca → sessão abre (placa + horário)
2. Câmera A conta os rolos disponíveis na baia
3. Câmera B conta por **cruzamento de linha virtual** na doca (counting_line + DeepSORT + voto multi-amostra; in=descarga / out=carga) — não filma o interior do caminhão
4. Sessão fecha ao sair → registro com total, duração, vídeo e evidência; saldo atualizado
5. Dashboard: tempo por sessão/baia, ociosidade, throughput, por turno/caminhão, export

**Dores declaradas pela Roccabela:** lentidão da doca, erro de contagem, erro de expedição. O MVP ataca as três: contar + auditar + dashboard. **Conferência contra o esperado (romaneio/NF/ERP) = Fase 2** — onde o valor explode (anti-furto, anti-disputa), com OCR do romaneio reusando o PaddleOCR do módulo Qualidade.

**Reuso (quase nada do zero):** counting_line + DeepSORT (038), motor de operations/cenários (023), modelo por câmera (045) + tuning (039), frames/R2 para evidência, relatórios (043), alert_rules (042), multi-tenant existente.

**Trabalho novo principal:** migration `loading_sessions` + ingest real (substitui o mock atual), operation-type de contagem de rolo, dashboard real, config de baia pelo front, **dataset/treino do modelo de rolo (único item de trilha humana — risco principal, coletar vídeo da doca real CEDO)**.

**Argumentos de venda validados por mercado (pesquisa 2026):** −25-35% erro de carregamento, −30-50% furto/quebra, +~20% dock-to-stock, ROI 200-350% em 12-18 meses; Gartner: até 2027, 50% dos armazéns trocam conferência manual por visão.

## 7. Riscos preliminares

- ~~Oclusão no carregamento~~ → **Resolvido por desenho:** contagem por cruzamento de zona virtual na porta da doca, sem depender de visão do interior do baú
- **Dupla contagem / rolos parcialmente visíveis** na área de disponíveis
- **Classificação por SKU:** se tecidos de SKUs diferentes forem visualmente quase idênticos (mesma cor/embalagem), a câmera não distingue — validar com amostras reais antes de prometer granularidade por SKU
- **Dependência do operador no MVP:** se ele informar o pedido errado, a conciliação fica errada — mitigar com confirmação simples na tela
- **Etapa 2 (notas ilegíveis):** OCR de documentos danificados/manuscritos é problema distinto de visão de objetos — tratar como subprojeto próprio
