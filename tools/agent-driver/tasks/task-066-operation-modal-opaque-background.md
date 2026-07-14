# Task 066 — Fix visual: modal "Nova Operação" sem fundo opaco (vídeo vaza atrás, texto ilegível)

**Status**: DONE (com ressalva) — confirmado na auditoria da task-078 (2026-07-14) que
`components/training/modals/OperationCreateModal.tsx`, `OperationEditModal.tsx` e
`DeleteConfirmModal.tsx` já usam `ui/Modal`. **Porém** a task-078 descobriu um bug sistêmico de
Portal + escopo de tema em `ui/Modal`/`AppDrawer`/`Popover` (a classe de tema do
`AppShell` não alcança `document.body`, onde o Radix `Dialog.Portal` renderiza) — todo `ui/Modal`,
incluindo estes, pode renderizar com fundo transparente na prática. Ver
`docs/quality/UX_FUNCTIONAL_BACKLOG.md` § task-078 "ACHADO PRINCIPAL". Recomenda-se validar
visualmente este modal depois que o bug de Portal for corrigido, antes de considerar 100% fechado.
**Risk**: P1-ALTO (bloqueia o fluxo de criar operação/cenário)
**Branch**: fix/task-066-operation-modal-opaque-background

> **Decisão (2026-07-07):** NÃO tratar isolada. É um caso da classe "modais/containers transparentes"
> que a **auditoria visual** vai mapear por completo. Atacar como uma das **primeiras ondas do restyle
> pós-auditoria**, usando o componente Modal consolidado + tokens + lente SLC (evita fix one-off e
> retrabalho). Exceção: só fazer um fix tático mínimo AGORA se o fluxo "Nova Operação" for necessário
> antes da auditoria concluir.

## Contexto (reportado em uso real — 2026-07-06, dev com fix da 063 já live)

O modal **"Nova Operação"** (wizard Tipo → Configuração → Revisão; opções: Contagem estática,
Sobreposição dinâmica/área fixa, Posição, Linha de contagem) renderiza **sobre o vídeo ao vivo SEM
fundo opaco** → a imagem da câmera vaza atrás e o texto escuro fica **ilegível**. É defeito DIFERENTE
da task-063 (que era cor hardcoded): aqui é **container/modal transparente + backdrop ausente**, então
o guard-rail da 065 não pega.

## Escopo

- Modal "Nova Operação" (criação de operação/cenário — ligado a task-023/024 scenario editor).
- **Auditar os demais modais/drawers do fluxo de Operação** (Configuração, Revisão, e qualquer outro
  que abra sobre o vídeo) — provável mesmo defeito.

## Fix

- **Fundo opaco** no card do modal (token do design system — bgCard/bgSurface), não transparente.
- **Backdrop** atrás do modal escurecendo/desfocando o vídeo (overlay dim) pra separar o conteúdo do
  feed ao vivo.
- Contraste texto/fundo WCAG AA; hover nos itens selecionáveis (as opções de tipo).
- Usar o **padrão de Container/Modal com tema (WS1 / ADR-0023)** — reaproveitar, não recriar.

## Aceite

- Modal "Nova Operação" **legível** sobre qualquer câmera (vídeo não vaza pelo conteúdo); backdrop
  escurece o feed atrás.
- Todas as opções de tipo legíveis, com hover; botão "Próximo: Configurar" visível.
- Demais modais do fluxo de Operação auditados e corrigidos se tiverem o mesmo defeito.
- Contraste AA; sem regressão; tsc limpo. Screenshot antes/depois. PR develop. Gate humano pra staging.

## Referências

- task-063 (fix visual anterior), task-023/024 (scenario editor/write), ADR-0023 (container/modal
  pattern), WS1 em `docs/quality/UX_FUNCTIONAL_BACKLOG.md`
