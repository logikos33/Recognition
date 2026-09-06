# ESTADO — V1 RVB (reentrante; releia ANTES de agir)

> Sessão: 05→06/09/2026, execução autônoma em 5 ondas. **47 PRs mergeados.**
> Primeiro ato de toda retomada: `git fetch` + ler este arquivo. Ele MANDA sobre o prompt.
> Evidência = caminho de arquivo, número de PR/issue, saída de comando. ⛔ Nunca conteúdo colado de memória.

## Onde estamos

- **Ambiente da V1: DEV** (decisão do Vitor, 05/09). Produção descartada: `staging` está ~1.246 commits atrás,
  último commit 15/07, e o bundle servido lá **não contém o front novo**.
- `develop` verde, DEV autodeployando dela. `/livez` agora prova o que roda: devolve `commit_source` e
  `tree_digest` (PR #811), não só uma variável.
- **Régua V1 re-medida em 31,6%** (12/38 sub-cláusulas) DEPOIS das ondas 1–3, com 9/9 itens ainda vermelhos.
  As ondas 4 e 5 vieram desse número. ⚠️ **A régua NÃO foi re-medida após as ondas 4 e 5** — o número
  vigente é anterior a 13 PRs. Não cite 31,6% como estado atual: **remeça**.

## O ÚNICO bloqueio de segunda é humano

**#817 — provisionar as 3 contas reais da RVB no DEV.** Um comando, nada a escolher (papel já decidido e
implementado: `trainer` ganhou `verification:read/write` para o ciclo fechar). Sem isso **ninguém entra** —
o tenant RVB tem 14 contas, nenhuma de pessoa real, todas com "último acesso: —".
Os cinco céticos da onda 5 disseram, cada um por sua frente: **nada mais bloqueia pelo lado do código.**

## O que mudou hoje (por família, não por PR)

| família | antes | depois |
|---|---|---|
| a porta | login entregava o **front antigo** | cai no front novo; raiz logada e deslogada com teste |
| verdade na tela | Score 100 "Conforme" sobre 24h sem evento | `null` + "—" com a razão; PDF do R2 e tela não podem discordar |
| procedência | 89% dos eventos eram caixa humana exibida como detecção | badge lê a origem declarada; "ONDE A IA MARCOU" nunca sobre caixa humana |
| segurança | `/andon` **sem JWT** varrendo todos os tenants; 3 blueprints com ZERO gate; `viewer` apagava câmera; operador apagava vídeo com **HTTP 200** | lote P0 + 20 rotas mutantes gateadas, testes cruzando a fronteira HTTP |
| perda de dado | migrations de produção **apagavam** `counting_sessions` e **resetavam credencial a cada deploy** | guarda no runner, válida já com `MIGRATIONS_LEDGER_CUTOVER` ausente (estado de produção hoje) |
| trabalho perdido | dois anotadores sobrescreviam um ao outro com 200 na cara | 409 nominal nas duas telas; F/V/X não avança no 403 |
| sessão | sem refresh; "Renovar" recarregava com o mesmo token | rota de refresh + troca de senha obrigatória com saída |
| jargão/roxo | "YOLOv8" na tela de entrada; SQL cru e `rvb_isolantes` na janela de deploy | 14→0 pares no caminho da RVB; erro sem tripa |

## Dívidas vivas com dono (não morreram — estão no GitHub)

- **#817** contas (bloqueio de segunda) · **#495** worker de produção sem repo · **#735** backup de produção
- **#725** cutover do ledger · **#723**/#222 rotação de senha · **#663** Resend no DEV
- **#832** leitura de videos/rules/operations ainda sem gate (adiado de propósito — gatear leitura na véspera
  quebraria tela de usuário legítimo) · **#840** `SemPermissao.tsx` serve a chave crua e a régua é cega a ela
- **#219** promoção develop→staging (a produção segue com AGPL e sem nada de hoje)

## Lições que custaram caro hoje (não repita)

1. **`gh pr checks` verde não cobre o merge** se a branch está atrás da develop. Rebase e confira de novo.
2. **`git diff --stat origin/develop` mente** quando a develop andou — use `origin/develop...HEAD` (três pontos).
3. **Default de parâmetro é congelado na definição da função.** Um teste do harness passou meses medindo NADA
   porque injetava variável de módulo depois do import (PR #807). Guard novo exige **prova por mutação**.
4. **Dois PRs verdes separados podem ser vermelhos juntos** (#755 × #757). O CI da ponta é o que vale.
5. **O cético acha buraco em quase todo PR** — inclusive regressões que o próprio conserto cria. Taxa de
   reversão medida na re-medição: **6 de 6 itens contestados caíram**. Item sem cético não é confiável: é
   **não auditado**.
6. **A tela irmã é o buraco mais comum**: conserto de tela é conserto do PADRÃO. Enumere as irmãs antes.
7. **Trocar "não sei" por "acho que sei" é pior** — o conserto de proveniência de 04/09 desligou o único
   sinal honesto (`unknown`) ao reportar uma variável em vez do código servido. Corrigido em #811.
