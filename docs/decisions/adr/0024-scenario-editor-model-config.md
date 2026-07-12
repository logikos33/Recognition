# ADR-0024 — Scenario Editor Reuse for Model Configuration

## Status: Accepted (2026-07-01)

## Contexto

O produto possui dois fluxos distintos que envolvem desenho sobre imagens de câmera:

1. **Scenario Editor** (existente): `DrawingCanvas` + `ScenarioEditor` + `RoiDrawer` em
   `components/scenario/` e `components/training/canvas/`. Usado para definir cenários
   de monitoramento (ROIs, linhas de cruzamento, zonas de exclusão).

2. **Configuração de modelo por câmera** (novo): ao associar um modelo treinado a uma
   câmera, o operador precisa definir linha de cruzamento, ROI de inferência, classes
   ativas e limiar de confiança por classe.

A tentação era criar um novo componente `ModelConfigCanvas` espelhando o Scenario Editor.
Isso geraria duplicação de lógica de:
- Desenho de polígono/linha sobre frame
- Coordenadas normalizadas (0..1) × resolução de câmera
- Serialização/deserialização de geometrias para o backend
- Gestão de estado multi-etapa (desenhar → confirmar → avançar)

## Decisão

Reutilizar `DrawingCanvas`, `ScenarioEditor` e `RoiDrawer` integralmente no fluxo
de configuração de modelo. Nenhuma duplicação de componente de canvas é permitida.

### Como compor

O fluxo de configuração de modelo é implementado como wizard dentro do `<Drawer>`
(ADR-0023), com etapas:

```
Etapa 1: Selecionar modelo treinado
Etapa 2: Definir ROI de inferência     → <RoiDrawer camera_id={id} mode="roi" />
Etapa 3: Definir linha de cruzamento   → <RoiDrawer camera_id={id} mode="line" />
Etapa 4: Selecionar classes ativas     → <ClassSelector model_id={id} />
Etapa 5: Definir limiares por classe   → <ThresholdSliders classes={selected} />
Etapa 6: Confirmar e salvar
```

`RoiDrawer` recebe `mode` prop para alternar entre polígono ROI e linha de cruzamento.
`DrawingCanvas` permanece agnóstico ao modo — apenas entrega coordenadas.

### O que NÃO duplicar

- Lógica de normalização de coordenadas (`toNormalizedCoords`, `fromNormalizedCoords`)
- Captura de frame via `GET /api/cameras/{id}/snapshot`
- Validação de geometria (polígono fechado, linha com exatamente 2 pontos)
- Estado de undo/redo do canvas

### Extensões permitidas

`RoiDrawer` pode receber `initialGeometry` prop para pré-carregar geometria salva
(edição de configuração existente). Isso é adição, não duplicação.

### Localização dos componentes

```
components/scenario/
├── DrawingCanvas.tsx       # primitivo de canvas — NÃO modificar interface
├── ScenarioEditor.tsx      # orquestra DrawingCanvas + controles
└── RoiDrawer.tsx           # drawer de ROI/linha — estender com props novas

components/training/canvas/
└── RoiDrawer.tsx           # alias ou re-export — unificar em sprint de limpeza
```

Débito: dois `RoiDrawer` coexistem em `components/scenario/` e
`components/training/canvas/`. Unificar em sprint futura (P3).

## Consequências

- Zero duplicação de lógica de canvas no produto.
- Consistência de UX: operador usa a mesma ferramenta de desenho em cenários e em
  configuração de modelo — curva de aprendizado única.
- `DrawingCanvas` se torna componente crítico: mudanças de interface quebram dois fluxos.
  Exige testes de regressão antes de qualquer alteração de props.
- Etapas 4 e 5 (`ClassSelector`, `ThresholdSliders`) são componentes novos — não têm
  equivalente no Scenario Editor e devem ser criados sem duplicar canvas.
