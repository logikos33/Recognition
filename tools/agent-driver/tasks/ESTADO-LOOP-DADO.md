# ESTADO — MISSÃO DADO (reentrante)

> Leia isto ANTES da tabela do prompt. `git fetch` primeiro. Última sessão: **2026-08-18**.

## ✅ Feito

| marco | estado |
|---|---|
| **M0 · #436** | ✅ **PR #437** — taxonomia por janela (`sem_gravacao`/`erro_transporte`/`falha_infra`), infra aborta na 1ª com exit 3, resumo por categoria, 7 testes (32 no módulo). **Destrava o timer.** |
| Na develop | #416 fusão atômica · #430 harness · #431 retenção · #432 SCA escopado · #435 minerador-serviço |
| Issues | #417–#436 abertas · #391 fechado (superado, prova byte a byte) |

## 🔴 RODANDO — não mate

**Coleta no Orin**, worktree isolado `/tmp/miner-run` (box **PINADO**), log `/tmp/coleta_20260818.log`.
20 canais · 3 dias (16–18/08) · 162 tarefas. Última leitura: **38 recortes `201 Created`**, 71 janelas
sem gravação. Retomar leitura:

```bash
ssh pandora@100.93.126.76 'grep -c "201 Created" /tmp/coleta_20260818.log; pgrep -cf "python /tmp/roda_coleta.py"'
```

⚠️ **Relançar** (o launcher já tem PATH do ffmpeg e guarda de aborto):
`ssh pandora@... 'nohup setsid ~/recognition/current/.venv/bin/python /tmp/roda_coleta.py > /tmp/coleta_$(date +%Y%m%d).log 2>&1 < /dev/null & disown'`

## ⏭️ PRÓXIMO PASSO

1. **M1** — quando a coleta terminar: rendimento câmera × faixa de hora · dedup · **re-medir nitidez
   sobre replay** (limiar 150 INTACTO) · **projeção por janela de 4 dias com ressalva de dia da semana**.
2. **M3.2/3.3/3.4** — modo estreito, fila pela carência, pré-anotação fase A.

## 🔎 Achado que corrige a premissa do M3.1

**Teclado e auto-avanço já existem em boa parte.** `cropClassifierLogic.ts:238` tem **13 bindings**
classe×estado (`1/2/3` auditiva · `q/w/e/r` mascara · `a/s/d` botas · `z/x/c` óculos);
`CropClassifier.tsx:557` trata `Enter`=aprovar, `Backspace`=voltar, `u`=desfazer, pular, não-sei,
reprovar; o mapa é visível nos botões; e **`avgSeconds`/recorte já é medido e exibido** (`:312`) — o
instrumento do M3.5 já está no ar.

**Falta de verdade:** (a) **auto-avanço** após tecla de classe em modo de uma classe só — hoje ainda
exige `Enter`; (b) modo estreito; (c) fila pela carência; (d) pré-anotação.
⚠️ **`z` para desfazer COLIDE** com `z`=óculos→presente. `u` já funciona e está escrito na tela —
⛔ não rebatizar sem decidir a colisão.

## 🔑 Preparado, aguardando chave do Vitor

### "OK checks" — comando pronto (reversível)
```bash
gh api -X PUT repos/logikos33/Recognition/branches/develop/protection \
  --input - <<'JSON'
{"required_status_checks":{"strict":false,"contexts":[
   "License gate (no AGPL/GPL in serving path)","Migrations harness (D1)","Tests (pytest)"]},
 "enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null}
JSON
# prova:    gh api repos/logikos33/Recognition/branches/develop/protection -q .required_status_checks.contexts
# reverter: gh api -X DELETE repos/logikos33/Recognition/branches/develop/protection
```
⚠️ Hoje: **404 Branch not protected**, `rulesets: []` — nenhum check é obrigatório (issue #433).
SCA fica como sinal (já escopado por caminho, #432).

### "OK OTA <dia/hora>" — plano pronto
- **Delta medido** `f8a3f1d4..7d6efe45` em `services/edge-sync-agent/`: **32 arquivos, +4841/−38**,
  quase tudo aditivo (o minerador, que não existe no box) — **reconferir na hora**, a develop andou.
- **Sequência:** `cd ~/recognition-src && git fetch origin develop && git checkout develop-local &&
  git merge --ff-only origin/develop` → o `edge-sync-agent-updater.timer` (10 min) constrói o release.
- **Verificação pós (com prova):** `systemctl --user is-active edge-sync-agent edge-frame-collector
  edge-live-view` = `active` · heartbeat novo no DEV · live view abre.
- **Rollback:** repinar o release atual —
  `ln -sfn ~/recognition/releases/123f739a53f083e498dcf665fbc3933b982cf6db/services/edge-sync-agent ~/recognition/current`
  + `systemctl --user restart edge-sync-agent edge-frame-collector`. **Release atual: `123f739a…`.**
- **Depois do OTA:** `systemctl --user enable --now edge-replay-miner.timer` e **verificar o 1º ciclo**.

⚠️ **Enquanto não há timer: coleta manual a cada 2 dias.** É o anti-padrão do D-174 em contenção —
está aqui no ESTADO justamente porque lista de pendências humana não tem relógio.

## Travas ativas
box PINADO · nenhum `DELETE` · zero segredo em log/argv · anti-lockout · reserva de disco ·
só DESENVOLVIMENTO (`staging`/`main`/`interchange` intocados).
