# Princípios de Design — SLC (Simple · Lovable · Complete)

**Norte de design da Recognition.** Guia o protótipo, as ondas de restyle e toda feature nova.
Filosofia: **SLC** (Simple, Lovable, Complete) — em vez de "mínimo viável", entregar algo **simples,
amável e completo**. Complementa: Contrato de Operabilidade (leigo opera pela UI), WS1-WS11
(UX_FUNCTIONAL_BACKLOG), guard-rail de cor (task-065). Público-alvo: **operador leigo** (não técnico).

---

## SIMPLES — reduzir carga cognitiva

- **Uma ação primária por tela.** Um botão principal claro (cor de marca); o resto é secundário/discreto.
- **Divulgação progressiva.** Mostrar o essencial; esconder o avançado atrás de "mais opções"/abas.
  Nada de despejar 20 campos de uma vez.
- **Linguagem humana, não técnica.** Traduzir chaves do backend → nomes que o leigo entende (WS2).
  Nunca expor nome técnico/enum na tela. "no_helmet" → "Sem capacete".
- **IA previsível.** Navegação consistente; cada coisa num lugar óbvio. Funções de admin no Admin
  (mover Site/Saúde pro admin — WS9), operação na operação.
- **Menos escolhas, bons defaults.** Câmera já nasce no substream (task-067); wizard com valores
  sensatos pré-preenchidos.

## AMÁVEL (LOVABLE) — que dê gosto de usar

- **Feedback imediato em tudo.** Hover perceptível em todo interativo; estados de foco; transições
  suaves (150-250ms); nada "morto" ao clicar.
- **Estados de carregamento e vazio caprichados.** "Conectando…" no vídeo em vez de erro; empty state
  que ensina o próximo passo (não uma tela em branco).
- **Erros empáticos e acionáveis.** Dizer o que aconteceu + como resolver, em português humano.
  Nada de stack trace / "column tenant_id does not exist" na cara do usuário.
- **Consistência = confiança.** Mesmos componentes, cores, espaçamentos em todo lugar (tokens WS1).
  Inconsistência parece amador.
- **Identidade visual coerente + white-label.** Cores da marca aplicadas via token; o tenant ajusta a
  paleta e TUDO acompanha (inclusive superfícies claras — o bug da 063 não pode existir).
- **Microinterações com propósito.** Pequenos toques (contador que anima, badge que pulsa num alerta)
  — sem exagero, sempre a serviço da clareza.

## COMPLETO — sem pontas soltas

- **Zero becos sem saída.** Todo botão leva a algo (o "Configurações" que não vai a lugar nenhum — WS9
  — ou faz algo, ou some). Todo link/notificação faz deep-link pro lugar certo.
- **Todo fluxo operável pela UI, sem script** (Contrato de Operabilidade). Se precisa de terminal, não
  está completo.
- **Cobrir todos os estados:** default, vazio, carregando, erro, sucesso, sem-permissão. Uma tela só
  está pronta quando os 6 existem.
- **Jornadas inteiras, não telas soltas.** Criar usuário → permissão → tenant → acesso numa jornada
  ligada (WS9), sem o usuário se perder trocando de aba.
- **Nada "em breve" no caminho crítico.** Placeholder é aceitável em módulo futuro (fueling), não num
  fluxo que o cliente precisa hoje.

---

## Navegação & Interatividade (profissional + fácil de navegar)

- **Hierarquia visual clara:** o olho sabe onde olhar primeiro (título → ação → conteúdo).
- **Navegação sempre visível e consistente** (sidebar/topo), com indicação de onde você está
  (breadcrumb / item ativo).
- **Deep-links e cross-linking** entre telas relacionadas (notificação "configurar chave" abre o drawer
  certo — WS9).
- **Responsivo e rápido:** percepção de velocidade (skeletons, otimismo na UI), sem travar ao navegar
  (lifecycle limpo — task-062).
- **Dashboards com cara de BI** (gráficos + séries temporais), não só cards com números (WS3/WS11).

---

## Como aplicar

1. **No protótipo estático:** desenhar cada tela contra esta lista (S/L/C + navegação). Usar os tokens
   extraídos na auditoria como base e divergir com intenção.
2. **Nas ondas de restyle:** priorizar pelo que mais viola SLC nas telas mais usadas (o REPORT da
   auditoria dá o mapa).
3. **Em feature nova:** só é "Concluído" quando passa nos 6 estados + Contrato de Operabilidade + tokens
   (sem hardcode — guard-rail 065).

## Referências de inspiração (inspirar, não copiar)

- ContaAzul (clareza pro leigo), Linear/Vercel (polish e consistência), Grafana/Datadog (observability
  com cara de BI — WS11). Referência de método: "SLC" (Jason Cohen).
