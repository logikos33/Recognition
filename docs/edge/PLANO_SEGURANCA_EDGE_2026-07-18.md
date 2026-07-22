# Trilha de Segurança — Edge e multi-tenancy

**Data:** 2026-07-18 · **Prioridade:** ALTA · **Trilha:** separada do plano de controle (decisão do Vitor)
**Regra:** `risk:security` **para a fila** para revisão humana. Nada aqui promove para staging/main.

> Achados de varredura do repo real em 2026-07-18. Cada item tem arquivo e linha.
> **Nenhum destes é hipotético** — todos foram confirmados no código.

---

## S1 — Escopos de device declarados mas NUNCA aplicados 🔴

**Onde:** `shared/python/recognition_shared/enums.py` (`DeviceTokenScope`) · `edge/routes.py:603`

`DeviceClaims.scopes` é validado pelo Pydantic e `_DEFAULT_SCOPES` é ecoado na resposta de enrollment. Mas
`grep scopes` em `services/api/app` retorna **um único hit funcional** — o eco. **Não existe `require_scope`.**

**Impacto:** um device enrolado com escopo só de heartbeat pode chamar **qualquer** endpoint de device. O
princípio de menor privilégio do ADR-0019 existe no papel e não no código.

**Correção:** decorator `@require_scope(...)` aplicado em toda rota de device; negar por padrão. Testes que
provem que um token sem o escopo recebe 403.

---

## S2 — `serve_hls` sem checagem de tenant 🔴

**Onde:** `cameras/stream_handlers.py:122`

Rota pública **por design** ("hls.js cannot send auth headers"). Valida UUID e filename, mas **não valida
tenant**. Quem souber o UUID de uma câmera lê os segmentos de vídeo — de qualquer tenant.

**Impacto:** vazamento de vídeo cross-tenant. UUID não é segredo (aparece em logs, URLs, respostas de API).

**Correção possível:** token de playback assinado e de vida curta na URL, ou cookie de sessão scoped ao tenant,
ou proxy autenticado. **Não** deixar a rota nua. Decidir a abordagem antes de implementar.

---

## S3 — `toggle_module_class` sem checagem de tenant 🔴

**Onde:** `modules/routes.py` — `PATCH /<code>/classes/<class_id>`

Recebe `class_id` e alterna direto, **sem verificar a que tenant a classe pertence**.

**Impacto:** um tenant pode ligar/desligar classe de detecção de outro. Viola C-01. Deve ser **404**, não 403
(não vazar existência).

---

## S4 — `/api/streams/status` público, sem tenant ⚠️

**Onde:** `streams/routes.py` (44 linhas)

Inspeciona workers Celery via Redis e **sempre retorna 200** (mascara erro). Expõe topologia de workers
publicamente.

**Correção:** exigir auth, ou remover a rota se não tiver consumidor.

---

## S5 — Rotas sem gate de admin ⚠️

| Rota | Onde | Problema |
|---|---|---|
| `GET /edge/commands` | `edge_commands/routes.py` | JWT + tenant, mas **sem gate de admin** — qualquer usuário lista comandos do site |
| `PATCH /site-gateways/<id>/status` | `site_gateways/routes.py` | idem, sem gate de admin |

---

## S6 — Dois fluxos de enrollment incompatíveis ⚠️

**Onde:** `devices/routes.py` (claim code → JWT HS256 `token_type=device_enrollment`) vs
`edge/routes.py` `/enroll` (token opaco, SHA-256 contra `enrollment_tokens.token_hash`)

`POST /devices/claim` é **público** (rate-limit 10/min) e emite um token que `/edge/enroll` **não aceita**.
Superfície de ataque a mais, sem função — o caminho `devices/` é órfão (sem consumo no frontend).

**Correção:** escolher um fluxo, aposentar o outro com evidência de que nada o consome.

---

## S7 — Drift ADR-0019 ↔ implementação ⚠️

| ADR-0019 diz | Realidade |
|---|---|
| `/api/v1/edge/enrollment/redeem` e `/api/v1/edge/auth/rotate` | Só existe `/enroll`. **`/auth/rotate` não existe** — sem rotação de chave sem re-enrollment |
| API retorna JWT RS256 assinado pela **chave privada do cloud** | Device gera o próprio par, envia `public_key_pem`; `/enroll` retorna só `{tenant_id, site_id, device_id, scopes}`. **Device auto-assina** |

O modelo implementado funciona (e a revogação é checada **antes** da verificação de assinatura — correto), mas é
**o oposto** do que o ADR descreve. **Corrigir o ADR para reproduzir a realidade**, ou mudar o código — mas não
deixar os dois divergindo, porque a próxima sessão vai confiar no ADR.

---

## S8 — Segredo commitado 🔴 (herdado, bloqueante de go-live)

Senha `admin@rvb.com.br` commitada no git durante o embarque do soak. **Rotacionar pela aplicação** — nunca por
shell/SQL, nunca commitar a nova. Avaliar se o segredo precisa ser expurgado do histórico.

---

## Ordem sugerida

1. **S1** (escopos) — é a fundação de toda a autorização de device; quanto mais rotas de device nascerem no plano
   de controle, mais caro fica depois.
2. **S3** e **S5** — checagem de tenant/admin faltando; correção pequena, risco alto.
3. **S2** (HLS) — precisa de decisão de abordagem antes de código.
4. **S8** — depende de ação do Vitor pela app.
5. **S6**, **S7**, **S4** — higiene e reconciliação.

**Regra transversal:** cross-tenant → **404**, nunca 403 (C-01, não vazar existência).
