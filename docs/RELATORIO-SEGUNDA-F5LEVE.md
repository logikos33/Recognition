# RELATORIO-SEGUNDA — sessão F5-LEVE (escrito 30/08; placar para segunda 31/08 à noite)

## O que está NO AR, provado (develop = DEV, autodeploy)

- **P1 · EPI funcional de ponta a ponta**: as 4 telas do handoff-v2 + os 4 obrigatórios da paridade mergeados e **provados no DEV pela tela, por perfil, com screenshot** (`docs/quality/evidence/f5leve-sr-a/novo-*.png`): aba Desempenho (editável vs somente-leitura por permissão) · Corrigir caixa (salvamento real + badge de autoria **com nome** — defeito de UUID achado na prova e corrigido em #587) · Parede por site com layouts nomeados · Ranking top-3 · Verificação com fila honesta (invariante D-56 protegido por teste provado por mutação).
- **Primeira demolição real (#588)**: 6 telas antigas fora da árvore (−3.095 linhas), tag de arquivamento `archive/front-antigo-epi-lote1-2026-08-30` no origin, redirects com query preservada provados 13/13, e2e inteiro 47/0.
- **P2 · Demo de Qualidade**: telas F4 no ar carimbadas com pendências verificadas (#590) + `docs/ROTEIRO-DEMO-QUALIDADE.md` (URL fixa por passo, "não prometer" explícito, congelável).
- 11 PRs mergeados nesta leva: #573 #575 #576 #578 #579 #581 #582 #585 #587 #588 #590. Detalhe com evidência: `docs/RELATORIO-VARREDURA-F5LEVE.md`.

## 🔴 O FLIP está pronto para o GO?

**SIM — PR #592 em DRAFT, aguardando o seu GO** (sign-off final do cético por execução: e2e 47/0, vitest 1103/1103, tsc 0, manifesto byte-exato, 9/9 sondas no navegador; AppRoutes 100% fora do diff — os redirects da demolição servem pré e pós flip).

**Condições de GO (quinta 03/09, antes do merge):**
1. Re-rebase sobre a develop do dia + 4 gates de novo na árvore final.
2. Congelamento de merges tocando App.tsx / RotasNovas / AppRoutes / ROTAS_NOVAS entre o rebase e o merge (coordenar com a F5-PESADA).
3. Aviso aos usuários: `/novo` salvo segue funcionando mas muda de endereço; telas antigas alcançáveis (counting, sites, investigation, reports, triagem) seguem no chrome antigo de propósito.
4. Dependência da PESADA: enquanto `app/acesso` não mergear, o deslogado cai no login ANTIGO (indireção TelaLogin = troca de 1 linha depois).

## O que falta, com dono e data

| Item | Dono | Data |
|---|---|---|
| §6 taxa de uso por área · §7 modelo por câmera · §10 logs ao vivo · §12 busca na parede | F5-LEVE | semana de 07/09 (decisão 30/08, via recomendada pelo PARIDADE doc; **avisar o cliente no onboarding**) |
| LOTE 2 da demolição: CamerasPage/AlertsHistoryPage órfãs | F5-LEVE | semana de 07/09 (junto com §6) |
| Família de saúde (4 rotas → 1 tela) | F5-LEVE | prancha até domingo; sem prancha → proposta .dc.html + implementação segunda (SR-C) |
| Cenário (/epi/cameras/:id/scenario) | F5-LEVE + design | só com reexport da prancha; backend é read-only (escrita = pedido registrado) |
| Telas antigas de Qualidade sem substituta (reports/rework/training) | design → F5-LEVE | setembro |
| Pedidos-ao-backend acumulados (presets de parede no servidor; nome de site p/ operador; callback_token; /api/classes envelope) | backend | setembro |

## Riscos de quarta (02/09)

1. Demo roda no PRÉ-flip: URLs com `/novo` (roteiro já cobre; se o GO sair quinta, endereços mudam DEPOIS do onboarding — sem impacto na demo).
2. Superadmin em Eventos precisa assumir contexto + período 30 dias (comportamento esperado; anotado no roteiro da prova).
3. Congelamento terça 18h vale para TODAS as pistas — o flip só re-rebasa, não merge.
