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

---

## 2026-08-18 · OTA FEITO · timer NO AR

**Chaves do Vitor: "OK checks" ✅ executada · "OK OTA" ✅ executada.**

### OTA — concluído e verificado
`current` → **`3e1afb57`**. Heartbeats 12:49:26 / 12:50:18 / 12:51:09 **após** o restart de 12:48:27.
`app.main` · `app.collector` · `app.live_view` sob o release novo. **Live view confirmado no olho
pelo Vitor.** Disco 56 GB.

🔴 **Achado (D-179): "desfixar" é apontar `public.edge_software_channels.dev` na NUVEM.** O updater
não lê o git do box — busca `target_ref` da API. Rodei-o com a fonte já atualizada e ele **saiu 0 sem
fazer nada**. **Rollback = apontar o canal de volta para `123f739a53f083e498dcf665fbc3933b982cf6db`**
e rodar o updater. ⚠️ Verificar por `readlink ~/recognition/current`, ⛔ nunca pelo exit code.

### Timer
`edge-replay-miner.timer` habilitado — próximo **19/08 03:30**. 1º ciclo disparado à mão como
verificação, rodando.

### Decisões desta sessão
- **Ciclo 2 parado antes do OTA**: 6/162 tarefas em 1h20 (~35h para fechar), 1.147 recortes já
  salvos, dedup protege re-mineração.
- **D-180 · trava + escopo**: `flock` (vale para systemd E coleta manual) · `--dias` 3→2.
  **#442 medido: 306 de ~612 janelas foram 404** — corta metade das requisições, ⚠️ mas 404 é falha
  barata, o ganho de TEMPO é menor. Por isso o escopo caiu também.
- **D-176** checks obrigatórios · **D-177** contrato por teste · **D-178** perda declarada.

### ⏭️ PRÓXIMO PASSO
1. **PR #457** (trava+escopo) e **#449** (D-176..178) → merge com CI verde → OTA de novo para levar a
   trava ao box *(canal `dev` → novo SHA)*
2. 🔴 **Prova DUPLA de retomabilidade** — matar o ciclo no meio, retomar, **posição certa E zero
   re-upload**. Agora possível: o estado persiste (`~/.local/state/recognition/`).
3. **M1 com projeção** — do ciclo 2 (1.147 recortes, 828 frames escaneados no ciclo 1, taxa de pessoa
   7,9%, **0 rejeitados por nitidez em 828** = re-medição sobre replay, D-173 confirmado em fonte
   independente).
4. **M3.4** pré-anotação fase A · **M3.5** multiplicador.
5. Issue: balde `missingCrops` visível no servidor (D-178) — perda humana nunca mais silenciosa.

---

## 2026-08-18 · PROVA DUPLA DE RETOMABILIDADE — ✅ PASSOU (medida, não declarada)

Feita no box, com o código pós-#463 (OTA nº 3 → `current` = `b8668b72`, verificado por `readlink`).

| momento | frames no banco | estado em disco |
|---|---|---|
| antes | 10.919 | *(apagado de propósito)* |
| durante a corrida | 10.938 | **`{"frames_uploaded": {"ch1": 19}}`** ← existia NO MEIO |
| após `SIGKILL` | 10.938 | **`{"ch1": 19}` intacto** |
| após retomada | 10.956 | `{"ch1": 19}` |

### Asserção 1 · posição retomada ✅
O arquivo de estado **existia durante a corrida** e **sobreviveu ao `SIGKILL`**. Antes do #463 ele só
nascia no fim do laço de 162 tarefas — a corrida morta perdia tudo.

### Asserção 2 · zero re-upload ✅
**37 frames, 37 instantes de captura DISTINTOS, zero repetido.**

⚠️ Conferi pelo `captured_at`, ⛔ não pelo nome do arquivo: nome carrega timestamp de captura, então
"nomes distintos" seria prova fraca — re-minerar a mesma janela geraria nome diferente. Instante
repetido é o que denunciaria janela re-minerada. Não houve nenhum.

Os instantes vão de 15:27:52 a 15:36:11 em progressão contínua — a retomada **seguiu em frente**, ⛔
não replicou.

### ⚠️ Uma folga honesta
O contador `ch1` ficou em 19 após a retomada, embora ela tenha subido 18 frames. A leitura foi feita
no meio de uma tarefa (a gravação é por tarefa concluída), mas **a semântica do contador merece um
olhar** — ⛔ não afeta as duas asserções, que são sobre sobrevivência do estado e ausência de
re-upload. Fica como ponto a verificar no próximo ciclo.

## ⏭️ PRÓXIMO PASSO
1. **M1 com projeção** — ciclo 2 (1.147 recortes) + este ciclo · rendimento câmera × hora · dedup ·
   nitidez re-medida (**0 borrados em 828 frames** no ciclo 1, D-173 confirmado em fonte independente)
2. **M3.4** pré-anotação fase A · **M3.5** multiplicador
3. Issues abertas nesta rodada: **#465** (playwright pendura 34+ min — não é obrigatório, mas queima
   runner e polui o quadro) · #442 · #445 · #448
