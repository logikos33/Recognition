# Lint Baseline — Phase 0

**Data:** 2026-05-28  
**Ferramenta:** ruff  
**Escopo:** services/api/

## Estado no início da Fase 0

`ruff check services/api/` (regras padrão) → **319 erros** de estilo histórico.

Categorias predominantes:
- `E` — style (indentação, espaços, linha longa)
- `W` — warnings (trailing whitespace, blank lines)
- `B` — bugbear (raise dentro de except sem `from err`)

Esses erros **existiam antes da Fase 0** — nenhum foi introduzido pela reorganização.
O CI novo detectou o debt histórico ao rodar pela primeira vez.

## Política Fase 0

`services/api/ruff.toml` configura apenas:
- `F` (pyflakes) — imports não usados, variáveis não definidas, etc.
- `E9` — erros de sintaxe Python

Isso garante que:
- Novos arquivos com erros de pyflakes (undefined names, unused imports) disparam CI vermelho
- O debt histórico de estilo não bloqueia o CI desta fase
- O baseline é explícito e documentado (não silenciado sem rastrear)

## Como ampliar as regras

Em sprint de qualidade futura, adicionar ao `ruff.toml`:

```toml
# Passo 1 — importações
select = ["F", "E9", "I"]  # isort

# Passo 2 — estilo básico
select = ["F", "E9", "I", "E", "W"]  # style completo

# Passo 3 — segurança e boas práticas
select = ["F", "E9", "I", "E", "W", "B", "S"]
```

Cada passo deve ser feito em PR separado, corrigindo os erros antes de ativar a regra.

## Referência

- `services/api/ruff.toml` — config ativa
- 319 erros originais preservados no histórico do CI run: PR #5 first push
