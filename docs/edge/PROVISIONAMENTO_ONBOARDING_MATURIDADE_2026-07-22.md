# Embarque de cliente / provisionamento — da dor manual ao self-service na plataforma

**Data:** 2026-07-22 · **Origem:** a jornada real de embarque do pandora/RVB no ambiente de DEV (2026-07-21/22)
**Relaciona:** task-097 (provisioning/go-live), ADR-0019 (device tokens), ADR-0004 (multi-tenant),
`GO_LIVE_EXECUCAO_2026-07-21.md` (Bloco 5), a série de prompts de enrollment/reconciliação.

> **Por que este documento existe.** Tentar provar a artéria (edge→nuvem) num box de teste levou várias rodadas,
> e CADA passo revelou um tropeço. Importante: **nenhum foi bug de arquitetura** — todos foram de **estado de
> ambiente** ou de **processo/ferramental**. Este é o registro para tornar o embarque de novos clientes fluido,
> depois automatizado, e por fim **preenchido pelo próprio cliente dentro da plataforma**. A dor de hoje é a
> especificação do produto de amanhã.

---

## 1. A jornada real de embarque (ponta a ponta)

O que é preciso acontecer, na ordem, para um cliente novo sair do zero até "o edge fala com a nuvem e o admin
reflete o dado real":

| # | Etapa | O que faz | Quem faz hoje |
|---|---|---|---|
| 1 | **Tenant** | Criar o tenant do cliente (schema-per-tenant, ADR-0004) | seed/script |
| 2 | **Admin** | Criar o usuário admin do tenant, **com e-mail válido** e senha | seed/script |
| 3 | **Módulos** | Habilitar os módulos contratados (epi / quality / counting) | seed/script |
| 4 | **edge_site** | Criar o site edge do cliente (o SITE_ID) sob o tenant | seed/script |
| 5 | **Câmeras** | Cadastrar as câmeras (IP, credenciais, módulo por câmera) | UI / seed stub |
| 6 | **Enrollment token** | Admin gera um token one-time para o device | admin (API/UI) |
| 7 | **Enroll do device** | O Jetson gera par de chaves, enrola, recebe identidade RS256 | script no box |
| 8 | **Config do coletor** | `EDGE_API_URL` + `EDGE_DEVICE_BEARER` no `.env` (chmod 600) + restart | sudo no box |
| 9 | **Verificação** | Heartbeat/telemetria chegam → admin reflete o device | admin (API/UI) |

Hoje isso é **manual, com conhecimento tribal**, espalhado em terminal + navegador + SSH + Railway. Foi
exatamente onde tropeçamos.

---

## 2. Catálogo de landmines (o que deu errado, e a causa raiz)

Cada um destes custou uma rodada. Todos são preveníveis.

| # | Sintoma | Causa raiz | Prevenção (o alvo) |
|---|---|---|---|
| L1 | `postgres.railway.internal` não conecta do Mac | Peguei a **DATABASE_URL interna** do Railway (só resolve dentro da rede) | O tooling deve exigir a **URL pública** e validar o host antes de agir |
| L2 | Ambíguo qual ambiente é o banco | Host interno é igual em todo ambiente; só o proxy público discrimina | Guardrail que **confirma DEV vs PROD** pelo host (`hayabusa` vs `interchange`) antes de qualquer escrita |
| L3 | Testei/apontei contra `api-v3-production` | A develop (código novo) está em **DEV**, não em produção; confundi os ambientes | O runbook fixa o ambiente-alvo por etapa; automação lê do config, não da memória |
| L4 | Seed falhou: `duplicate key tenants_slug_key` | Tenant RVB já existia com **UUID aleatório**, e o seed assume UUID determinístico e cria do zero | Provisionamento **idempotente que resolve por slug**, não recria; ou parte de estado limpo controlado |
| L5 | Admin perdido, recuperação por e-mail não funciona | Admin criado com **e-mail inválido** (`admin@rvb.com.br`, undeliverable) | **E-mail válido obrigatório** no cadastro do admin (validação + verificação) |
| L6 | Senha nova não pega ao re-seedar | `INSERT ... ON CONFLICT (email) DO NOTHING` engole a senha se o admin já existe | Fluxo de reset explícito (ADR-0042), não re-seed silencioso |
| L7 | "edge_site criado" mas banco tem 0 sites | **Mecanismo (achado depois):** o `seed_rvb_edge.py` fazia o INSERT do edge_site e os 28 UPDATE de câmera na **mesma transação**; um UPDATE falhou (ver L11) → rollback do edge_site junto. Dois scripts rodaram; o 1º (admin) deu certo e o "deu certo" foi lido como o todo, o erro do 2º passou despercebido. Report conflado + sem verificação | Regra: **nunca reportar "feito" sem query de verificação** que casa com o banco; transação por unidade; **um passo, um resultado verificado** |
| L11 | UPDATE de câmera aborta a transação do edge_site | **A causa da causa:** migration 026 adiciona `active_module` a `cameras` com `IF EXISTS (table_name='cameras')` **sem qualificar schema**. Em schema-per-tenant, `cameras` vive em `{tenant_schema}.cameras`, não em `public`. A coluna pode não existir onde o UPDATE espera | ⚠️ **Não é só do seed** — `active_module` é a base do roteamento de modelo por câmera (task-045). Investigar se a coluna existe na `cameras` do schema do tenant em todos os ambientes (issue própria) |
| L8 | `Uncaught SyntaxError` / `command not found: -H` | Confusão **terminal (curl) vs console do navegador (JS)**; `\` de continuação quebrou o comando | UI que gera o token com 1 clique elimina o curl/console do fluxo do usuário |
| L9 | `Missing Authorization Header` / `Não autorizado` | JWT expirado, colado com `Bearer`/aspas, ou parcial | Token gerado **dentro da plataforma**, sem o usuário manusear JWT cru |
| L10 | Firewall/egress (potencial, não ocorreu no teste) | Rede do cliente pode bloquear a saída do edge | Checklist de rede pré-embarque + teste de conectividade automatizado |

**O padrão:** estado acumulado inconsistente (L4), report não-verificado (L7), ferramental cru que expõe o
usuário a terminal/JWT/ambiente (L1, L2, L3, L8, L9), e validação ausente no cadastro (L5, L6). **Zero** disso é
a arquitetura falhando.

---

## 3. Escada de maturidade (onde estamos → onde queremos chegar)

```
Nível 0 — MANUAL COM CONHECIMENTO TRIBAL   ← estamos aqui
   terminal + navegador + SSH + Railway, passos na cabeça, cada erro é uma rodada.

Nível 1 — RUNBOOK À PROVA DE TROPEÇO
   um documento único, ordenado, com os guardrails embutidos (host, e-mail, verificação),
   copy-paste seguro. Elimina "esqueci um passo" e "ambiente errado".

Nível 2 — UM SCRIPT ORQUESTRADOR
   um `provision_client.py` idempotente que faz tenant→admin→módulos→site, com validação
   (e-mail, UUID por slug, verificação pós-escrita) e um só ponto de entrada. Reduz 9 passos a 1.

Nível 3 — AGENTE EXECUTANDO
   o Code (ou um agente dedicado) roda o orquestrador, faz o enroll no box por SSH, e verifica,
   parando só nos pontos que exigem humano (senha, sudo, credencial de câmera).

Nível 4 — SELF-SERVICE NA PLATAFORMA   ← o norte
   o próprio cliente/operador preenche tudo pela UI: cria o site, cadastra câmeras, gera o
   enrollment-token com 1 clique, e um wizard guia o device até "online". Zero terminal, zero JWT cru.
```

Cada degrau **remove uma classe inteira de landmines** do §2. O Nível 4 é onde o embarque vira produto, não
operação — e é o que permite escalar para 40 clientes sem o time virar gargalo.

---

## 4. O alvo: provisionamento dentro da plataforma (spec embrionária)

O que a UI precisa fazer para chegar ao Nível 4. Isto vira PRD quando for a hora:

**Tela "Novo cliente / site":**
- Formulário: nome do tenant, admin (**e-mail validado + verificação de entrega**), módulos contratados.
- Cria tenant + admin + módulos numa transação verificada (resolve por slug se já existir; nunca duplica).

**Tela "Câmeras":**
- Cadastro por câmera (IP, credencial, módulo, ROI), já existente em parte — reusar.

**Tela "Conectar o edge" (o wizard de enrollment):**
- Botão **"Gerar token de enrollment"** (1 clique — sem curl, sem JWT cru; o token one-time nasce e é mostrado).
- Instrução gerada para o device (o comando único a rodar no Jetson, ou um instalador que já recebe o token).
- **Checklist de rede** exibido: as saídas que o firewall do cliente precisa liberar (API, R2, túnel, NTP).
- **Painel de status ao vivo:** "aguardando device… enrolado ✓… heartbeat recebido ✓… telemetria fluindo ✓" —
  o critério de sucesso visível, que é a artéria provada.

**Regras transversais que a plataforma precisa impor (as lições viram invariantes):**
- E-mail de admin **sempre válido** (L5/L6).
- Toda escrita de provisionamento **idempotente e verificada** (L4/L7).
- Segredos (bearer, token) **nunca expostos ao usuário como texto cru** (L8/L9).
- Ambiente **explícito e checado** (L1/L2/L3).

---

## 5. Recomendação de sequência (o que construir primeiro)

1. **Nível 1 agora, de graça:** consolidar toda esta jornada + os guardrails num **runbook único** de
   provisionamento (a partir deste doc + os prompts da série de enrollment). Baixo custo, resolve o embarque da
   RVB real já.
2. **Re-seed limpo do DEV** para alinhar UUIDs determinísticos — tira o estado órfão que causou L4/L7, e dá um
   baseline confiável para testar o resto.
3. **Nível 2 (script orquestrador)** logo após a artéria fechar — vira a base do provisionamento repetível, e é o
   coração que a UI do Nível 4 vai chamar por baixo.
4. **Nível 4 (self-service)** entra no roadmap de produto, não de infra — é feature vendável ("o cliente conecta
   sozinho em minutos"), e é o que a tese de "cada cliente treina o próprio modelo" pede: se o cliente treina,
   o cliente também deve **provisionar** sem depender do time.

---

## 6. Princípios que emergiram (guardar como invariantes de operação)

1. **Report tem que casar com o banco.** "Feito" sem query de verificação não é feito (L7). Verificar não é
   paranoia — é o que separou "seguir confiando" de "descobrir que o site não existia".
2. **Ambiente é explícito, nunca de memória.** Host, URL, tenant: confirmar contra a fonte (Railway, banco), não
   contra o que se lembra. C-04 aplicado a operação.
3. **Idempotência de verdade.** Não é "tem ON CONFLICT" — é "roda 2× e o resultado é o mesmo, inclusive a senha".
4. **E-mail válido é invariante, não detalhe.** Um admin com e-mail undeliverable é uma conta que ninguém
   recupera. Em produção não há re-seed.
5. **O usuário não manuseia credencial crua.** JWT no F12, bearer no `.env`, token no curl — cada um é uma chance
   de erro e de vazamento. A plataforma deve absorver isso.
6. **Cada tropeço no teste é um tropeço a menos no cliente — se virar runbook/UI.** A dor só é desperdício se não
   for capturada.

---

## 7. Log da jornada (para referência — o que de fato aconteceu)

1. Diagnóstico #217: o pandora era stack 100% local, nunca falou com a nuvem (artéria não provada).
2. Erro de ambiente: preparação apontou para produção; corrigido para DEV.
3. Chrome caiu → reconectado; tentativa de gerar token in-browser bloqueada (proteção de credencial, correta).
4. Admin perdido (e-mail inválido) → decisão de recriar sob e-mail válido do Vitor (`vitor@logikosvision.com.br`).
5. `DATABASE_URL` interna (não conecta) → troca pela pública; guardrail de host `hayabusa` = DEV confirmado.
6. Seed falhou: tenant já existia com UUID aleatório → reconciliação sob o tenant existente.
7. Reconciliação criou o admin (login OK) mas **não** o edge_site, apesar do report → pego por verificação no banco.
8. Enrollment token: confusão terminal×console, `\` quebrando o comando, JWT → "Missing Auth Header", depois
   "Site não encontrado" (o site não existia).
9. **Em aberto:** criar o edge_site verificado → gerar o token → enrolar o pandora → provar a artéria.

> Este documento é vivo: ao fechar a artéria, anexar o runbook final que funcionou e marcar o §5 item 1 como
> concluído.
```
