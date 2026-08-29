# Prompt Claude Code — F4: Qualidade integrada + Carga unificada

> Cole no Claude Code na raiz do repo `Recognition`. Referências de design na pasta `design_handoff_logikos_vision/` (abra os .dc.html no navegador). Leia o README.md do pacote antes. Regras transversais: sistema navegável e deployável ao fim da fase · `tsc --noEmit` limpo · testes verdes (incl. `no-offbrand-colors`) · toda rota nova com loading (LogikosLoader) + empty + error · zero jargão de ML em tela de cliente · rotas antigas mantêm redirect.

## Objetivo
Qualidade dentro do shell (telas aprovadas preservadas) e Carga como um módulo só.

## Referências de design
`Qualidade.dc.html` (jornada no shell) · `Gestão/Revisão/Configuração Qualidade.dc.html` (aprovadas — recriar fiel, sem redesenhar) · `Carga.dc.html` · `Handoff LOTE 3.dc.html`.

## Implementar
1. Sidebar Qualidade: Dashboard · Inspeções · Peças · Retrabalho · Câmeras · Relatórios · Config (Treinamento migra para o Estúdio). Telas de módulo deixam de renderizar header próprio — o shell fornece TopBar/breadcrumb.
2. Ligar `inspections` no service real; aplicar Twins conforme as telas aprovadas; gate do modo demo.
3. Telas novas do Qualidade: Retrabalho (KPIs + fila NC → retrabalho → recaptura → conforme, tempo acima da meta em âmbar) e Câmeras de estação (zona de captura demarcada, último veredito, teste de conexão).
4. `/carga`: fundir counting+fueling — UM nome (Carga), rotas separadas: dashboard (KPIs, sessões/hora, divergência por baia), baias (cards com live + contador), eventos, validação (contado vs manual editável, 2 decisões explícitas, registro autor/hora, fila de pendentes). Tokens no lugar dos 91 inline styles.
5. Resgatar relatórios reais em /epi/relatorios e /carga.

## Aceite
Zero mock em tela de produto; um nome para Carga; telas aprovadas do Qualidade pixel-fiéis dentro do shell.
