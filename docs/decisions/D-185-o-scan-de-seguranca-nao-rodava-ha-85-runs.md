# D-185 · O scan de segurança ⛔ não rodava há 85 runs — uma chave YAML repetida

**Data:** 2026-08-19 · **Status:** ✅ vigente

**O achado.** `security-scan.yml` está em `failure` **em 100% dos runs** desde 18/08. Não é um scan que
reprova: é um workflow que ⛔ **nunca executa**. A API devolve `total_count: 0` jobs, zero log, zero
tempo faturado — o GitHub recusa o arquivo na validação, antes de agendar qualquer coisa.

Com ele foram junto, silenciosamente: **gitleaks, bandit, pip-audit, npm audit e SBOM**.

**A causa.** Commit `6f895b0` (18/08 13:01 UTC) deixou `working-directory` escrito **duas vezes** no
mesmo step do `npm audit`:

```yaml
      - run: npm audit --audit-level=high
        if: steps.escopo.outputs.auditar == 'true'
        working-directory: apps/${{ matrix.app }}
        working-directory: apps/${{ matrix.app }}   # <- repetida
```

Última execução de verdade: **18/08 13:06 UTC**. De lá até 19/08: **85 runs, 85 `failure`**.

⚠️ **A ironia importa para o método:** `6f895b0` é do PR que consertava o vermelho do #421 —
"npm audit só audita o app que o PR tocou". O conserto do ruído produziu **ausência total de sinal**,
que é pior, porque ausência não parece defeito.

**Por que ninguém viu.** Três camadas de disfarce, e vale nomear as três:

| camada | o que ela mostrava |
|---|---|
| `yaml.safe_load` (Python) | ⛔ **não** reclama de chave duplicada — fica com a última em silêncio. "O YAML parseia" ⛔ não prova nada |
| quadro de checks do PR | o `security-scan` simplesmente ⛔ **não aparece**. Check ausente ⛔ não é check vermelho |
| `gh run view` | *"This run likely failed because of a workflow file issue"* — mas só quem foi olhar |

Mesma família do resto da semana: [[D-183]], #417, #436 — **o defeito é indistinguível do
funcionamento**.

⚠️ **Consequência para o #433.** A definição de pronto daquela issue lista
`Secret detection (gitleaks)` entre os checks a tornar obrigatórios. ⛔ **Não dava** — o check não
existia para ser exigido. Tornar obrigatório um check que nunca roda deixaria a `develop` travada
para sempre.

**Decisão.** Remover a linha repetida e **plantar o guard que teria pego isto**:
`scripts/ci/check_workflow_hygiene.py`, num job próprio do `ci.yml`. Ele recusa chave duplicada com
um loader estrito — justamente porque o `safe_load` aceita.

**Segundo achado, mesma raiz de "o CI não avisa".** ⛔ Nenhum job de nenhum workflow declarava
`timeout-minutes`, e o default do GitHub é **360 minutos**. Medido no `Frontend tests` (#465):

```
run 32168166726   Install Playwright browsers   17:56 -> 23:55   (6h, cancelado à mão)
run 32165120756   Install Playwright browsers   17:21 -> 17:55   (34min, cancelado à mão)
```

Nos dois, o passo de E2E ficou `skipped` — ⚠️ **o teste nunca foi o culpado**, era o
`npx playwright install --with-deps` (apt no runner). Todos os 17 jobs passam a declarar timeout, com
os números tirados da duração medida em runs verdes, ⛔ não de regra de bolso.

⚠️ **O que isto ⛔ NÃO resolve:** a causa dentro do apt continua sem prova. O que muda é que a próxima
travada produz log em 8 min em vez de silêncio até alguém cancelar.
