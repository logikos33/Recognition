# Prompt Claude Code — F3: Jornada EPI (o coração)

> Cole no Claude Code na raiz do repo `Recognition`. Referências de design na pasta `design_handoff_logikos_vision/` (abra os .dc.html no navegador). Leia o README.md do pacote antes. Regras transversais: sistema navegável e deployável ao fim da fase · `tsc --noEmit` limpo · testes verdes (incl. `no-offbrand-colors`) · toda rota nova com loading (LogikosLoader) + empty + error · zero jargão de ML em tela de cliente · rotas antigas mantêm redirect.

## Objetivo
As 8 telas da jornada EPI dentro do shell F1, fechando o loop detectar → triar → agir → provar.

## Referências de design
`EPI Dashboard/Ao Vivo/Eventos/Evento Detalhe/Ações/Verificação/Câmeras/Relatórios.dc.html` · `Handoff LOTE 2.dc.html` (componentes e regras).

## Implementar
1. `/epi/dashboard`: score 0–100 (Space Grotesk, tooltip "como é calculado", tendência 7d) + KPIs + widgets arrastáveis existentes (WidgetShell) + seletor site/turno persistente.
2. `/epi/live`: VMS único (fundir grid atual) — presets 2×2/3×3/4×3, colunas 2–6, modo DESTAQUE, overlay toggle (DetectionOverlay sem % de confiança), tile de reconexão com LogikosLoader + TENTATIVA N, drawer da câmera. Em ≥5 colunas: status vira ponto, labels de bbox somem.
3. `/epi/eventos`: fundir Alertas+Investigação — thumbnail com bbox REAL, classe com ícone, câmera por nome (select), ack por botão explícito, seleção múltipla, timeline de barras por hora.
4. `/epi/eventos/:id`: player com faixa 24h color-coded e scrubbing, Prev/Próx câmera vizinha, veredito Confirmar/Descartar/Criar ação (sugestões por tipo, responsável + prazo), Compartilhar (TTL 1h/24h/7d, ver/ver+baixar).
5. `/epi/acoes` v1: criar (inclusive preventiva sem evento — modal Nova ação)/atribuir/concluir; kanban abertas|concluídas + lista; vencida em vermelho; "minhas ações"; taxa de conclusão.
6. `/epi/verificacao`: evidência grande com zoom lado a lado com a detecção proposta; Confirmar/Rejeitar ≥56px; contador; atalhos ← → C R A; A envia para a fila de anotação (Estúdio, F5) sem travar.
7. `/epi/cameras`: absorver Sites/saúde — lista+detalhe com teste de conexão passo a passo (Stepper) e resultado com o que fazer; abas Câmeras · Sites & Edge (modo edge/dual/cloud, saúde do Jetson, edge-sync) · Saúde (semáforo).
8. `/epi/relatorios`: export (período, formato) — a config do digest completa em F5.

## Aceite
Jornada digest→evento→ação completa sem beco; de qualquer evento dá para agir em ≤2 cliques; 4 estados em toda rota.
