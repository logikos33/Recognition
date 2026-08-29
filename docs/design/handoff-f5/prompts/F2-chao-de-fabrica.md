# Prompt Claude Code — F2: Chão de fábrica fora do shell

> Cole no Claude Code na raiz do repo `Recognition`. Referências de design na pasta `design_handoff_logikos_vision/` (abra os .dc.html no navegador). Leia o README.md do pacote antes. Regras transversais: sistema navegável e deployável ao fim da fase · `tsc --noEmit` limpo · testes verdes (incl. `no-offbrand-colors`) · toda rota nova com loading (LogikosLoader) + empty + error · zero jargão de ML em tela de cliente · rotas antigas mantêm redirect.

## Objetivo
Kiosk e andon rodando sem o chrome do SaaS, com autenticação de dispositivo.

## Referências de design
`Kiosk RVB.dc.html` (aprovado — NÃO redesenhar) · variante tile do loader em `Logikos Loading.dc.html`.

## Implementar
1. Entry separado para `/tablet/:station` e `/quality/andon` (sem TopBar/sidebar), token de dispositivo (BE `verify_andon_access`) + claim-code UI no admin.
2. Indicador de desconexão WS no kiosk (fail-open explícito: banner "Validação indisponível — siga o processo normal", nunca bloqueia).
3. Branding do tenant no kiosk via tokens; textos de veredito vindos de config (nada hard-coded RVB).

## Aceite
Tablet abre sem login interativo e sem chrome do SaaS; queda de rede não trava a produção.
