# Runbook — Deploy do edge-sync-agent (systemd + NTP) — Fase 4 PR-D

Daemon completo do edge-sync-agent (`services/edge-sync-agent/app/main.py`'s
`run_daemon()`, PR-C): identidade do device (PR-A) + evidence/discovery API +
`config_poller`/`command_poller`/`uploader`/`heartbeat` (PR-B), cada um
supervisionado com restart+backoff, shutdown gracioso em `SIGTERM`/`SIGINT`.

**Código:** `services/edge-sync-agent/app/main.py` (`run_daemon`).
**Testes (offline):** `services/edge-sync-agent/tests/test_daemon.py`,
`test_main.py`, `test_heartbeat.py`, `test_token_manager.py`, `test_enrollment.py`.

---

## Por que `systemctl --user` (sem sudo) e não uma unit de sistema

`docs/edge/REGRAS_PLATAFORMA_JETSON.md` §3.4 (achado de sessão hands-on real no
box, não especulação) documenta que **sudo no pandora exige senha e está
bloqueado pra execução autônoma** — bate com `systemd de sistema`,
`daemon-reload` de sistema, `/etc/systemd/system/`. O padrão **já provado**
no soak co-residente (task-113, veredito GO em 4.8h,
`docs/edge/SOAK_RVB_2026-07-18.md`) é `systemctl --user` + cgroup v2 delegado
(`MemoryMax`/`OOMScoreAdjust` sem privilégio) + **`Linger=yes` já ativo** em
pandora (unit `--user` sobrevive a reboot mesmo sem sessão logada).

⚠️ **Diferença da unit já commitada em `deployments/edge/systemd/recognition-edge-sync.service`:**
aquele arquivo é do bundle task-113 (`deployments/edge/README.md`), assume
`WantedBy=multi-user.target` (sistema, sudo) e tem `ExecStart=-m app`
desatualizado (o entrypoint real, desde o PR-C, é `-m app.main`). Ele foi
**"preparado fora do box"** (o próprio README admite: a sessão de nuvem não
alcançava o Tailscale) e nunca validado contra o REGRAS. Este runbook/unit
(`deploy/edge-sync-agent.service`, `--user`) é o caminho **validado contra o
que o box realmente permite**. Reconciliar os dois arquivos (ou aposentar o
antigo) é pendência separada, fora do escopo do PR-D — sinalizado, não
corrigido aqui.

---

## Instalação (sem sudo — roda como `pandora`)

1. Levar o `edge-sync-agent` para o box, ex. `/opt/recognition/services/edge-sync-agent`
   (mesmo path já usado pela unit de telemetria, task-100).
2. Instalar dependências (venv ou o Python 3.11 já usado pra API — ver
   `docs/edge/REGRAS_PLATAFORMA_JETSON.md` §3.4 "API precisa de Python 3.11"):
   ```bash
   pip3 install -r services/edge-sync-agent/requirements.txt
   ```
3. Rodar o instalador (idempotente, sem sudo):
   ```bash
   cd services/edge-sync-agent/deploy
   ./install.sh install
   ```
   Isso cria `~/.config/systemd/user/edge-sync-agent.service` e, se não
   existir, `~/.config/recognition/edge-sync-agent.env` (chmod 600) a partir
   do `.example`.
4. **Editar** `~/.config/recognition/edge-sync-agent.env`:
   - `DEVICE_ID`/`DEVICE_NAME` — identidade deste device.
   - `ENROLLMENT_TOKEN` — token one-time do admin (`POST
     /api/v1/edge/sites/<site_id>/enrollment-tokens`). Só é necessário no
     1º boot — o enroll é idempotente (pula se já há identidade persistida em
     `EDGE_DEVICE_KEY_PATH`).
   - `EVIDENCE_TRUST_PUBLIC_KEY_PATH`, `TENANT_ID`, `SITE_ID`, `RECORDER_*` —
     ver `services/edge-sync-agent/AGENT.md` (evidence API/gravador, já em
     produção neste daemon desde antes do PR-C).
5. Habilitar:
   ```bash
   systemctl --user enable --now edge-sync-agent
   ```
6. Verificar:
   ```bash
   ./install.sh status
   # ou manualmente:
   systemctl --user status edge-sync-agent
   journalctl --user -u edge-sync-agent -f
   ```

## Pré-requisito: NTP (RS256 exige relógio correto)

`token_manager.get_bearer()` (PR-A) cunha JWT RS256 com `iat`/`exp` de ~5min —
relógio errado quebra enroll/heartbeat/upload silenciosamente (claims
inválidas, não um erro óbvio). Verificar (sem sudo):

```bash
timedatectl status
# ou, direto:
timedatectl show --property=NTPSynchronized --value   # deve ser "yes"
```

Se `NTPSynchronized=no`: JetPack 6.2 (base Ubuntu) normalmente já vem com
`systemd-timesyncd` ativo — checar `systemctl status systemd-timesyncd`
(leitura não exige sudo). **Habilitar/reiniciar o timesyncd exige sudo**
(`sudo systemctl enable --now systemd-timesyncd`) — se estiver desligado,
registrar como pendência pro Vitor (mesma disciplina do REGRAS §3.4 pra outros
itens sudo-gated), não é algo que a instalação autônoma resolve sozinha.

## Desinstalar

```bash
./install.sh uninstall
```

Remove a unit e desabilita; **preserva** `~/.config/recognition/` (tem a
identidade/chave do device — apagar manualmente só se for descomissionar o
device de vez, já que a chave privada não pode ser regerada sem novo
enrollment).

## Logs do edge (unit `--user`)

**Achado 2026-08-08, no box da RVB:** `journalctl --user -u edge-live-view`
responde "No journal files were found". Causa: `/var/log/journal` não existe
neste box → journald com `Storage=auto` (default; `journald.conf` sem nenhum
override) cai pra armazenamento **volátil** em `/run/log/journal`, e esse
diretório é `root:systemd-journal` sem ACL de leitura pro usuário `pandora` —
o journal do usuário fica ilegível. **Sem sudo não dá pra corrigir o
journald.**

**Solução aplicada (sem sudo):** `edge-live-view.service` grava
`StandardOutput`/`StandardError` direto em arquivo em vez de depender do
journal (`ExecStartPre=mkdir -p %h/logs` +
`StandardOutput=append:%h/logs/edge-live-view.log`):

```bash
tail -f ~/logs/edge-live-view.log
```

**Rotação:** `edge-log-rotate.timer` (`OnCalendar=daily`, `Persistent=true`)
dispara `edge-log-rotate.service` (oneshot), que faz **copytruncate** em
qualquer `~/logs/*.log` acima de 50MB — `cp` pra `.1` sobrescrevendo +
`truncate -s 0` do original. Copytruncate é obrigatório aqui: o fd que a unit
em execução mantém aberto por `append:` continua apontando pro mesmo inode
depois de um rename simples, então um `mv` deixaria a unit escrevendo pra
sempre num arquivo sem nome. Instalado e **habilitado automaticamente** por
`./install.sh install` (não depende de `edge-sync-agent.env`, então não tem
motivo pra ficar como passo manual como as outras units).

**Journal persistente de verdade (exige sudo — guardado pra quando o Vitor
quiser rodar; decisão do Vitor 2026-08-08: "pega só o log em arquivo por
enquanto; guarda os comandos de sudo"):**

```bash
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal
sudo usermod -aG systemd-journal pandora
sudo systemctl restart systemd-journald
# relogar (ou reboot) para o grupo valer; depois:
journalctl --user -u edge-live-view -f
```

**Fora de escopo:** os sinks de telemetria remota continuam desligados
(`docs/edge/DIAGNOSTICO_OBSERVABILIDADE_2026-07-21.md`) — resolver isso é
tema separado; este runbook só tira o edge de "caixa preta" localmente
(log legível no próprio box, sem depender de journald nem de rede).

## Gate 1.6 (validação real no pandora — pendente, é OPS/Vitor)

O que este PR-D entrega é código/config; a validação abaixo **não foi feita
por esta sessão** (não há acesso ao box físico) — fica como pendência
explícita, é o gate 1.6 do `GUIA_EXECUCAO_RVB.md`:

- [ ] Serviço sobe após `systemctl --user enable --now` e **sobrevive a reboot
      real** do Jetson (prova o `Linger=yes` na prática, não só por doc).
- [ ] Depois de subir: heartbeat volta a aparecer no admin DEV
      (`GET /api/v1/edge/sites/<site_id>/heartbeats`).
- [ ] `timedatectl show --property=NTPSynchronized --value` → `yes`.
- [ ] `journalctl --user -u edge-sync-agent` sem loop de erro (enroll ok,
      loops supervisionados sem crash-loop constante).

## Fora de escopo deste PR-D

OTA (canal de software) · lease de licença (ADR-0057 item 4.2) · reconciliar
`deployments/edge/systemd/recognition-edge-sync.service` com este runbook.
