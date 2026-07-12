# Runbook — Preservar autoria/histórico ao mergear develop→main (refletir produtividade no GitHub)

**Objetivo:** quando promovermos `develop → main`, fazer de um jeito que **preserve a autoria e as
datas dos commits**, pra que o gráfico de contribuições do GitHub reflita a produtividade real do
desenvolvimento (mesmo assistido por IA). Registro criado em 2026-07-06.

## Por que os commits em `develop` não aparecem no gráfico hoje

O gráfico de contribuições do GitHub só conta commits que atendem TODAS estas condições:

1. **Estão na branch default do repo** (`main`) ou em `gh-pages`. Commits em `develop`/feature branches
   **não contam** até serem mergeados na `main`. → é o motivo principal hoje (seguramos tudo em develop
   pelo gate humano).
2. **Email do autor** casa com um email da conta GitHub. Já configurado:
   `Vitor Emanuel <85122602+logikos33@users.noreply.github.com>`. Commits antigos sob outra identidade
   **não retroagem**.
3. Repo **não é fork** (ok).
4. Se o repo é **privado**: a atividade só aparece no perfil público com a config
   **Settings → Profile → "Include private contributions on my profile"** ligada.

## Checklist ANTES de promover develop→main

- [ ] Ligar **"Include private contributions on my profile"** (GitHub → Settings → Profile) — se o
      `Recognition` for privado, sem isso nada aparece no gráfico público.
- [ ] Confirmar que os commits de develop estão autorados como **Vitor** (email noreply acima):
      `git log develop --format='%an <%ae>' | sort | uniq -c`
- [ ] **NÃO usar SQUASH no merge para main.** Squash colapsa tudo num único commit autorado por quem
      faz o merge → **perde o crédito por commit** e a linha do tempo real.
- [ ] Usar **merge commit preservando histórico**:
  - Via CLI: `git checkout main && git merge --no-ff develop`
  - Via GitHub PR: escolher **"Create a merge commit"** (NUNCA "Squash and merge" nem "Rebase and merge"
    se quiser manter os commits idênticos com autor+data originais).
- [ ] Após o merge + push na `main`, os commits de develop entram no gráfico **com as datas originais**
      (o GitHub usa a data de autor), refletindo quando o trabalho foi feito.

## Config do repo (opcional, pra evitar squash acidental)

- Em **Settings → General → Pull Requests**: manter **"Allow merge commits"** habilitado e considerar
  **desabilitar "Allow squash merging"** no fluxo develop→main pra não colapsar histórico por engano.
  (No fluxo feature→develop, squash pode ser aceitável; a regra crítica é develop→main = merge commit.)

## Medir a produtividade depois (tempo/volume investido)

Depois que estiver na `main`, dá pra extrair o panorama:

```bash
# commits por autor
git shortlog -sn --all

# commits por dia (linha do tempo)
git log --date=short --pretty='%ad' | sort | uniq -c

# commits por autor no período do projeto
git log --since=2026-05-01 --until=2026-07-31 --format='%ad %an' --date=short | sort | uniq -c

# linhas adicionadas/removidas por autor (esforço aproximado)
git log --author="Vitor" --pretty=tformat: --numstat \
  | awk '{add+=$1; del+=$2} END {printf "add %s / del %s\n", add, del}'
```

O gráfico de contribuições (perfil GitHub) + esses números dão a visão de tempo/volume ao longo do
desenvolvimento do sistema.

## Observações honestas

- Commits **antigos** feitos antes de configurar a identidade do Vitor **não vão retroagir** (email não
  bate) — o gráfico reflete de forma completa **daqui pra frente** + o que for mergeado na main.
- O gate humano **develop→staging→main** continua valendo; este runbook é sobre **como** fazer o merge
  final pra main sem perder o histórico, não sobre pular o gate.
