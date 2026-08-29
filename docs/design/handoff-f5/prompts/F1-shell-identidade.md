# Prompt Claude Code — F1: Shell único + identidade Twins

> Cole no Claude Code na raiz do repo `Recognition`. Referências de design na pasta `design_handoff_logikos_vision/` (abra os .dc.html no navegador). Leia o README.md do pacote antes. Regras transversais: sistema navegável e deployável ao fim da fase · `tsc --noEmit` limpo · testes verdes (incl. `no-offbrand-colors`) · toda rota nova com loading (LogikosLoader) + empty + error · zero jargão de ML em tela de cliente · rotas antigas mantêm redirect.

## Objetivo
Uma navegação só para o SaaS inteiro, com a identidade Twins (tokens --lk-*, 3 vozes tipográficas, LogikosLoader) aplicada no shell — sem tocar as telas internas ainda.

## Referências de design
`Shell Logikos Vision.dc.html` (TopBar, sidebar contextual, admin, sessão, ⌘K, mobile) · `Logikos Loading.dc.html` + `lk-loader.js` (loader) · `Handoff LOTE 1.dc.html` (medidas e componentes).

## Implementar
1. Tokens `--lk-*` e `--st-*` no tema `recognition-dark`, preservando a ponte white-label (ThemeProvider → /v1/tenant/branding → CSS vars). Substituir hexes fora da marca (#ef4444, #f59e0b, #6366f1…) pelos tokens semânticos.
2. TopBar global 56px: monograma O-fechadura + wordmark LOGIKOS (latino), switcher de módulo (só módulos do usuário), breadcrumb dinâmico site → área → câmera (ellipsis no nível não-final; busca cede espaço até 110px), busca ⌘K, sino, usuário com papel em PT + Sair.
3. Sidebar contextual por módulo, 236px/64px colapsável, item ativo ciano com borda esquerda 2px; rodapé Trocar módulo · Admin (superadmin). A sidebar do EPI NUNCA aparece dentro de Qualidade/Carga.
4. LogikosLoader como componente React (portar máquina de estados de `lk-loader.js`): fullscreen na troca de rota/módulo, tile em câmera reconectando, spinner ≤24px em botões. Substituir LoadingSpinner.
5. Transição Admin: faixa 2px âmbar + banner "VOCÊ ESTÁ NA PLATAFORMA · PAINEL ADMIN" com tenant em foco e Voltar ao módulo — sem redesenhar o admin.
6. Sessão expirando: toast 5 min antes com countdown mono e Renovar.
7. Tipografia 3 vozes via Google Fonts; lucide-react (stroke reto) no lugar de TODOS os emojis; ⌘K básico (rotas + câmeras) conforme o design.
8. Mobile: sidebar vira drawer; alvos ≥44px.

## Aceite
Uma navegação; Quality sem menu do EPI; breadcrumb em 100% das rotas; todo estado de espera é LogikosLoader; zero grego, zero emoji estrutural.
