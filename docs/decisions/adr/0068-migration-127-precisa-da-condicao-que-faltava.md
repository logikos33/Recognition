# ADR-0068 — Migration 127 já apaga o dia que ela mesma previu

- **Status:** Proposta
- **Data:** 2026-08-31
- **Contexto imediato:** ADR-0065 (presença é conformidade, ausência é
  violação) e a migration `125_yolo_classes_is_violation.sql` (backfill de
  polaridade) e `127_polaridade_nao_erode.sql` (devolve NULL ao que a 125
  gravou sem uma rota que decidisse). Achado feito verificando o veredito da
  rodada 2 de correção UX (contrato A1) contra o código real.

---

## O pressuposto que expirou

`127_polaridade_nao_erode.sql` existe porque, em modo **LEGADO** (o modo real
de produção hoje — `runner_core.py`, sem `MIGRATIONS_LEDGER_CUTOVER=1`), TODA
migration reexecuta a cada boot da API. A 125 termina com:

```sql
UPDATE public.yolo_classes SET is_violation = FALSE WHERE is_violation IS NULL;
```

Sem controle, isso apagaria a decisão de um admin a cada reinício. A 127
devolve `NULL` só para classes criadas a partir de `2026-08-25`, e o próprio
cabeçalho dela é explícito sobre a condição que sustenta essa correção:

> ⚠️ PRESSUPOSTO, e ele tem prazo: nenhuma rota grava `is_violation`. No dia
> em que existir uma (...), esta migration passa a apagar decisão humana e
> precisa ganhar a condição "e ninguém decidiu explicitamente".

**Esse dia chegou nesta mesma rodada.** O commit `d4b0ce77` (HEAD deste
worktree) faz `TenantClassService.create_class` **exigir** `is_violation` na
criação (`ValidationError` sem ele) e `patch_class` aceita `is_violation`
como campo editável a qualquer momento
(`services/api/app/domain/services/tenant_class_service.py:88-126,199-204`).
Ambas são rotas vivas, hoje, atrás de `Classes.tsx`/`ModuleClassesPage.tsx`
e do endpoint PATCH de classe.

## O conflito exato

Em modo legado, a cada boot da API, a `127` roda:

```sql
UPDATE public.yolo_classes
   SET is_violation = NULL
 WHERE is_violation IS FALSE
   AND created_at >= TIMESTAMP '2026-08-25 00:00:00';
```

Esse recorte **não distingue** duas origens para `is_violation = FALSE` numa
classe criada depois de 25/08:

1. O backfill antigo (o que a 127 existe para desfazer) — não deveria
   existir mais, já que `create_class` não insere sem a coluna.
2. **Um admin escolhendo "conformidade" explicitamente**, pela tela nova
   (seletor obrigatório na criação) ou por um PATCH later — o que a própria
   migration, ANTES desta rodada, não tinha como acontecer.

Hoje as duas são indistinguíveis no schema: `yolo_classes` não guarda
**quem decidiu nem quando**, só o valor. Resultado: em produção (modo
legado), toda classe que um admin marcar explicitamente como conformidade
(`is_violation=false`) a partir de agora **é apagada de volta para NULL no
próximo reinício da API** — a mesmíssima classe de bug que a 127 foi escrita
para consertar, só que na direção oposta e sobre uma decisão real, não sobre
um backfill.

## O recorte exato do que falta

A condição que a 127 previu e não tem hoje: **"e ninguém decidiu
explicitamente"**. Isso exige que o schema saiba diferenciar "valor herdado
de um backfill" de "valor gravado por uma pessoa numa rota" — ou seja, uma
segunda informação além do booleano (`decided_at`, `decided_by`, uma origem
enum, ou equivalente). **Essa coluna não existe.** Inventá-la agora, sob
pressão de congelamento (terça 18h), é exatamente o tipo de decisão de
schema que não deveria ser tomada às pressas — daí este registro em vez de
um PR.

## O que isto NÃO decide

- **Qual mecanismo de proveniência.** Coluna nova (`is_violation_decided_at`
  timestamp nullable, ou `polarity_source enum('backfill','human')`), ou
  outro desenho — fica para quem decidir com tempo.
- **Se a 127 deve ganhar essa condição ou se deve ser aposentada.** Uma
  alternativa: quando `MIGRATIONS_LEDGER_CUTOVER=1` virar o padrão de
  produção (fora do escopo desta ADR), a 127 deixa de reexecutar a cada boot
  e o conflito desaparece sozinho — mas produção está em modo legado HOJE,
  então isso não fecha a lacuna para o embarque desta semana.
- **Se algum admin já perdeu uma decisão real.** Não investiguei o dado de
  produção agora (fora do escopo desta rodada); é o primeiro passo de quem
  pegar esta ADR.

## Consequência enquanto isto não é decidido

Em produção (modo legado, hoje): marcar uma classe criada a partir de
25/08/2026 como **conformidade** (`is_violation=false`), pela tela ou por
PATCH, **não é durável** — reverte para `NULL` (observação) no próximo
reinício da API. Marcar como **violação** (`is_violation=true`) não tem este
problema (a 127 só mexe em `FALSE`). Até a decisão acima, qualquer operação
de cadastro que dependa de "conformidade" sobreviver a um restart precisa
saber disso.

## Relacionadas

- **ADR-0065** — presença é conformidade, ausência é violação.
- `infra/migrations/125_yolo_classes_is_violation.sql`,
  `infra/migrations/127_polaridade_nao_erode.sql` — congeladas (checksum),
  não editar; qualquer correção é migration nova.
- `services/api/app/domain/services/tenant_class_service.py` — as rotas que
  passaram a gravar `is_violation` e tornaram o pressuposto da 127 obsoleto.
