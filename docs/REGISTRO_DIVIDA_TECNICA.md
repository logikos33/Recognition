# Registro de dívida técnica — Recognition

**Levantado em:** 2026-08-02 · **Método:** varredura do código real + docs, não de memória (C-04)

> ⚠️ **Limitação desta varredura — ler antes de confiar em qualquer item.**
> A árvore local está na branch `fix/admin-users-null-tenant-id` e as refs estão **defasadas**: o último merge
> visível na `develop` é o **#238 (29/jul)**. Os PRs **#246, #250, #252, #255, #257** — que trouxeram o endpoint de
> segmento do live view, a guarda de câmera alimentada pelo edge, o token de playback HLS e o recorte por pessoa —
> **não estão nesta cópia**. Itens marcados 🔍 não puderam ser verificados e precisam ser reconferidos contra a
> `develop` real antes de virar tarefa.

---

## P0 — Crítico (segurança / perda de dado)

### D-01 · Credenciais em texto claro no repositório, e a senha se auto-restaura
**Onde:**
- `infra/migrations/040_reset_superadmin_password.sql:2` — senha do superadmin em comentário
- `infra/migrations/025_superadmin_viewer_role.sql:26-27` — senha padrão **e** o comando exato que gera o hash
- `infra/migrations/027_superadmin_vitor.sql:34-42` — superadmin hardcoded com `ON CONFLICT DO UPDATE password_hash`
- `services/api/app/api/v1/auth/routes.py:90` — credencial no exemplo do Swagger
- `scripts/smoke_test.sh:19` — credencial no payload
- `apps/frontend/dist/assets/index-CX1rji7l.js:186` — bundle **commitado** com `"🔑 Acesso padrão: …"`

**Por que é o item nº 1:** as migrations rodam **a cada boot** do `SERVICE_TYPE=api`. O `ON CONFLICT DO UPDATE
password_hash` significa que **trocar a senha pelo app não adianta — o próximo deploy reverte**. Não é uma senha
vazada; é uma senha vazada que se reinstala sozinha.

**Correção:** superadmin novo criado **fora de migrations**; migration aditiva desativando as contas antigas;
revogar sessões (incluindo `jti` no blocklist do Redis — `is_active=false` **não** invalida JWT já emitido);
provar que a senha antiga dá 401 e o token antigo dá 401. Remover o bloco de "acesso padrão" da tela de login.

**Verificar:** a tela de login **viva** mostra a credencial? O bundle está commitado, mas o Railway builda do fonte —
confirmar na tela antes de concluir.

---

### D-02 · Senha de tenant novo é derivável do slug
`services/api/app/api/v1/admin/routes.py:299`
```python
temp_password = f"EpiMonitor@{slug[:4].upper()}2024!"
```
Quem souber o slug de um tenant sabe a senha do admin dele. Vetor **cross-tenant**, que é justamente o que a
ADR-0004/C-01 existe para impedir.

**Atenuante:** os outros dois fluxos já usam `secrets.token_urlsafe(12)` (`:753`, `:992`) — é resíduo esquecido, não
padrão do sistema. Correção é trocar uma linha pela que já existe ao lado.

---

### D-03 · Fallback silencioso de storage — o pool de anotação pode evaporar
`services/api/app/infrastructure/storage/local_storage.py:109-127`

Faltando `R2_ENDPOINT`/`R2_KEY`/`R2_SECRET`, `get_storage()` devolve `LocalStorage` no **disco efêmero do
container**. O upload retorna **201**, e a imagem some no próximo deploy. **Sem um único `logger.warning`.**

**Por que importa agora:** é exatamente o caminho dos frames de coleta da RVB. Coletar 500 frames, fazer deploy e
perder tudo é um cenário real, e o sistema não avisaria.

**Detalhe que o doc antigo errava:** `R2_BUCKET` **não** faz parte da condição — tem default `"epi-monitor"`
(`:120`). Sem ele o upload vai pro R2, num bucket possivelmente errado. Falha diferente, igualmente silenciosa.

**Correção:** falhar alto no startup se `DEPLOYMENT_MODE` de produção e R2 incompleto. Nunca degradar em silêncio.

---

### D-04 · Migrations: colisão de numeração e diretório duplicado
- **6 arquivos no prefixo `052`**: `branding_tenants`, `camera_fps_quality`, `cameras_retention_days`,
  `custom_roles`, `events_search_indexes`, `model_scenario_config`. Ordem resolvida por
  `sorted(glob)` (`infra/migrations/run_migrations.py:34`) — determinística, mas **alfabética, não intencional**.
- **16 números ausentes**: 042–045 e 053–064.
- **Diretório duplicado**: existe `migrations/` na raiz com 5 arquivos que **não batem** com `infra/migrations/`
  (o `001` de cada um é um arquivo diferente). Risco de alguém rodar o conjunto errado.
- **Conteúdo duplicado**: `051:44` e `080:64` criam ambos `device_claim_codes.code_hash`, e ambos o índice
  `idx_dcc_hash` (`051:53`, `080:75-76`).

**Precedente:** a ADR-0021 registra que uma colisão de numeração **já derrubou o startup da API**. Isto é a mesma
mina, ainda armada.

---

## P1 — Alto (quebra ao escalar para 25–28 câmeras)

### D-05 · Vazamento de cursor no repositório base
`services/api/app/infrastructure/database/repositories/base.py` — `:28`, `:38`, `:48`, `:58`, `:67`, `:80`.
Nenhum dos 6 métodos usa `with conn.cursor()` nem chama `.close()`. O `with get_connection()` devolve a **conexão**
ao pool; o cursor fica pendurado nela. Mesmo padrão em `connection.py:43`,
`model_rollout_repository.py:58,69,83`, `video_repository.py:45`.

**Relação direta com a investigação de RAM em curso:** é um candidato a crescimento monotônico de memória
independente do live view. O mapa de consumo precisa distinguir os dois.

### D-06 · `_execute_mutation` não commita — funciona por acidente
`base.py:43-51` — o docstring diz que commita, mas **não há `conn.commit()`**. Depende de `autocommit=True` no pool,
e `_execute_in_transaction` (`:78`, `:88`) **liga e desliga** `autocommit`. Se aquele `finally` falhar, mutations
seguintes na mesma conexão param de commitar **em silêncio**. Perda de dado sem erro.

### D-07 · Fallback do gunicorn sobe o app com WebSocket morto
`railway_start.py:151-162` — o `except ImportError` degrada de `GeventWebSocketWorker` para worker `sync`
(`:157-159`), que **não suporta WebSocket**. O app sobe, o health check passa, e SocketIO/live view estão mortos —
com um `log.warning` como único sinal. Falha silenciosa de novo.

*(Correção de doc: o CLAUDE.md diz `gunicorn/eventlet`. É **gevent**. `eventlet` só sobrevive em
`services/api/requirements.txt:13` e `requirements-full.txt:12`, que **não são usados no deploy** — requirements
órfãos que confundem quem lê.)*

### D-08 · 🔍 Sem guarda para câmera alimentada pelo edge no `start_stream`
`stream_handlers.py:27-88` — a ramificação (`:58`) é só `_is_gateway_online(r)`. Se o gateway estiver offline e
`deployment_mode == 'edge'`, o fallback Celery (`:70-73`) dispara `start_hls_stream` + `inference_loop` contra uma
câmera **que já é alimentada pelo edge** — ffmpeg e inferência duplicados. A única lógica ciente de edge
(`stream_info`, `:205-222`) é **informativa, não bloqueia nada**.

🔍 **Reconferir na develop atual** — o PR #250 pode ter mudado isso e não está nesta árvore.

### D-09 · Custo de live view em escala já foi medido — e não fecha
- `docs/evidence/live-view-resource-analysis-2026-07-06.md:78` — 28 câmeras com re-encode ≈ **14 vCPU**,
  registrado como **inviável no tier da API**.
- `docs/research/PESQUISA_CV_30_CAMERAS.md:133-136` — uma GPU satura ~20 streams de decode; 28 câmeras **já passa**.

Ou seja: o problema de consumo que apareceu agora com 1 câmera **já estava documentado desde 06/jul**. O mapa de
consumo (`MAPA-CONSUMO-API-LIVEVIEW-PROMPT.md`) deve partir daí, não do zero.

### D-10 · Coleta morre em silêncio por config com unidade errada
Três ocorrências da mesma família, todas com o mesmo sintoma — **zero frame, zero erro**:
`COLLECTOR_MOTION_THRESHOLD=8.0` contra ruído medido 0.39 · `=2.0` numa variável que virou fração 0–1 ·
`TARGET_FRAMES_PER_CAMERA=17` do experimento, se esquecido no lugar.

**Correção barata:** validação de faixa no startup do coletor — fora do domínio, falha alto. E quando a config
migrar para a nuvem (ADR-0058), a validação vai junto, senão o erro passa a ser **configurável pela tela**.

---

## P2 — Médio (funcional, bloqueia entrega)

| # | Item | Onde |
|---|---|---|
| D-11 | **Não existe recuperação de senha** — nenhum fluxo. Fase 2 bloqueada por falta de conta de e-mail verificada | ADR-0042 (Proposta) `:9`, `:74` |
| D-12 | 4 telas sem endpoint: Validação de Contagem (rotas mortas), clipes de evidência, pré-anotação (`/api/frames/*` vazio), verificação **sem `tenant_id`** (P0) | `CONTRACT_COVERAGE_VALIDATION.md:24-38` |
| D-13 | Domínio **Quality (50 rotas) nunca enumerado** — cobertura real desconhecida | `CONTRACT_COVERAGE_VALIDATION.md:40-45` |
| D-14 | **10 features prontas sem caminho na UI** (~34h): ScenarioEditor sem botão, RoiDrawer com zero imports, VerificationQueue/Counting/Fueling sem nav | `UNPRODUCTIZED_FEATURES.md:14-23` |
| D-15 | `GET /api/alerts/<id>/snapshot` **sem filtro de tenant** — marcado "não portar" | `MIGRATION_WIRING_SPEC.md:72` |
| D-16 | **3 pipelines de upload coexistindo** | `MIGRATION_WIRING_SPEC.md:84` |
| D-17 | Módulo `fueling` legado — nada é standalone, migrations não podem ser apagadas | `modulo-fueling-legado-carga-descarga.md` |
| D-18 | `develop` **184 commits à frente** de `staging` (= produção), que está parada em **15/jul** | git · 🔍 refs locais defasadas, confirmar |
| D-19 | CI: develop "parcialmente verde" — 7 testes falhando + 9 erros | `MUTIRAO_FINAL_REPORT.md:177` |
| D-20 | ~15 modais caseiros em vez do Modal do kit (`TODO-WS1`, baseline congelada por teste) | `apps/frontend/src/**` |
| D-21 | 17 usos de `any` no TS, concentrados em chamadas de API não tipadas | `apps/frontend/src/**` |

---

## P3 — Processo e rastreabilidade

| # | Item |
|---|---|
| D-22 | **ADRs citadas que não existem como arquivo**: 0037, 0038, 0054, 0057. A 0054 e a 0057 são citadas pela 0058 — e a **0057 foi destruída por um `git clean`** nesta máquina. Recriar. |
| D-23 | `docs/security/` **vazio** — `credentials-inventory.md` e `lgpd-pending.md` nunca criados, embora exigidos pelo plano |
| D-24 | `EDGE_DEPLOYMENT_PLAN.md` — **122 checkboxes abertos vs 2 marcados**. Trilhas S0/S1/S2/S3 (segurança, hardening API, hardening edge, gate pré-produção) inteiramente em aberto |
| D-25 | CLAUDE.md desatualizado: diz `eventlet` (é gevent); `AGENTS.md:214-227` descreve um `get_storage()` que não é o real |
| D-26 | Sem down migrations (por design, registrar como decisão) · sem rate limiting · sem request ID · gestão da chave Fernet de senha de câmera |

---

## Itens que os docs alegam e o código **desmente** (não gastar tempo)

| Alegação | Realidade |
|---|---|
| 47 `print()` no backend | **0 reais.** 1 falso positivo dentro de string (`routes_test_console.py:96`) |
| 29 `any` implícitos no TS | **0** de `: any`. 17 no total contando `as any` e `api.get<any>` |
| gunicorn com `eventlet` deprecated ("ALTO RAIO") | É `GeventWebSocketWorker`. Eventlet só em requirements órfãos |
| Pool de anotação invisível (bloqueio nº 1 do flywheel) | Corrigido pelo **PR #246** — doc `FLYWHEEL_ANOTACAO_EPI.md:55` está velho |

> Isto é dívida também: **documento que descreve um sistema que não existe mais** custa tempo de quem lê e produz
> tarefa fantasma. Vale um passe de reconciliação nos docs junto com a correção do CLAUDE.md.

---

## Ordem sugerida

1. **D-01** (credencial que se auto-restaura) — antes de qualquer coisa; o resto da segurança depende de ter um
   superadmin confiável.
2. **D-03** (fallback de storage) — antes da encenação do lote 1, senão o dataset pode evaporar sem aviso.
3. **D-04** (colisão de migration) — já derrubou deploy uma vez; corrigir antes da próxima migration.
4. **D-02** (senha derivável) — uma linha.
5. **D-05 / D-06** (cursor e commit) — entram no mesmo PR do mapa de consumo, já que D-05 pode ser a causa do
   crescimento de RAM.
6. **D-10** (validação de faixa da config) — barato, evita a quarta repetição.

O resto (D-11 em diante) cabe na varredura de segurança já planejada para o dia do embarque final, junto com o
fechamento do repo e a migração dev→produção.
