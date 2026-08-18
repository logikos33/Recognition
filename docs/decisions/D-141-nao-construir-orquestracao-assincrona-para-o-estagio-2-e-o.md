# D-141 · ⛔ NÃO construir orquestração assíncrona para o Estágio 2 — e ⏸️ o Estágio 2 em si fica adiado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ⏸ adiada (o Estágio 2) + ⛔ não construir (a orquestração)

**O que NÃO vamos construir, e por quê:** fila, tabela nova ou state-machine dedicada para o
loop recorta→classifica. Motivo: **não há dor de orquestração para resolver — o Estágio 2 nem está servido**
(`detectors.py:169-216` é single-stage; grep por `stage_2`/`masked_bce` volta vazio). O risco real é de
inércia: os padrões assíncronos do repo (`propagation_jobs`, `search_jobs` — Celery + tabela + polling)
serão reaproveitados por hábito. Quando o Estágio 2 for construído, **loop síncrono**.
*(Guardrail equivalente já registrado como D-109 na PR #385, ainda não mergeada — ver D-142.)*

**O Estágio 2 em si — ⏸️ adiado com CONDIÇÃO OBJETIVA, não data:**
> **quando houver ≥500 recortes com veredito humano completo (present/absent/N-A por classe)
> E o FPS do Estágio 2 medido no Orin mantiver as 28 câmeras com folga.**

Hoje não é possível decidir: o veredito por recorte acabou de ganhar tela (aba Classificar, #384) e não há
lote classificado que permita dimensionar o ganho. **Adiar sem gatilho é como o briefing do Frigate sumiu.**
