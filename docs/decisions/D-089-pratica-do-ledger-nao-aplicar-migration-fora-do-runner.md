# D-089 · Prática do ledger: NÃO aplicar migration fora do runner

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · Vitor (prompt) + Claude (guarda) · ✅ (PR #360)**

A migration 113 foi aplicada com `psql -f` do arquivo versionado, mas **fora do runner** — não
entrou no ledger do DEV. Benigno neste caso (`ADD COLUMN IF NOT EXISTS` faz no-op e converge no
deploy), mas o padrão é o problema:

⛔ **Não aplicar migration fora do runner em ambiente que o runner gerencia.** O ledger é o
registro de o que foi aplicado onde; aplicação fora dele faz o ledger **mentir sobre o estado
do ambiente** — e a próxima pessoa que raciocinar a partir dele raciocina errado. É o C-04
aplicado ao banco. Se a coluna é necessária agora, faça o deploy — **a pressa de "preciso dela
já" é o que cria a deriva.** Se for inevitável, **grave a entrada no ledger junto**: migration
aplicada sem registro é estado invisível.

**Resposta à pergunta da rodada — o runner detecta?** Antes do PR #360, **não avisava em
nenhum caso**: no modo legado, "already exists" é tolerado por heurística todo boot (passa
batido por design); no modo ledger (`MIGRATIONS_LEDGER_CUTOVER=1`), migration idempotente
aplicada fora reaplicava como no-op e **convergia em silêncio**, e migration não-idempotente
**derrubava o boot** (`SystemExit(1)` em "already exists" desconhecido) — o caso benigno era
invisível e o ruim virava outage, nunca aviso. **Agora** (PR #360): primeira aplicação segundo
o ledger num banco estabelecido que gera `NOTICE ... already exists, skipping` → **WARNING de
possível deriva no startup**. Limite honesto: só statements `IF NOT EXISTS` emitem NOTICE.
