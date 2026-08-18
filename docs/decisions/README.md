# Decisões — uma decisão, um arquivo

Índice gerado: [`INDICE.md`](./INDICE.md) · Histórico congelado:
[`../REGISTRO_DE_DECISOES.md`](../REGISTRO_DE_DECISOES.md) · Arquitetura longa:
[`adr/`](./adr/)

## Por que mudou

O registro era um único arquivo append-only de ~3.500 linhas. Com duas sessões
trabalhando em paralelo, **todo append cai na mesma região do mesmo arquivo**.
Resultado medido: **3 colisões de número `D-` em 3 rodadas**. As cicatrizes estão
no próprio conteúdo — D-105 e D-106 tiveram de ser renumerados na consolidação
do merge #384 porque os números já estavam em uso na `develop`.

Um arquivo por decisão não elimina a chance de duas sessões escolherem o mesmo
número. Ele troca o custo: em vez de resolver um conflito de merge no meio de um
arquivo gigante, você **renomeia um arquivo e regera o índice**.

## Como registrar uma decisão

```bash
python3 tools/decisoes.py new "Título da decisão"   # cria o próximo D- livre
$EDITOR docs/decisions/D-NNN-titulo.md
python3 tools/decisoes.py index                     # regera o índice
```

Formato do arquivo — o mínimo, nada mais:

```markdown
# D-176 · Título da decisão

**Data:** 2026-08-18 · **Status:** ✅ vigente

Contexto em uma linha. A decisão. Por quê — e o que foi descartado.
```

**Status:** `✅ vigente` · `🔄 em execução` · `⏸ adiada` · `↩ substituída` ·
`❌ revertida` · `📌 dívida/constatação`

## Regras

1. **Um arquivo por decisão.** O nome é `D-NNN-slug.md` e o `# D-NNN` do título
   interno tem de bater com o número do arquivo — o `check` falha se divergir.
2. **Arquivo de decisão não se reescreve.** Mudou de ideia? Decisão nova, e a
   antiga vira `↩ substituída por D-NNN`. O erro registrado é o que impede
   repetir.
3. **`INDICE.md` é gerado.** Não edite à mão — a edição some no próximo `index`.
4. **Decisão de arquitetura com alternativas e consequências vira ADR**
   (`adr/`). Este registro diz *o que* foi decidido; a ADR diz *por quê*, longo.

## Colidiu mesmo assim?

Duas sessões criaram `D-176-*.md` diferentes. O git mostra dois arquivos
adicionados, sem conflito de conteúdo:

```bash
git mv docs/decisions/D-176-o-meu.md docs/decisions/D-177-o-meu.md
sed -i '' '1s/D-176/D-177/' docs/decisions/D-177-o-meu.md
python3 tools/decisoes.py index
```

## Migração do monólito

Feita **por script**, sem edição manual em massa:
`python3 tools/decisoes.py split` leu `docs/REGISTRO_DE_DECISOES.md` e escreveu
as 170 entradas `### D-NN ·` como arquivos, **corpo verbatim**. O monólito
continua no repositório, íntegro e congelado — a regra append-only dele nunca
disse que se podia apagar entrada, e não se apagou nenhuma. Conteúdo que não era
entrada `D-` (constatações, notas de método) permanece lá e só lá.

## CI

O gate de docs (`scripts/ci/check_docs_gate.py`) roda `decisoes.check()`: falha
se houver número `D-` duplicado, se o título interno não bater com o nome do
arquivo, ou se o `INDICE.md` estiver desatualizado.
