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
| **Elevation of Privilege** | Device com escopo restrito (ex.: só `heartbeat:write`) usa o mesmo token para chamar endpoints de outro escopo (ex.: `config:read`, comandos de stream) | Os escopos (`DeviceTokenScope`) são emitidos e trafegam nas claims do token, mas a checagem de escopo por rota ainda não está implementada de forma consistente nas rotas de edge. **Detalhe de código e correção rastreados internamente (não publicados aqui)** — ver task de acompanhamento. | **Não mitigado — gap real, correção em andamento** |

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
| **Tampering** | Query sem filtro de tenant permite update/delete cross-tenant | **Gap real confirmado por leitura de código**: uma mutação no domínio de alertas não aplica filtro de `tenant_id` na cláusula `WHERE`, ao contrário do padrão usado no restante do repositório (que sempre filtra por `tenant_id` para evitar enumeração cross-tenant). **Localização exata e correção rastreadas internamente (não publicadas aqui)** — ver task de acompanhamento. | **Não mitigado — gap real, correção em andamento** |
| **Repudiation** | Ação administrativa cross-tenant (ex.: superadmin em impersonation) não é rastreável | ADR-0025 prevê "super-admin da plataforma precisa impersonar qualquer tenant para suporte", mas não há, nesta leitura, tabela de audit log dedicada para esse fluxo — apenas roles/permissions JSONB por tenant (`docs/decisions/adr/0025-roles-permissions-by-tenant.md`) | **Não mitigado** |
| **Information Disclosure** | Endpoint revela a um atacante que um recurso de outro tenant existe (enumeration) | Documentado como princípio em `SECURITY.md`: "acesso cross-tenant retorna 404 (nunca 403 — não vazamos existência)". **Confirmado parcialmente, mas com contra-exemplo real**: o domínio de alertas segue o padrão corretamente (404 em qualquer caso cross-tenant); pelo menos um outro domínio ainda responde 403 em vez de 404 para acesso cross-tenant, vazando a existência do recurso via diferença de status code. **Localização exata e correção rastreadas internamente (não publicadas aqui)** — ver task de acompanhamento. | **Parcialmente mitigado — inconsistente entre domínios, correção em andamento** |
| **Denial of Service** | Um tenant abusa de endpoints caros (export, treino) e degrada outros tenants (banco compartilhado) | Rate limiting existe na camada HTTP (Flask-Limiter, Redis) mas por IP, não por `tenant_id` (`extensions.py:15`); schema-per-tenant isola dados mas não isola I/O de um único Postgres compartilhado (ADR-0004 reconhece isso implicitamente: "sem impacto de performance até centenas de tenants") | Parcial |
| **Elevation of Privilege** | Usuário `operator` de um tenant escala para `admin`/`superadmin`, ou role customizado (ADR-0025) herda permissão indevida | `require_training_role()` consulta registry canônico de permissões (`app/core/permissions.py`) em vez de hardcode duplicado, evitando duas fontes de verdade (`services/api/app/core/auth.py:182-286`); `admin_required()` em `auth.py` é explicitamente documentado como **não** verificando role sozinho — delega ao service/repository, e o próprio docstring alerta: "Qualquer uso assumindo que ele bloqueia não-admins é furo de segurança" (`services/api/app/core/auth.py:65-78`) | Mitigado nos pontos que usam o registry; **depende de disciplina do autor da rota** nos pontos que ainda usam `admin_required` cru |

---

## Gaps conhecidos

Lista honesta do que este documento encontrou **sem mitigação verificável** no código
atual — não é um problema do modelo de ameaças, é o resultado dele:

1. **Cross-tenant write numa mutação do domínio de alertas** — não filtra por
   `tenant_id` na cláusula `WHERE`, ao contrário do padrão do restante do repositório.
   Qualquer usuário autenticado pode mutar um recurso de outro tenant sabendo/adivinhando
   o identificador. Este é o gap de maior severidade encontrado nesta análise.
   **Correção rastreada internamente** (localização exata não publicada aqui).
2. **Inconsistência 404-vs-403 no domínio de câmeras** — contraria o princípio
   declarado em `SECURITY.md` ("nunca 403 — não vazamos existência"): pelo menos um
   fluxo de acesso a câmera de outro tenant responde 403 em vez de 404, vazando
   existência do recurso. **Correção rastreada internamente** (localização exata não
   publicada aqui).
3. **Escopos de device token (`DeviceTokenScope`) não são verificados de forma
   consistente por rota** — os escopos existem e trafegam nas claims, mas a checagem
   por rota nas APIs de edge ainda não está completa. Um token com escopo mínimo pode,
   em alguns endpoints, ter acesso além do pretendido. **Correção rastreada
   internamente** (localização exata não publicada aqui).
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
   linha a linha aqui, mas relevante ao escopo): há queries de validação em outro
   repository que não filtram por `tenant_id` — mesma classe de gap do item 1, em
   outro domínio.

Nenhum item acima foi corrigido como parte deste PR — o objetivo deste documento é
apenas mapear a superfície de ameaça e ser honesto sobre o que ainda não está coberto.
