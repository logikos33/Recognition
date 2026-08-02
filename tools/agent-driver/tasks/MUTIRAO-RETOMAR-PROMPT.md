# Mutirão — RETOMAR de onde parou

> Use este prompt sempre que a sessão for interrompida (limite de uso, contexto, queda).
> **Regra número um: descubra o estado real antes de fazer qualquer coisa. Não refaça nada. Não mude status de
> nada. Não recomece tarefa.**

---

## PASSO 1 — Inventário (obrigatório, antes de qualquer edição)

Você **não sabe** onde parou. Descubra pelo git, não por suposição.

```bash
# 1. Quais worktrees existem
git worktree list

# 2. Quais branches do mutirão existem e o que cada uma tem
git branch -a --list 'mutirao/*'
for b in $(git branch --list 'mutirao/*' --format='%(refname:short)'); do
  echo "=== $b ==="; git log --oneline origin/develop..$b
done

# 3. ⚠️ O MAIS IMPORTANTE: trabalho NÃO COMMITADO em cada worktree
#    É aqui que a sessão foi cortada no meio.
git worktree list --porcelain | grep '^worktree ' | cut -d' ' -f2 | while read -r w; do
  echo "=== $w ==="; git -C "$w" status --short
done

# 4. PRs abertos (se tiver gh disponível)
gh pr list --state open 2>/dev/null
```

### Como classificar cada item da fila

| Sinal | Significa | O que fazer |
|---|---|---|
| Branch com commit + relatório entregue | **FEITO** | **Não toque.** Só anote na lista |
| Worktree com **mudança não commitada** | **INTERROMPIDO NO MEIO** | Retome **daqui**. Leia o diff, entenda o que já foi feito, **complete** — não recomece do zero |
| Branch existe mas sem commit | Começou e não avançou | Retome do início do item, reaproveitando o worktree |
| Nada | Não começou | Entra na fila normal |

⛔ **NUNCA rode `git clean`** — e em particular agora: as mudanças não commitadas são exatamente o trabalho que a
interrupção deixou pela metade. Limpar isso é perder a sessão inteira.

**Ao fim do PASSO 1, imprima uma tabela** com item × estado × onde está (worktree/branch) × o que falta.
**Depois siga sozinha** — não precisa de confirmação para retomar.

---

## PASSO 2 — Estado conhecido (pode estar desatualizado; o PASSO 1 manda)

*Atualizado em 2026-08-03. Se o git disser outra coisa, **o git vence**.*

### ✅ Concluído
- **Item 2.6 — validação de faixa de config**
  Worktree `wt-26`, branch `mutirao/feat-config-ranges`, commit `65eecfd3`.
  Criou `services/api/app/core/config_validation.py` (15 envs), estendeu
  `CameraService._validate_hardening_fields` (port/channel/subtype/live_view_subtype), 25 testes novos,
  ruff limpo. Suíte: 3851 passed / 6 failed — os 6 são o **baseline pré-existente conhecido**
  (`test_quality_inference_onnx.py`, mock pollution), **não são regressão**.

### 🔧 Ajustes pendentes NO 2.6 (revisão do Vitor — faça antes de considerar o item fechado)

1. **Bug real — as faixas permitem a falha que o item existe para impedir.**
   Foi documentado que `COLLECTOR_PERSON_CONFIDENCE = 1.0` *"desliga o trigger por pessoa silenciosamente"*, e a
   faixa ficou `0.0–1.0`, que **aceita 1.0**. Threshold de confiança em 1.0 = zero detecção, sem erro, sem log.
   **Trocar `le=1.0` por `lt=1.0`** em `DETECTION_CONFIDENCE_THRESHOLD`, `VERIFICATION_THRESHOLD`,
   `DRIFT_SCORE_ALERT_THRESHOLD` e no que for análogo. O limite **inferior** pode continuar inclusivo
   (0.0 = "detecta tudo, filtra depois" é uso legítimo); o superior nunca é.

2. **Não crie um segundo caminho de validação de config.**
   O item **2.1** (R2 obrigatório em produção) é validação de boot também — **deve entrar no mesmo
   `config_validation.py`**, com `model_validator(mode="after")` para a obrigatoriedade condicional por
   `DEPLOYMENT_MODE`. Dois validadores divergentes é exatamente o padrão dos dois runners de migration que já
   custou caro neste repo.

3. **`app/__init__.py:61-65` vai ser disputado** pelos itens 1.2 (introspecção) e 2.1 (preflight de R2).
   Desenhe o hook de boot como **uma chamada só** (`validate_boot()`) que os outros itens estendem **por dentro**,
   em vez de cada item acrescentar sua linha ali. Evita o conflito antes dele existir.

### 📤 Para a sessão do EDGE (relatório, não faça você)
`deploy/edge-sync-agent.env.example` ainda documenta `COLLECTOR_MOTION_THRESHOLD` com default **`8.0`** — valor da
época pré-fração. Hoje a variável é fração `0.0–1.0`, então **`8.0` nunca dispara**. É o arquivo que alguém copia ao
provisionar uma **box nova**, e vêm ~25 câmeras da RVB. Uma box provisionada assim não coleta nada e não reclama.
Correção de uma linha, prioridade alta.

### 🔴 Prioridade ao retomar: item 1.1 (live view)
O deadlock de cold start **continua aberto**. É o único item da fila que o cliente enxerga. Se nada estiver
interrompido no meio, **1.1 é o próximo**, antes de qualquer outro.

---

## PASSO 3 — Retomar a fila

Continue por `tools/agent-driver/tasks/MUTIRAO-PROMPT-UNICO.md`, respeitando:

- **Ordem:** 1.1 → resto da fase 1 → fase 2 → fase 3.
- **Os dois únicos pontos de parada** (🛑): env de R2 ausente em produção (0.1) e backfill em produção (3.5).
  Fora deles, decida e siga.
- **Live view verificado antes e depois de cada fase.** Se regredir, PARE.
- **Roteamento de modelos:** Fable orquestra e decide; Haiku faz varredura/grep (subagente, devolve conclusão, não
  dump); Sonnet implementa; Fable/Opus só no 3.5. Não use raciocínio estendido em tarefa mecânica.
- Não promova para `staging`/`main`. Um PR por tema. `ruff check .` limpo.
- Não exponha segredo em log/commit/PR — env var se reporta **presente/ausente**, nunca o valor.

## Ao terminar cada item, atualize este arquivo

Mova o item para "✅ Concluído" com **worktree, branch e commit**. É isso que faz a próxima retomada custar 2
minutos em vez de meia hora.
