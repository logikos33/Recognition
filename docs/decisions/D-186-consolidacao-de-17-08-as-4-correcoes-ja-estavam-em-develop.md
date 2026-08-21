# D-186 · Consolidação de 17/08: as 4 correções já estavam em develop; merges parados por CI vermelho pré-existente

**Data:** 2026-08-17 · **Status:** ↩ substituída — o bloqueio descrito aqui foi removido (ver "Depois")

> **Nota de port.** Corpo verbatim da entrada que os PRs #385/#386 acrescentavam a
> `../REGISTRO_DE_DECISOES.md` — arquivo **congelado** desde a migração para um-arquivo-por-decisão.
> Lá ela nascia como `D-116`, número **já ocupado** na `develop` por outra decisão. Portada aqui com
> número livre; os PRs de origem foram fechados sem merge.

**17/08 · Claude · 📄 análise (sem código)**

**Provado (`file:line` no clone).** #378 `versioning_v2.py:402 "supercategory": module_code` · #381 migrations
118–122 presentes · #382 `gpu_reconciler.py:161` + "ALERTA, NÃO termina" · #376 docs-gate em `ci.yml`. **As
correções que importam já estão em develop.** Nenhum merge feito: **todo PR aberto está vermelho no check
pré-existente `SCA (npm audit) (landing)`** (falha idêntica em #385/#343/#387, dep da landing alheia aos diffs).
`develop` é não-protegida (GitHub deixaria), mas "CI vermelho PARE". **Passo do Vitor:** bumpar a dep da landing
ou marcar o check advisory → #343/#385/#386 mergeiam limpo.

**Veredito: ⏸️ mergear docs quando CI verde.**

## Depois (2026-08-21, no port)

O "passo do Vitor" foi feito, pelas duas pontas, e o bloqueio ⛔ não existe mais:

- **#432** tornou o `SCA (npm audit)` `continue-on-error` **e** escopado ao app que o PR toca — o vermelho
  deixou de aparecer em PR que ⛔ não mexe na landing (era o caso de #385/#386, que só tocam docs);
- **#488** achou que o `security-scan.yml` estava sendo **recusado inteiro pelo GitHub** havia 85 runs (chave
  YAML duplicada) — ⛔ nenhum scan rodava. Corrigido; o workflow voltou a executar e a `develop` fecha verde.

⚠️ A recomendação de mergear os docs ⛔ **não** foi seguida: o conteúdo destes PRs já havia entrado na `develop`
por outra via (renumerado `D-118`..`D-127`), então mergear teria duplicado entrada. Ver [[D-188]].
