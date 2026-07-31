# Runbook — Rotacionar a credencial do gravador (NVR) de um site

**Origem:** incidente de 2026-07-31 na RVB — a senha do NVR vazou em log de aplicação (stderr do ffmpeg) e em
chat. O PR #251 impede vazamento **futuro** (redação na origem), mas não desfaz o que já vazou: a credencial
exposta deve ser considerada **comprometida**.

---

## ⚠️ Não só trocar a senha do `Admin` — criar um usuário de serviço

A credencial vazada era a do **`Admin` do NVR**, com acesso total ao gravador. O sistema **nunca** deveria usar
conta admin: o correto é um usuário dedicado, **só de visualização/stream** (menor privilégio).

Se vazar de novo, o estrago é "alguém assiste ao vídeo" — não "alguém administra o gravador do cliente".

> **Gate de go-live (bloqueante):** o sistema não usa conta admin de gravador. Usuário de serviço com menor
> privilégio, sempre.

---

## Onde a credencial vive (3 lugares — todos precisam mudar)

| # | Onde | Quem consome |
|---|---|---|
| 1 | **`.env` do box** (`~/.config/recognition/edge-sync-agent.env`, chmod 600) | live view + coletor de frames — **é o que restaura o serviço** |
| 2 | `public.recorders` (cifrado, Fernet) | extração NVR cloud-side (ADR-0034) |
| 3 | `public.cameras` (uma linha por câmera, cifrado) | build de URL RTSP na nuvem (`camera_service`) |

---

## Ordem SEM downtime (usuário novo antes de matar o antigo)

> ⚠️ **Box ANTES da nuvem.** O live view e o coletor leem do `.env` do box (`recorder_factory.build_recorder_client_from_env`),
> **não** do cadastro da nuvem. Fazendo o box primeiro, o serviço volta antes — e se o cadastro da nuvem falhar,
> o live view não cai junto.

1. **No NVR:** criar usuário de serviço (ex.: `logikos-svc`) com senha forte nova e permissão **mínima**
   (live/playback; sem admin, sem config). **Manter o `Admin` ativo por enquanto.**
2. **No box (pandora) — PRIMEIRO:** atualizar `RECORDER_USERNAME`/`RECORDER_PASSWORD` no `.env` (chmod 600) →
   `systemctl --user restart` das units (`edge-sync-agent`, `edge-live-view`, `edge-frame-collector`).
3. **No cadastro da nuvem — DEPOIS:** atualizar `public.recorders` **e** `public.cameras` (uma por câmera) via API
   (`PUT /api/v1/recorders/<id>` e `PUT /api/cameras/<id>` com `username`/`password`).
4. **Verificar:** live view volta a tocar · heartbeat seguindo 201 · coletor subindo frames.
5. **Só então:** trocar a senha do `Admin` no NVR (ou desabilitá-lo para uso externo). A partir daqui a credencial
   vazada não vale mais nada.
6. **Conferir que não vaza mais:** nos logs, a URL RTSP deve aparecer como `rtsp://user:***@host`.

### 🔐 Ao automatizar

- Senha via `getpass`, passada por **stdin do ssh** — **nunca em `argv`**. Argumento de processo é visível no `ps`
  para qualquer usuário do host; usar `argv` seria repetir exatamente o erro que este runbook existe para corrigir.
- Nunca imprimir, logar ou commitar a senha.
- Se a etapa do box falhar, **parar antes** de mexer na nuvem — não deixar os dois lados divergentes.

---

## Se o cliente não permitir criar usuário no NVR

Fallback: trocar a senha do `Admin` mesmo. A ordem inverte e **há janela de indisponibilidade** — entre a troca no
NVR e o restart das units, o live view e o coletor ficam com credencial inválida:

`NVR` → `.env` do box + restart → cadastro da nuvem

Fazer em janela combinada com o cliente, avisando que o live view cai por alguns minutos.

---

## Registrar a cada rotação

- Credencial antiga = **comprometida**. Não reutilizar em nenhum outro equipamento ou site.
- Data, motivo e quem executou.
