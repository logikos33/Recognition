# D-100 · Ponytail adotado — reduz código, NUNCA verificação

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · Claude · 🔄 em execução (instalação pelo Vitor)**

Rodada de ferramenta (não de produto). Adotado o ruleset **Ponytail** (`DietrichGebert/ponytail`,
MIT) — "sênior preguiçoso", escada de 7 degraus antes de escrever código: 1) precisa existir? (YAGNI)
· 2) já existe no codebase? reusa · 3) stdlib faz? · 4) recurso nativo? · 5) dependência instalada? ·
6) uma linha? · 7) só então o mínimo que funciona. Lema: *"lazy about the solution, never about
reading"*. Combina com como o projeto já vinha decidindo na mão (reusar `remote_train.py`,
`GpuProvider`, seletor do #362). **Verificado (C-04, não marketing):** puramente local, **zero egress**,
sem chamada de rede; custo medido do `AGENTS.md` ≈ **~800 tokens/sessão** (arquivo único auto-contido);
escreve em `~/.config/ponytail/`; reversível (`/plugin uninstall`). Instala com 2 comandos que o Vitor
digita (`/plugin marketplace add DietrichGebert/ponytail` + `/plugin install ponytail@ponytail`) —
slash-commands não são executáveis por agente.

🔴 **GUARDA INEGOCIÁVEL — Ponytail pode cortar CÓDIGO, nunca VERIFICAÇÃO.** Independentemente do que o
ruleset sugira, continuam obrigatórios: percorrer o caminho no navegador antes de entregar roteiro
(D-82 — foi o que pegou o `useToast` que 276 testes verdes não pegaram); soak ≥3× o TTL antes de
declarar estabilidade; prova com número dos dois lados (banco **e** R2, antes **e** depois); nunca
`completed` sem artefato verificável; e as travas de segurança (guard por destino, C-01 cross-tenant→404,
ADR-0017 sem fallback de tenant, redação de credencial). **Em conflito, a regra do projeto vence e o
episódio é reportado** (é informação sobre a ferramenta).
