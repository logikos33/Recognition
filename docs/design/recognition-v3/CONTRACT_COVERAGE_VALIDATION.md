# Validação de Cobertura — Design v3 × Contrato de Backend

> **Pergunta:** antes de migrar pro front novo, quanto do que o design precisa já tem endpoint real, e o
> que vai faltar? · **Data:** 2026-07-12 · **Método:** cruzamento das 4681 linhas de
> `Recognition-visao-final.dc.html` × `API_CONTRACT_MAP.md` (33 domínios) × `CONTRATO_FRONT_BACK.md`.
> Regra: só conta como COBERTO se o endpoint (método+path) aparece **literalmente** no mapa. Nada inventado.

## 1. Veredito — cobertura

| Métrica | Valor |
|---|---|
| Telas/modais do design analisados | **24** |
| Features do design identificadas | **138** |
| **COBERTO** (endpoint real serve) | **84 — 61%** |
| **PARCIAL** (existe, mas com divergência/ressalva) | **30 — 22%** |
| **FALTA** (backend não tem) | **24 — 17%** |

**Leitura:** o esqueleto operacional (auth, módulos, câmeras, operações, alertas, eventos, training,
admin) tem backend real — dá pra migrar essas telas com confiança. **17% falta** e **22% é armadilha**
(portar ingênuo = bug). Nenhum dos dois some sozinho: precisam de decisão antes da migração.

## 2. O que vai FALTAR (bloqueia a tela — resolver antes)

1. **Validação de Contagem (tela inteira):** o design pede aceitar/rejeitar sessão, agregado diário e
   threshold de erro — **nenhum endpoint existe**. E as 2 chamadas que a tela usaria já são **mortas
   hoje** (`PATCH /counting/sessions/{id}` e `GET .../validation-report` — achados D1/D2 P0). Só edição
   de placa (`/plate`) e listagem (`/plates`) existem. → **backend novo ou tela "em breve".**
2. **Clipes de evidência (~20s):** o design mostra player de clipe em Contagem, Verificação e Alertas —
   **nenhuma rota de clipe** no mapa. Bloqueia a coluna "ver evidência". → precisa endpoint (ADR-0033).
3. **Pré-anotação assistida por IA (núcleo do Training Studio):** blueprint `/api/frames/*` **vazio**
   (#9); o real (`/api/training/frames/<id>/pre-annotate`) está com **flag OFF** (decisão nossa,
   ADR-0031). → UI "em breve" (consistente com o que já decidimos).
4. **Verificação com tenant seguro:** `POST /api/verification/<id>/review` existe mas **sem tenant_id**
   (#14 P0). Confirmar/rejeitar não pode ser portado sem o fix. → depende do defeito P0.

**Não bloqueia (falta, mas contornável):** presets de grid do VMS (hoje localStorage), config de duração
de clipe pré/pós, threshold de erro, toggles de 2FA/push/email sem backend, assistente de tickets IA
(já "em breve" no design), catálogo de fabricantes RTSP (client-side, ok).

## 3. Buraco na PRÓPRIA validação — Quality não está no mapa

O domínio **Quality (50 rotas)** **não foi enumerado** no `API_CONTRACT_MAP.md §1.21`. As telas
**Peças, Retrabalho, Kiosk e Andon** (módulo Qualidade) ficaram como PARCIAL "confirmar na fonte". Ou
seja: **não sabemos a cobertura real dessas 4 telas** até enumerar `quality/routes.py`. → **ação
obrigatória antes de migrar o módulo Qualidade** (não afeta EPI/Contagem).

## 4. Backend que o design NÃO usa (inverso)

- **Dropado de propósito (v3 simplificou):** Chat/ChatFAB (sumiu), tablets Quality V1/V2 (viraram
  Kiosk/Andon), `/api/v1/videos/*` (14 rotas R2+Celery sem consumidor — o design usa o legado
  `/api/training/videos`; oportunidade de consolidar).
- **Confirmar se foi absorvido:** **Fueling** (`/api/fueling/*`, 5 rotas) — o "Carga & Descarga" do
  design é **Contagem** (`/api/counting/*`), não o fueling do CLAUDE.md. Fueling ficou órfão →
  confirmar se foi substituído por counting.
- **Device-facing (correto não ter UI):** edge heartbeat/enroll/commands, site-gateways, storage
  health, streams status.
- **Gap de UI a confirmar:** onboarding de **device/edge** (`/api/devices/claim`, criação de sites,
  enrollment-tokens) — se o produto vende multi-site edge, falta a tela de claim/provisionamento.
  **Notifications channels** (whatsapp/telegram/email/webhook) — backend tem CRUD; design só tem
  toggles genéricos.

## 5. Riscos de inconsistência (portar ingênuo = bug) — o "22% PARCIAL"

1. **Envelope errado:** Dashboard (por classe/câmera), Investigação (`eventsService`) e Impersonate
   (`impersonation.ts`) assumem `{success,message,data}`; o real é `{status,data}` (#3). Portar o parser
   atual = tela quebra em silêncio. **Corrigir ao portar.**
2. **`/api` vs `/api/v1` em Câmeras (#12):** só `probe/effective-model/config/health-context` têm alias
   v1. Presumir v1 pro resto = 405. **Usar o path real por rota.**
3. **Endpoints mortos de Contagem (D1/D2):** não replicar — wire só no real, resto "em breve".
4. **Cross-tenant P0:** snapshot de alerta (#7), toggle de classe (#6), verificação (#14), Andon (scan
   por schema, sem JWT). Portar direto = vazamento entre tenants. **Depende dos fixes P0.**
5. **Export de Relatórios (D3):** FE atual chama sem `/api` → 404. Usar `GET /api/v1/reports/export`.
6. **Branding duplicado (#10):** só o canônico `/api/v1/admin/tenants/<id>/branding`; o nested está
   deprecated mas vivo.
7. **`acknowledge` 2× (#11):** fiar no dono `alerts`, não no delegado de training.
8. **Raw fetch:** Anotação, Auditoria-export, Andon usam `fetch()` cru — portar pro `api.ts`.
9. **Demo destrutivo (#5) + temp_password (#4):** a aba "Dados de Demo" não pode expor o seed que apaga
   dado real; criação de tenant devolve senha previsível. Não expor/depender.

## 6. Gate antes de iniciar a migração (o que fazer agora)

Ordenado — nada disso é a migração em si; é destravar pra ela não gerar inconsistência:

1. **Enumerar o domínio Quality** (`quality/routes.py`) e completar a cobertura das 4 telas de
   Qualidade — hoje é ponto cego. (Se o go-live inicial é só EPI, isso pode ser paralelo.)
2. **Decidir os 4 "FALTA que bloqueia":** Validação de Contagem, clipes de evidência, verificação
   segura, pré-anotação — cada um vira "backend novo (ADR/task)" ou "UI em breve". Sem decisão, essas
   telas não têm como funcionar igual.
3. **Priorizar os P0 de segurança** (snapshot, classe, verificação, quality-seed, temp-password) —
   as telas que os tocam (Alertas, Modelos, Verificação, Admin) não devem ser migradas por cima do bug.
4. **Decidir consolidação de uploads** (`/api/v1/videos/*` vs `/api/training/videos`) e **confirmar
   Fueling→Contagem** — pra não migrar Treinar/Carga fiando no pipeline errado.
5. **Regra de ouro na migração:** onde COBERTO → portar; onde PARCIAL → portar consertando (envelope/
   path/dono correto); onde FALTA → "em breve" + pendência de backend, nunca chamada fabricada.

## 7. Conclusão

**61% migra direto, 22% migra consertando, 17% precisa de decisão (backend novo ou "em breve").** O
EPI (núcleo, go-live RVB) está majoritariamente COBERTO — dá pra começar por ele. As telas de
**Qualidade e Validação de Contagem** são as de menor cobertura e as que mais precisam de decisão antes.
Nenhuma inconsistência aqui é surpresa não-mapeada: está tudo rastreado acima.
