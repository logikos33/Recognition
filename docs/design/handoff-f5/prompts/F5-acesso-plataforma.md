# Prompt Claude Code — F5: Acesso e plataforma

> Cole no Claude Code na raiz do repo `Recognition`. Referências de design na pasta `design_handoff_logikos_vision/` (abra os .dc.html no navegador). Leia o README.md do pacote antes. Regras transversais: sistema navegável e deployável ao fim da fase · `tsc --noEmit` limpo · testes verdes (incl. `no-offbrand-colors`) · toda rota nova com loading (LogikosLoader) + empty + error · zero jargão de ML em tela de cliente · rotas antigas mantêm redirect.

## Objetivo
Fechar plataforma: acesso self-service, digest, share links, TV e Estúdio.

## Referências de design
`Estúdio.dc.html` · `TV RVB.dc.html` · `EPI Relatórios.dc.html` (digest) · `EPI Evento Detalhe.dc.html` (share) · `Handoff LOTE 3.dc.html`.

## Implementar
1. "Esqueci minha senha" self-service (reset com senha temporária já existe no BE — ADR-0042).
2. Canais de notificação + digest diário por e-mail (BE pronto): horário, destinatários, conteúdo (score do dia, top-5 eventos com thumbnail, ações vencidas), prévia. Deep links do e-mail para /epi/eventos/:id.
3. Share links com TTL (1h/24h/7d) e permissão ver/ver+baixar + central de links no admin.
4. `/tv/:site`: playlist de painéis (score gigante 360px, semáforo, últimos eventos), rotação a cada N s, relógio, sem chrome e sem interação, 1080p, legível a 10 m, grid grego de fundo.
5. Estúdio no registry v1, atrás de gate `estudio:acesso` (tela de acesso restrito com CTA "Solicitar acesso"): Dados (galeria + upload, isolamento por tenant), Anotação (fila recebendo casos da Verificação EPI + pré-anotação), Treinos (job ao vivo: progresso, época, ETA, curvas erro↓/mAP↑), Modelos (mAP/precisão/recall em Mono, ativar com validação, comparar 2).
6. Announcements banner da plataforma.

## Aceite
Digest chega por e-mail com deep links funcionais; TV roda sozinha; Estúdio invisível para quem não tem a permissão; loop Verificação → Anotação → Treino → Modelos → ativar fecha no produto.
