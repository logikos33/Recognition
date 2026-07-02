# ADR-0023 — Container Modal Pattern

## Status: Accepted (2026-07-01)

## Contexto

A reforma visual do produto (MUTIRÃO FINAL) introduziu múltiplos fluxos de criação
e edição que precisam coexistir com o contexto já aberto na tela:

- Criar câmera sem perder a grade de câmeras visível ao fundo
- Editar regra de alerta sem sair do histórico de alertas
- Configurar modelo sem fechar a página de câmeras
- Navegar entre etapas de um wizard (ex.: criar câmera → configurar stream → configurar ROI)
  sem gerar "pilha de páginas" na rota

Abordagens avaliadas:

| Abordagem | Vantagem | Desvantagem |
|-----------|----------|-------------|
| Página separada (`/cameras/new`) | URL compartilhável | Perde contexto, navegação dupla |
| Inline expansion | Sem sobreposição | Desloca layout, quebra scroll |
| Modal simples | Foca atenção | Difícil de compor com wizard multi-etapa |
| **Container modal/drawer deslizante** | Mantém contexto, compõe etapas | Implementação mais cuidadosa |

## Decisão

Adotar um padrão único de **container sobrepositor** para todas as UIs de criação,
edição e configuração do produto. O container pode se materializar como:

- **Modal centralizado**: para ações de confirmação, detalhes simples (≤ 3 campos)
- **Drawer lateral deslizante** (painel direito, 480px): para formulários médios e wizards
- **Sheet/bottom sheet** (mobile): variante responsiva do drawer

### Regras do padrão

1. **Abre sobre o contexto**: o conteúdo atrás permanece visível (overlay semitransparente),
   sem redirecionar para nova rota.
2. **Não interrompe processos em segundo plano**: streams HLS, polling de alertas e
   WebSocket continuam ativos enquanto o container está aberto.
3. **Fecha voltando ao lugar**: fechar o container retorna foco exatamente para o elemento
   que o abriu (câmera, regra, modelo), não para o topo da página.
4. **Composição de etapas**: wizard multi-etapa é implementado como estado interno do
   container (step 1 → 2 → 3), não como stack de modais.
5. **URL opcional**: para fluxos compartilháveis (ex.: link direto para edição de câmera),
   o container pode ser ativado por query param (`?modal=camera&id=X`), mas não é
   obrigatório.

### Componente base

`components/shared/ContainerModal.tsx` exporta:
- `<Modal>` — centralizado, foco em confirmações
- `<Drawer>` — lateral, foco em formulários e wizards
- `useContainerModal()` — hook para abrir/fechar programaticamente

Todos os componentes de criação/edição herdam desses primitivos.
Proibido criar modais ad-hoc com `dialog` ou `fixed` CSS fora desse componente.

## Consequências

- Consistência visual garantida: todas as sobreposições usam o mesmo sistema de z-index,
  animação de entrada/saída e gestão de foco (a11y).
- Redução de rotas: fluxos de criação/edição não geram rotas dedicadas, simplificando
  `AppRoutes.tsx`.
- Composição de wizard sem "modal hell" (empilhamento de modais sobre modais).
- Custo: ContainerModal precisa de testes de acessibilidade (foco trap, `aria-modal`,
  `Escape` para fechar) antes de ser usado em produção.
- Restrição: fluxos que precisam de URL própria (ex.: página de relatório exportável)
  continuam como rotas — o padrão de container é para ações transacionais, não para
  conteúdo navegável.
