# Pedidos ao backend — pista F5 (Estúdio + Admin + Acesso + Kiosk/TV)

> Pedidos formais levantados durante a migração F5 (SR1 Estúdio fechada,
> PRs #572–#586). Cada item: o que falta, por quê, e quem decide. Não é
> trabalho desta rodada — é registro para priorização.

1. **Share links** (Admin Plataforma → detalhe do tenant; Evento Detalhe). O
   bundle de design F5 desenha "Compartilhar com expiração 1h/24h/7d +
   permissão ver/ver+baixar" nas duas telas. Zero backend hoje — nenhuma rota
   de link assinado com escopo/expiração para evidência ou tenant.

2. **Login devolver `force_password_reset`**. A tela de troca obrigatória de
   senha (Acesso, F5 SR2) precisa saber, na resposta do login, se o usuário
   tem que trocar a senha antes de continuar. Hoje `get_by_email` não
   seleciona essa coluna — o claim nunca chega ao front mesmo quando o banco
   já marca o usuário.

3. **E-mail de reset apontar pro fluxo novo**. `password_reset_service.py:69`
   monta o link para `/reset-password` (rota antiga). Quando o flip para o
   front novo acontecer, o e-mail já disparado antes do flip continua levando
   para lá — elo aberto que precisa de decisão (versão do link no token, ou
   redirect na rota antiga).

4. **Parede kiosk POR SITE**. Reforço do item 2 das DECISOES de 29/08: o
   kiosk hoje não tem recorte por site edge — cliente com mais de um site
   não consegue montar parede isolada por local.

5. **TV por site `/tv/:site`**. Rota agregada + WebSocket para um painel
   "modo TV" (grade full-screen sem menu) escopado a um site — não construído
   nesta pista (decisão: não fazer TV agora, só registrar o pedido).

6. **Fila por incerteza — decisão de produto**. `?ordenar=incerteza` já
   existe pronto no backend
   (`services/api/app/api/v1/training/image_handlers.py` +
   `infrastructure/database/repositories/frame_repository.py`, com teste em
   `test_fila_por_incerteza.py`), mas NENHUM dos dois fronts chama. Não é bug
   nem dívida de paridade — é decidir se o produto quer ligar esse filtro na
   galeria do Estúdio (`app/estudio/Dados.tsx`).

7. **Avaliação por câmera para os gráficos da prancha Modelos**.
   `model_evaluations` não tem `camera_id` — os gráficos de drift/avaliação
   por câmera que a prancha do R4 (catálogo de modelos) desenha não têm como
   ser construídos sem essa coluna.

8. **🔒 SEGURANÇA (needs-human) — `GET /api/training/jobs` vaza
   `callback_token` e escopa por `user_id`, não por tenant**
   (`services/api/app/api/v1/training/job_handlers.py`, `list_jobs_handler`,
   linha ~257). Comparando com `get_job_status_handler` (linha 277) e
   `stop_job_handler` (linha 390), que fazem `job.pop("callback_token", None)`
   antes de responder, a listagem não faz esse expurgo — quem lista os jobs
   recebe o token usado pelo callback da GPU remota. Escopo por `user_id` (não
   `tenant_id`) também diverge do resto do domínio (ADR-0004/C-01). Achado
   pelo cético durante a auditoria do Estúdio; **registrado aqui, não
   corrigido nesta rodada** — é código de `services/api`, fora do escopo desta
   pista (docs + carimbos).

9. **Listagem e revogação de dispositivos reivindicados** (Admin →
   Dispositivos, F5 SR2 PR-3). O desenho mostra uma tabela
   dispositivo/vínculo/tipo/status com botão "Revogar" por linha.
   `services/api/app/api/v1/devices/routes.py` só tem `POST /claim-codes`
   (gera código) e `POST /claim` (público, o dispositivo resgata); o
   `DeviceClaimRepository` (`infrastructure/database/repositories/
   device_claim_repository.py`) só expõe `create`, `redeem` e `get_status`
   (este último documentado como "nunca expor na API"). Sem `GET` de
   listagem nem endpoint de revogação, a tabela fica fora da tela — só a
   geração de código ficou de pé.

10. **`exportAuditLog` sem `date_from`/`date_to`** (Admin → Auditoria, F5 SR2
    PR-3). `GET /v1/admin/audit-log/export` (`routes.py:2264`) aceita período,
    mas `adminService.exportAuditLog` só encaminha `tenant_id`/`action` — o
    CSV exportado nunca respeita o filtro de período escolhido na tela
    (sempre as últimas 10 mil linhas). Extensão de duas linhas no wrapper;
    fora do escopo desta pista (`modules/**` intocável nesta PR).
