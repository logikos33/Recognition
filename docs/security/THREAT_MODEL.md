# Threat Model — Recognition (STRIDE)

## Escopo e método

Este documento aplica STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure,
Denial of Service, Elevation of Privilege) a **duas fronteiras de confiança** do produto:

1. **Edge↔Cloud**: câmera/DVR na LAN do cliente → Mini PC de edge → API cloud (Railway).
2. **Isolamento multi-tenant**: tenant A não pode, sob nenhuma circunstância, ler ou
   escrever dados do tenant B.

Cada categoria STRIDE traz uma ameaça concreta nessa fronteira e o mecanismo **já existente
no código/ADRs** (citado por arquivo ou número de ADR) que mitiga — ou, quando não há
mitigação verificável, isso é dito explicitamente e listado em "Gaps conhecidos" ao final.
Nenhuma mitigação foi inventada: tudo aqui foi confirmado lendo o código real deste
worktree, não inferido de documentação ou de conhecimento prévio (parte do CLAUDE.md
deste repo está desatualizada quanto a paths — `backend/`/`frontend/` não existem mais;
os paths reais são `services/api/app/` e `apps/frontend/`).

**Fora de escopo**: segurança física dos Mini PCs, segurança da rede LAN do cliente
além da câmera/MikroTik, compliance LGPD (ver `docs/security/LGPD_PRIVACIDADE_CFTV.md`),
licenciamento de dependências (ver `scripts/check_license_gate.py` — controle de
supply-chain, não de segurança de runtime, citado aqui só de passagem).

---

## Fronteira 1 — Edge↔Cloud

Contexto real: câmeras (Hikvision/Intelbras) nunca são expostas à internet
(port-forward é **rejeitado por design**, ADR-0020, opção C, motivo: lockout
anti-brute-force das próprias câmeras). O Mini PC de edge disca **outbound** para um
hub WireGuard via MikroTik (ADR-0020). O `edge-sync-agent` que consumiria essa
conectividade para sincronizar detecções está **marcado como placeholder, não
implementado** (`services/edge-sync-agent/AGENT.md`: "Este serviço ainda não está
implementado... Implementação: Fase 4"). Já implementados no lado cloud: enrollment,
verificação de token e endpoints `/api/v1/edge/*` (`services/api/app/core/device_auth.py`,
`services/api/app/api/v1/edge/routes.py`, `edge_commands/routes.py`, `edge_events/routes.py`).

| STRIDE | Ameaça | Mitigação existente (arquivo/ADR) | Status |
|---|---|---|---|
| **Spoofing** | Device malicioso finge ser um Mini PC legítimo para injetar heartbeats/eventos falsos | JWT **RS256 assimétrico**: chave privada só no cloud, dispositivo prova posse via assinatura verificada contra `public_key_pem` armazenada em `device_tokens` (ADR-0019; `services/api/app/core/device_auth.py:79-102`, `verify_device_token`). Enrollment usa claim code de uso único, TTL 15 min, hash SHA-256 armazenado (`generate_claim_code`/`hash_claim_code`, `device_auth.py:39-44`) — token bruto nunca persistido. | Mitigado |
| **Tampering** | Comando RTSP malicioso força FFmpeg a executar código / acessar host arbitrário | `RTSPUrlValidator` — 4 camadas: tamanho máx., blocklist de caracteres de shell-injection, whitelist de scheme (`rtsp/rtsps/http/https`), rejeição de loopback/link-local/multicast/reservado (`services/api/app/core/validators.py:72-140`) | Mitigado |
| **Tampering** | Modelo YOLO adulterado é entregue ao edge (supply-chain do artefato de inferência) | Documentado como fluxo desejado — `model_manager.py` deveria validar SHA256 do `.pt/.engine` antes de trocar o modelo em produção (`services/edge-sync-agent/AGENT.md:101-114`) | **Não implementado** — o `edge-sync-agent` inteiro é placeholder; não há código real fazendo esse download/verificação hoje |
| **Repudiation** | Operador nega ter executado uma ação destrutiva via device (ex.: comando de stream) | `device_tokens` guarda `revoked_by`/`revocation_reason` e enrollment é rastreado por `claim_id` (`shared/python/recognition_shared/device.py`); heartbeats gravados em `edge_heartbeats`. Não há, porém, um log de auditoria correlacionando comando→operador→device de forma pesquisável fim-a-fim. | Parcial |
| **Information Disclosure** | Tráfego edge↔cloud interceptado na rede do cliente expõe credenciais de câmera / frames | Transporte roda sobre overlay **WireGuard** via MikroTik, hub-and-spoke, sem porta aberta no cliente (ADR-0020). Escopos do device token limitam o que um token comprometido pode ler (`heartbeat:write`, `detection:write`, `config:read`, `stream:report` — `AGENT.md:130-139`, `DeviceTokenScope` em `shared/python/recognition_shared/enums.py`) | Mitigado (transporte); ver gap de escopo abaixo |
| **Denial of Service** | Device (ou credencial de device vazada) inunda a API cloud de heartbeats/eventos | Flask-Limiter ativo com storage Redis em produção (`services/api/app/extensions.py:15`, `app/__init__.py:83-85`) — mitigação genérica de rate limit na API; não há evidência de limite **por device_id** dedicado a `/api/v1/edge/*` | Parcial |
| **Elevation of Privilege** | Device com escopo restrito (ex.: só `heartbeat:write`) usa o mesmo token para chamar endpoints de outro escopo (ex.: `config:read`, comandos de stream) | `verify_device_token` retorna `DeviceClaims` com `scopes: list[DeviceTokenScope]` (`shared/python/recognition_shared/device.py:24-32`), mas o helper usado pelas rotas, `get_device_context()`, **descarta os scopes** e retorna só `(tenant_id, site_id, device_id)` (`services/api/app/core/device_auth.py:104-146`). Não existe `require_scope`/checagem de `claims.scopes` em nenhuma rota grepada (`edge/routes.py`, `edge_commands/routes.py`, `edge_events/routes.py`). | **Não mitigado — gap real** |

---

## Fronteira 2 — Isolamento multi-tenant

Contexto real: schema-per-tenant no PostgreSQL (ADR-0004) — tabelas de dados
operacionais (cameras, alerts, frames, detections, models) vivem em `{tenant_schema}.*`,
tabelas de infraestrutura global vivem em `public.*` com `tenant_id NOT NULL`
(Constitution C-01). `get_tenant_id()`/`get_tenant_schema()`/`get_role()` em
`services/api/app/core/auth.py` **lançam `AuthenticationError` se o claim estiver
ausente do JWT** — sem fallback silencioso (ADR-0017, camada 1, corrigido após o
incidente do tenant `default` documentado no próprio ADR).

| STRIDE | Ameaça | Mitigação existente (arquivo/ADR) | Status |
|---|---|---|---|
| **Spoofing** | Usuário forja/edita um JWT para alegar pertencer a outro `tenant_id`/`tenant_schema` | JWT assinado (flask-jwt-extended, HS256 para usuários — separado dos device tokens RS256 conforme `AGENT.md:137`); claims obrigatórios validados a cada request via `get_tenant_id()`/`get_tenant_schema()` (`services/api/app/core/auth.py:87-124`) | Mitigado |
| **Tampering** | Query sem filtro de tenant permite update/delete cross-tenant | **Gap real confirmado por leitura de código**: `AlertRepository.acknowledge(alert_id)` executa `UPDATE alerts SET acknowledged = TRUE WHERE id = %s RETURNING *` **sem cláusula `AND tenant_id = %s`** (`services/api/app/infrastructure/database/repositories/alert_repository.py:93-98`), e a rota `POST /<alert_id>/acknowledge` chama esse método passando só o `alert_id`, sem `tenant_id` (`services/api/app/api/v1/alerts/routes.py:126-129`). Compare com o método vizinho `get_snapshot_evidence_key`, que já filtra `WHERE id = %s AND tenant_id = %s` justamente para evitar enumeração cross-tenant (comentário no próprio arquivo, linhas 82-91). | **Não mitigado — gap real** (qualquer usuário autenticado de qualquer tenant pode reconhecer/mutar um alerta de outro tenant sabendo ou adivinhando o UUID) |
| **Repudiation** | Ação administrativa cross-tenant (ex.: superadmin em impersonation) não é rastreável | ADR-0025 prevê "super-admin da plataforma precisa impersonar qualquer tenant para suporte", mas não há, nesta leitura, tabela de audit log dedicada para esse fluxo — apenas roles/permissions JSONB por tenant (`docs/decisions/adr/0025-roles-permissions-by-tenant.md`) | **Não mitigado** |
| **Information Disclosure** | Endpoint revela a um atacante que um recurso de outro tenant existe (enumeration) | Documentado como princípio em `SECURITY.md`: "acesso cross-tenant retorna 404 (nunca 403 — não vazamos existência)". **Confirmado parcialmente, mas com contra-exemplo real**: `alerts/routes.py:134` segue o padrão (`error("Alerta não encontrado", 404)`); porém `CameraService.get_camera/update_camera/delete_camera` levantam `AuthorizationError` (HTTP **403**, `services/api/app/core/exceptions.py:45-49`) quando `camera["tenant_id"] != tenant_id`, não `NotFoundError` (404) — ver `services/api/app/domain/services/camera_service.py:168-171,239-240,338-339,428-429` e `crud_handlers.py:150-151`. Isso vaza a existência do `camera_id` de outro tenant via diferença de status code. | **Parcialmente mitigado — inconsistente entre domínios** |
| **Denial of Service** | Um tenant abusa de endpoints caros (export, treino) e degrada outros tenants (banco compartilhado) | Rate limiting existe na camada HTTP (Flask-Limiter, Redis) mas por IP, não por `tenant_id` (`extensions.py:15`); schema-per-tenant isola dados mas não isola I/O de um único Postgres compartilhado (ADR-0004 reconhece isso implicitamente: "sem impacto de performance até centenas de tenants") | Parcial |
| **Elevation of Privilege** | Usuário `operator` de um tenant escala para `admin`/`superadmin`, ou role customizado (ADR-0025) herda permissão indevida | `require_training_role()` consulta registry canônico de permissões (`app/core/permissions.py`) em vez de hardcode duplicado, evitando duas fontes de verdade (`services/api/app/core/auth.py:182-286`); `admin_required()` em `auth.py` é explicitamente documentado como **não** verificando role sozinho — delega ao service/repository, e o próprio docstring alerta: "Qualquer uso assumindo que ele bloqueia não-admins é furo de segurança" (`services/api/app/core/auth.py:65-78`) | Mitigado nos pontos que usam o registry; **depende de disciplina do autor da rota** nos pontos que ainda usam `admin_required` cru |

---

## Gaps conhecidos

Lista honesta do que este documento encontrou **sem mitigação verificável** no código
atual — não é um problema do modelo de ameaças, é o resultado dele:

1. **Cross-tenant write em `alerts.acknowledge`** — `AlertRepository.acknowledge()` não
   filtra por `tenant_id` (`alert_repository.py:93-98`); a rota também não passa
   `tenant_id`. Qualquer usuário autenticado pode marcar como reconhecido um alerta de
   outro tenant. Este é o gap de maior severidade encontrado nesta análise.
2. **Inconsistência 404-vs-403 no domínio de câmeras** — contraria o princípio
   declarado em `SECURITY.md` ("nunca 403 — não vazamos existência"). `camera_service.py`
   levanta `AuthorizationError` (403) em vez de `NotFoundError` (404) para acesso
   cross-tenant em get/update/delete de câmera, vazando existência do recurso.
3. **Escopos de device token (`DeviceTokenScope`) não são verificados por rota** —
   `get_device_context()` autentica o device (assinatura, revogação, tenant/site) mas
   descarta `claims.scopes` antes de retornar; nenhuma rota grepada em
   `api/v1/edge*` checa escopo. Um token com escopo mínimo tem, na prática, acesso a
   qualquer endpoint de device.
4. **`edge-sync-agent` inteiro é placeholder** (`AGENT.md`: "ainda não está
   implementado", Fase 4) — a validação de SHA256 de modelo YOLO antes de troca em
   produção, o buffer SQLite resiliente e a mirror API LAN existem só como design;
   nenhuma dessas mitigações de Tampering/DoS descritas no ADR está rodando em
   produção hoje.
5. **Sem audit log dedicado para impersonation/superadmin cross-tenant** — ADR-0025
   menciona o requisito de suporte mas não há tabela/mecanismo de log correlacionável
   encontrado nesta leitura.
6. **Rate limiting é por IP, não por tenant** — um tenant com tráfego elevado
   (legítimo ou não) pode degradar a experiência de outros tenants no mesmo Postgres
   compartilhado; não há quota por `tenant_id`.
7. **Débito técnico já registrado no CLAUDE.md deste repo** (não reconfirmado
   linha a linha aqui, mas relevante ao escopo): `count_validated()` e
   `get_annotated_by_video()` em `frame_repository.py` não filtram por `tenant_id`
   — mesma classe de gap do item 1, em outro repositório.

Nenhum item acima foi corrigido como parte deste PR — o objetivo deste documento é
apenas mapear a superfície de ameaça e ser honesto sobre o que ainda não está coberto.
