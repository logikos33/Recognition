# Runbook — OTA bare-metal do edge-sync-agent (ADR-0057 item 10)

Canal de software: a nuvem publica um `target_ref` (git ref — commit ou tag)
por canal (`dev` para a RVB); o agente compara com o que está rodando e, se
diferente, puxa a atualização sozinho. **A nuvem nunca empurra/aplica nada no
device diretamente** — só indica.

**Por que não é Docker:** `docs/edge/REGRAS_PLATAFORMA_JETSON.md` §3.4 documenta
que sudo no pandora está bloqueado pra execução autônoma, e Docker não é
usável sem sudo (`socket é root:docker`). Não existe `Dockerfile` em
`services/edge-sync-agent/`. "Versão" aqui é **git ref + venv por release +
symlink `current` atômico** — ver `services/edge-sync-agent/app/ota/`.

---

## Mecanismo

```
GET /api/v1/edge/software/target  (device auth RS256, escopo config:read)
  → {channel, target_ref}                         [app/ota/client.py]

target_ref != ref ativo (current_ref, resolvido do symlink `current`)?
  → git fetch (no OTA_SOURCE_REPO)                 [release_manager.fetch]
  → git worktree add releases/<ref>/ <ref>          [release_manager.build_release]
  → python3 -m venv + pip install -r requirements.txt
  → smoke-check: python -c "import app.main"        [release_manager.smoke_check]
  → troca `current` atomicamente (symlink temp + os.replace)
  → systemctl --user restart edge-sync-agent
  → health-check pós-restart: serviço ativo + heartbeat.ok recente
      (retries com backoff — ver app/ota/updater.py)
  → ok:   poda releases antigas (mantém current+previous+últimas K)
          + recicla as units secundárias (best-effort, ver abaixo)
  → falha: aponta `current` de volta pra release anterior, reinicia de novo
          + recicla as units secundárias de volta (best-effort, mesma lógica)
```

## Units secundárias recicladas junto (frame-collector, live-view)

Até 06/08/2026 o updater reiniciava **só** `edge-sync-agent` — `edge-frame-collector`
e `edge-live-view` rodam do mesmo symlink `current`, mas ficavam presas no código da
release ANTERIOR até alguém dar `systemctl --user restart` manual no box (dívida
registrada em `docs/REGISTRO_DE_DECISOES.md` D-42, item que já mordeu de verdade —
mudança de coleta que não chegava no box).

`OTA_UNIT_NAME` (edge-sync-agent) continua sendo a **única** unit cuja saúde decide
o resultado do ciclo — é ela que fala com a nuvem e toca o heartbeat sentinel; não
existe sinal equivalente pras secundárias. Por isso:

- `OTA_SECONDARY_UNIT_NAMES` (novo, csv; padrão `edge-frame-collector,edge-live-view`)
  lista as units que são recicladas **depois** do desfecho de `edge-sync-agent` —
  nunca antes, nunca em paralelo — para que uma secundária jamais seja empurrada pra
  cima de um release que acaba falhando a validação do principal.
- Restart best-effort: falha ao reiniciar uma secundária fica **alta no log**
  (`ota_secondary_restart_failed`/`ota_secondary_restart_error`) mas NUNCA dispara
  rollback do release nem impede a tentativa das outras secundárias da lista.
- No ROLLBACK, as secundárias também são recicladas — depois que `current` já
  voltou pra release anterior — pra não ficarem presas na release nova enquanto o
  principal já reverteu (a única exceção: quando não existe release anterior pra
  reverter — `rollback_impossible` — as secundárias ficam intocadas de propósito,
  já que empurrá-las pro mesmo código recém-reprovado não ajuda em nada).
- `edge-telemetry-collector` foi **avaliado e excluído** de propósito: é uma unit
  systemd de **sistema** (`sudo`, `WantedBy=multi-user.target`), não `--user` como
  as outras três, e roda de um path fixo (`/opt/recognition/edge-sync-agent`) fora
  do symlink `current` — o updater (sem sudo, `docs/edge/REGRAS_PLATAFORMA_JETSON.md`
  §3.4) não teria nem permissão de reiniciá-la, e reiniciá-la não mudaria o código
  dela mesmo assim.

## Por que é uma unit systemd SEPARADA do daemon (não uma thread do PR-C)

`systemctl --user restart edge-sync-agent` mata **todo o processo** do daemon
quase imediatamente — inclusive qualquer thread que tivesse disparado esse
restart. Se a lógica de "esperar, verificar saúde, reverter se falhar"
rodasse dentro do próprio processo que está sendo reiniciado, o restart
mataria o código exatamente no momento em que ele tentaria provar que a nova
versão funciona — quebrando silenciosamente a única garantia que este
mecanismo existe pra dar ("nunca bricar o box"). Por isso:

- `edge-sync-agent.service` — o daemon (PR-C), inalterado na lógica.
- `edge-sync-agent-updater.service` + `.timer` — processo **separado**,
  dispara periodicamente (`OnUnitActiveSec=10min`), faz o ciclo completo
  (build→swap→restart→health→rollback) e sai. Sobrevive ao restart do daemon
  porque não está no cgroup dele.

## Prova de vida pós-restart: sentinel do heartbeat

O updater não consegue perguntar ao daemon "seu heartbeat está indo?" depois
de reiniciá-lo (são processos diferentes, sem IPC). Em vez disso,
`heartbeat.py` (PR-B) toca um arquivo (`EDGE_HEARTBEAT_SENTINEL_PATH`, default
`~/.local/state/recognition/heartbeat.ok`) a cada envio bem-sucedido; o
updater olha o `mtime` desse arquivo — se estiver "recente" (dentro de
`heartbeat_fresh_s`, folga sobre o intervalo de heartbeat) **e** o serviço
estiver `active`, considera saudável.

---

## Publicar uma atualização (lado nuvem)

```bash
curl -X PUT https://api-v3-desenvolvimento.up.railway.app/api/v1/admin/software-channels/dev \
  -H "Authorization: Bearer <token superadmin>" \
  -H "Content-Type: application/json" \
  -d '{"target_ref": "<sha ou tag>"}'
```

Consultar o estado atual: `GET /api/v1/admin/software-channels` (lista todos
os canais e seus `target_ref`).

## Instalação no box (sem sudo)

```bash
cd services/edge-sync-agent/deploy
./install.sh install
# editar ~/.config/recognition/edge-sync-agent.env — sobretudo OTA_SOURCE_REPO
systemctl --user enable --now edge-sync-agent
systemctl --user enable --now edge-sync-agent-updater.timer   # liga o canal de OTA
```

`OTA_SOURCE_REPO` deve apontar pro checkout git de onde `install.sh` rodou
(`git worktree add` precisa de um repo real como fonte). `install.sh install`
sem OTA ainda habilitado só cria o symlink `current` apontando pro checkout
atual (mesmo comportamento do PR-D original) — o **primeiro ciclo real do
updater** migra sozinho pro layout `releases/<ref>/` de verdade assim que um
`target_ref` for publicado (o "ref ativo" resolvido de um `current` que não
segue o padrão `releases/<ref>/...` nunca bate com um `target_ref` real, o
que naturalmente dispara essa migração — não precisou de bootstrap especial).

## Como provar o update remoto (gate 1.6 — pendente, é OPS/Vitor)

Esta sessão não tem acesso ao box físico — o checklist abaixo **não foi
executado**, fica pendente:

- [ ] Publicar um `target_ref` novo (commit real subsequente) no canal `dev`.
- [ ] `systemctl --user start edge-sync-agent-updater` (ou esperar o timer) e
      acompanhar `journalctl --user -u edge-sync-agent-updater -f`.
- [ ] Confirmar `readlink ~/recognition/current` mudou pro novo ref.
- [ ] Confirmar `systemctl --user status edge-sync-agent` voltou a `active`
      e o heartbeat reapareceu no admin (`GET /sites/<site_id>/heartbeats`).
- [ ] **Forçar uma falha** (ex.: publicar um `target_ref` de um commit com
      `requirements.txt` quebrado ou um `app/main.py` com erro de sintaxe) e
      confirmar que `current` volta pro ref anterior sozinho e o serviço
      volta a ficar saudável — sem intervenção manual.
- [ ] Confirmar releases antigas são podadas (`ls ~/recognition/releases/`
      não cresce sem limite).

## Fora de escopo

Lease de licença (ADR-0057 item 4.2 — não acoplar ao OTA; box em dev é
permissivo, item 11) · modelo→edge (Plano 4, canal separado) ·
reconciliar `deployments/edge/systemd/recognition-edge-sync.service`
(chip `task_e5e9e6b7`, já aberto).
