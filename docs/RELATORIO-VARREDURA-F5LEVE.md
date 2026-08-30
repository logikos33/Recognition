# Relatório de varredura — sessão F5-LEVE (30/08/2026)

> Fonte de cada afirmação: PR mergeado, teste rodado ou sonda no navegador. Nada alegado sem evidência.

## Placar de PRs (todos mergeados na develop, gates de merge cumpridos)

| PR | Tema | Prova |
|---|---|---|
| #573 | Ranking de câmeras (widget Dashboard) | vitest 154/154 · prova-DEV screenshot |
| #575 | Parede por site + layouts nomeados (AoVivo) | 159/159 · suíte 1024/1025 (flaky alheia) · prova-DEV |
| #576 | Aba Desempenho (ajustar câmera + saúde) | 156/156 · prova-DEV superadmin/operador |
| #578 | Corrigir caixa (EventoDetalhe) | 158/158 · suíte 1024/1024 · prova-DEV com SAVE real |
| #579 | Fila de verificação honesta (§3) | 151/151 · invariante D-56 depois provado por mutação |
| #581 | Confiança em Eventos + fabricante + gate hasModule (§9/§15) | 387/387 · bug real de fetch em Carga corrigido |
| #582 | Sem-sinal + local/módulo no quadrinho (§11/§13) | 177/177 · §14 provado JÁ-COBERTO |
| #585 | PR-A carimbo: 6 telas MIGRADO | manifesto SUBSTITUIDA 6→0 · réguas 8/8 |
| #587 | Autoria com nome (defeito achado na prova-DEV) | pytest 74/74 · ledger append-only preservado |
| #588 | **PR-B demolição lote 1** (−3.095 linhas) | e2e inteiro 47/0 · 13/13 sondas de redirect · mutação D-56 · tag `archive/front-antigo-epi-lote1-2026-08-30` no origin |
| #590 | Carimbo F4 (6 telas Qualidade/Carga SUBSTITUIDA) | pendências VERIFICADAS (candidatas falsas refutadas) |

## Manifesto (pós-demolição, linha a linha por categoria)

- **MIGRADO 1** — ReportsPage (paridade fechada; demolição em lote futuro).
- **SUBSTITUIDA 6** — as 6 F4 de Qualidade/Carga (#590), pendências nomeadas no cabeçalho de cada uma.
- **PENDENTE 146** — telas antigas ainda sem substituta completa; inclui o **LOTE 2 explícito**: `CamerasPage.tsx` e `AlertsHistoryPage.tsx` (órfãs de rota desde #588; morrem na semana de 07/09 junto com §6/§7/§10/§12).
- **SEM-DESENHO 7** — rotas aguardando prancha (família de saúde, cenário, triagem etc.; LISTA-PARA-O-DESIGN-v2).
- **INFRA 226** — não-telas; caso a caso na varredura final da migração.

## Zero link caindo no antigo sem deliberação

- Réguas da coexistencia (rotas relativas · links via rotaNova · inventário de sombras explícito) verdes na develop.
- Pós-#588: TODAS as rotas antigas das 6 telas demolidas redirecionam via `rotaNova()` — 13/13 sondas verdes (param + querystring preservados, zero loop), provado também na semântica pós-flip com `PREFIXO_NOVO=''` temporário.

## Placar do contrato

`python3 tools/build_migration_map.py check` → **0 inconsistências** (rodado pelo cético em #588).

## Paridade — estado final da lista de 15

Fechados: §1 §2 §3 §4 §5 §9 §11 §13 §14 §15. Refutados na lista final: janela-livre, marcação-em-alerta, acesso-direto-à-fila. **Adiados com dono e prazo (decisão 30/08, via recomendada pelo próprio doc): §6 §7 §10 §12 → semana de 07/09, pista F5-LEVE, aviso ao cliente no onboarding.**

## Evidência visual

`docs/quality/evidence/f5leve-sr-a/novo-*.png` — 5 provas × 2 perfis no front novo do DEV (marcador de shell validado por screenshot; 1ª rodada da prova invalidada por ter testado o front antigo — contraste preservado nos arquivos sem prefixo).

## Dívidas registradas (não desta leva)

- Pedidos-ao-backend: presets de parede no servidor (por site) · nome legível do site para papel operador · (herdados) /api/training/jobs vaza callback_token; /api/classes fora do envelope.
- `apps/frontend/test-results/` tracked e não gitignorado (dívida pré-existente).
- 3 rotas antigas de Qualidade sem substituta (reports/rework/training) seguem PENDENTE.
