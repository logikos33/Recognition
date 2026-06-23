# Plataforma de Cenários Configuráveis (multi-módulo)

> **Status:** norte de produto + arquitetura · **Data:** 2026-06-04
> **Companion:** `EDGE_DEPLOYMENT_PLAN.md`, ADR-0007 (deployment modes), ADR-0015 (multi-backend inference),
> `docs/architecture/HARNESS_PLANO_IMPLEMENTACAO.md`.
> **Objetivo:** transformar a configuração de detecção em uma experiência de **edição visual por câmera** —
> o operador escolhe o cenário (o que a câmera deve "olhar") e o sistema aplica o módulo, a região de
> interesse, as classes e as regras certas. Um único motor; N cenários; multi-tenant.

---

## 1. O conceito de "Cenário"

Um **Cenário** é a configuração de detecção de **uma câmera**: o que detectar, onde na imagem, e o que fazer
com o resultado. Ele **não é uma tabela nova** — é a composição de coisas que o sistema já modela:

| Peça do cenário | Onde já vive no código |
|---|---|
| Câmera (+ site) | `public.cameras` (com `site_id`) |
| Módulo + classes | `module_code`, `tenant_modules`, `module_classes` |
| Operação (ROI/linha/zona + parâmetros) | `operations` (`type_id` + `config` JSONB, com `op_class.validate_config` + hot-reload via Redis) |
| Regra de alerta | `alert_rules` |
| Agenda (quando ativo) | `camera_modules_schedule` |

Ou seja: o **`operations`** já é um motor de "operações configuráveis por câmera/módulo". O Cenário é a
**camada que amarra essas peças como uma unidade** que o front edita visualmente e versiona.

---

## 2. Operation-types por módulo (o catálogo)

O framework de operação (`op_class` + `validate_config`) existe; falta o **catálogo de tipos concretos**,
um por necessidade. As 3 frentes da RVB viram 3 tipos no mesmo motor:

| Módulo | Operation-type | `config` (JSONB) | Saída |
|---|---|---|---|
| **EPI** | `epi_zone` | zona/ROI + classes a vigiar (ex: `no_helmet`, `no_vest`) | alerta quando classe "sem" presente na zona |
| **Qualidade** | `defect_trigger` | ROI da esteira + gatilho + classes de defeito | inspeção + OCR de peça + contagem única (DeepSORT) |
| **Estacionamento** | `counting_line` | geometria da **linha** + direção + classe (`person`) | contagem de cruzamentos (DeepSORT track único) |

Cada tipo é uma classe registrada com seu schema de `config`, validação e renderizador no front (qual
ferramenta de desenho usar: polígono/zona, linha, ponto).

---

## 3. Edição visual no front (o que muda no frontend)

A "mágica" do produto é **desenhar o cenário sobre a imagem da câmera**. Isso é trabalho de frontend e deve
ser feito com boas práticas e **testado de verdade** (hoje a única verificação de front é `tsc`).

### 3.1 Stack e padrões (alinhado ao que já existe)
- React 18 + TypeScript (strict) + Vite; estado com Zustand; UI com Radix; streaming com HLS.js.
- **Overlay de desenho** (canvas/SVG) sobre um frame da câmera (still/HLS snapshot): ferramentas **zona
  (polígono)**, **linha** e **ponto**, escolhidas pelo operation-type.
- Componentes pequenos e isolados; sem estado global desnecessário; sem `any` implícito.
- **Acessibilidade:** foco/teclado nas ferramentas de desenho, labels ARIA, contraste — não só mouse.
- **Sem segredo no front**; toda escrita de cenário passa pela API (tenant do JWT).

### 3.2 Testes (pré-requisito — o front precisa virar testável)
- **Vitest + React Testing Library** para componentes (render, interação, estados de erro/loading).
- **Playwright** para e2e do editor (desenhar uma linha/zona, salvar, recarregar e ver persistido).
- Job de CI de frontend (lint + tsc + Vitest + Playwright headless) — vira parte da eval.
- **Validação de UX:** após implementar, rodar o editor, **tirar screenshot, revisar e anotar melhorias**
  (ergonomia do desenho, undo/redo, snap, feedback de salvamento) antes de considerar concluído.

### 3.3 Fluxo do operador (alvo)
1. Escolhe a câmera → vê um frame ao vivo/recente.
2. Escolhe o módulo (EPI / Qualidade / Contagem) → o editor mostra as ferramentas e classes do tipo.
3. Desenha a ROI/linha/zona sobre a imagem.
4. Define classes + regra de alerta + agenda.
5. Salva → o cenário é versionado e (no edge) aplicado por hot-reload, sem reiniciar a operação.

---

## 4. Estratégia de modelos multi-módulo (embutida)

Cada par **(tenant × módulo)** tem sua linhagem de modelo; a eval é **diferente por módulo**:
- **EPI** → recall por classe de EPI (falso-negativo de "sem capacete" é crítico).
- **Qualidade** → recall de defeito + falso-positivo + acurácia do OCR de peça (modelo custom do produto do cliente).
- **Estacionamento** → acurácia de contagem na linha (detector de **pessoa** é base off-the-shelf, treino ≈ zero).

**Reuso entre clientes:** EPI base e detector de pessoa são reaproveitáveis; Qualidade é custom por cliente.
O pipeline de treino/versionamento (`training`, `dataset`, `models`, `dataset_version → model_id`) já existe.

---

## 5. As 3 frentes da RVB = os 3 primeiros cenários (juntas no go-live)

A RVB precisa das **três no ar juntas**. No motor de cenários, são 3 instâncias:
- EPI: `epi_zone` nas câmeras de produção.
- Qualidade: `defect_trigger` nas câmeras da esteira.
- Estacionamento: `counting_line` nas câmeras do pátio.

Todas no mesmo DeepStream multi-pipeline do edge (Fase 5), lendo a `config` do cenário por câmera.

---

## 6. Onboarding de cliente novo = configuração, não código

Com a plataforma de cenários, um cliente novo é: cria o tenant → habilita módulos → para cada câmera,
**desenha o cenário** (módulo + ROI/linha + classes + regra). Reusa modelos base onde dá; treina custom só
onde precisa. **Sem reescrever código** — frentes distintas viram configuração + (quando necessário) treino.

---

## 7. Sequência de implementação (decomposta pra fila)

1. **Harness de teste de frontend** (Vitest + RTL + Playwright + job de CI) — torna o front testável. *Pré-requisito.*
2. **API de Cenário (leitura) + catálogo de operation-types** — serializa o cenário sobre o que existe; lista
   os tipos por módulo. Software, tabelas existentes.
3. **Editor visual de cenário (frontend)** — desenhar ROI/linha/zona + escolher módulo/classes/regra + salvar.
4. **Escrita de cenário + os 3 operation-types** (epi_zone, defect_trigger, counting_line) — escreve `operations`
   com `config` validado; classe security (configura detecção).
5. **Edge aplica o cenário** (DeepStream lê a `config` por câmera) — Fase 5, hardware.

> Migrations: o Cenário é wrapper sobre tabelas existentes; se for preciso um campo de versão/nome de cenário,
> entra como migration aditiva pelo fluxo com checkpoint (não autônomo).

---

## 8. Riscos / decisões em aberto
- **Editor visual no caminho crítico do go-live?** Se apertar, o go-live pode configurar o cenário "no nervo"
  (API/seed) e o editor visual entra logo depois — a definir.
- **Frontend autônomo** só é seguro depois do harness de teste (item 1); sem ele, a eval do front é fraca.
- **Performance do edge** com 3 pipelines + ROIs por câmera na mesma GPU (RTX) — validar na Fase 5.
