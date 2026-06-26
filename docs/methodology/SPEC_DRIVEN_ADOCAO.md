# Spec-Driven Development — Adoção no Recognition

> **Origem:** "Manual de Spec-Driven Development para Projetos de Dados" (Data Squad, v2.0), baseado no
> GitHub Spec Kit (2025), Nygard (ADR, 2011), Evans (DDD/Ubiquitous Language, 2003), dbt/data-quality (HARNESS).
> **Propósito deste doc:** registrar a metodologia (memória de longo prazo), mapear ao estado atual do
> Recognition, e listar as melhorias priorizadas a aplicar no nosso fluxo (incluindo o desenvolvimento
> autônomo via agent-driver).
> **Data:** 2026-06-03 · **Status:** ✅ Aceito (vivo).

---

## 1. A inversão Spec-Driven (a tese)

"Especificações não servem ao código; código serve às especificações." A SPEC é o artefato primário;
código é a expressão da SPEC numa linguagem. Manter o software = evoluir a SPEC e regenerar. Três forças
tornam isso necessário agora: IA gera código a partir de linguagem natural; complexidade cresce; ritmo de
mudança acelera (pivôs viram regeneração, não reescrita).

Por que importa pra nós: resolve a dor crônica de **regra de negócio que migra do documento pra cabeça de
quem implementou**. No modo autônomo (agent-driver), a SPEC é o contrato que o agente respeita — a qualidade
da SPEC determina a qualidade do output (lição do task-002, ver §5).

## 2. Os sete artefatos — o que cada um responde

| Artefato | Pergunta que responde | Quando criar | Vida |
|---|---|---|---|
| **Constitution** | Quais princípios não podemos violar? | Início | Imutável (emendas raras) |
| **SPEC** | O que construir e por quê? | Antes de cada feature | Vida do componente |
| **PLAN** | Como implementar tecnicamente? | Após SPEC aceita | Até próxima geração |
| **TASKS** | Em qual ordem executar? | Após PLAN | Até implementação |
| **ADR** | Por que X em vez de Y? | Quando há trade-off real | Imutável |
| **HARNESS** | Como provamos que está correto? | Componente com baseline | Vida do projeto |
| **GSD** (Glossary & Shared Definitions) | O que esse termo significa aqui? | Início + evolui | Vida do projeto |

> ⚠️ **Colisão de sigla:** o manual chama de **GSD** o *Glossary & Shared Definitions* (linguagem ubíqua /
> DDD). No nosso repo, `docs/architecture/GSD.md` é o *Global System Document* (visão de sistema). São
> coisas diferentes. Para não confundir, o glossário de domínio (o GSD do manual) deve se chamar
> **"Glossário / Linguagem Ubíqua"** aqui.

## 3. Fluxo canônico: SPEC → PLAN → TASKS → IMPLEMENT

1. **SPEC** — *o que e por quê*, sem tecnologia. User stories + critérios de aceite verificáveis + edge cases.
2. **PLAN** — *como*, com stack. Data-model, contratos, alternativas, gates da Constitution.
3. **TASKS** — lista numerada com dependências e marcador `[P]` (paralelizável).
4. **IMPLEMENT** — agente executa com **supervisão humana a cada PR**. "Humano dirige, agente faz o grosso."

ADR, HARNESS e GSD vivem em paralelo: a Constitution injeta gates no PLAN; o GSD é referenciado pela SPEC;
o ADR ancora decisões técnicas; o HARNESS define o critério de aceite quantificado.

## 4. Mapeamento ao Recognition — o que já temos

| Artefato (manual) | No Recognition | Status |
|---|---|---|
| Constitution | `/constitution.md` (C-01..C-08) | ✅ Temos |
| ADR | `docs/decisions/adr/0001..0019` (template Nygard) | ✅ Temos |
| HARNESS | `tests/harness/migrations/` + plano O/D | ✅ Temos (e crescendo) |
| SPEC/PLAN/TASKS | `tools/agent-driver/tasks/task-NNN-*.md` + EDGE_DEPLOYMENT_PLAN | ⚠️ Parcial (SPEC e PLAN misturados) |
| GSD (glossário/linguagem ubíqua) | — | ❌ **Lacuna** |
| Global System Doc | `docs/architecture/GSD.md` | ✅ (outro artefato, ver §2) |

Conclusão: a fundação está madura. As lacunas são (a) glossário de domínio e (b) a separação/qualidade das
specs — que é onde mais ganhamos no modo autônomo.

## 5. Melhorias priorizadas (o "tudo de bom" a aplicar)

### M1 — Protocolo [NEEDS CLARIFICATION] (maior ROI, aplica já)
A inovação mais valiosa do template Spec Kit: ao escrever uma spec, **se você está assumindo algo sem ter
confirmado, marque `[NEEDS CLARIFICATION: pergunta]` em vez de chutar**. Spec com NEEDS CLARIFICATION pendente
**não vai pra "Aceito"** — é bloqueante.

Por que é ouro pra nós: o bug de isolamento multi-tenant do task-002 entrou porque a spec *assumiu* o modelo
de atribuição de tenant (claims vs enrollment) e chutou errado. Um `[NEEDS CLARIFICATION: device auto-assina
o token ou o servidor emite? fonte de atribuição de tenant?]` teria travado a spec antes do agente rodar.
**Ação:** adicionar uma seção "NEEDS CLARIFICATION" ao template de task spec; instruir o agent-driver a
PARAR e emitir a dúvida em vez de adivinhar (reforça o C-04 "ver o real, não assumir").

### M2 — Criar o GSD / Glossário de domínio (lacuna)
Recognition tem vocabulário denso: tenant, site, edge, device, enrollment token vs device token, heartbeat,
deployment_mode (cloud/edge/hybrid), módulos (epi/fueling/quality/counting/operations), classes EPI
(helmet/no_helmet/vest...), DeepSORT/track_id, RTSP/MediaMTX, etc. Sem glossário, cada spec redefine e
ambiguidade acumula. **Ação:** criar `docs/gsd/glossario.md` (linguagem ubíqua): termos + definição + onde
aparece + regras transversais numeradas (R1, R2...). Specs referenciam §X em vez de duplicar.

### M3 — Reestruturar o template de task spec (WHAT/WHY-first + test-first)
O manual separa SPEC (intenção) de PLAN (tecnologia). Nossas task specs misturam — o que é aceitável para o
driver (o agente precisa de concretude), mas a ordem importa: **liderar com critérios de aceite verificáveis
e invariantes de segurança/negócio (test-first)**, e tratar dicas de implementação como secundárias. É nos
critérios de aceite que o bug entra ou é barrado. **Ação:** atualizar `tools/agent-driver/tasks/_TEMPLATE.md`
com: metadados (status, owner, ADRs/GSD referenciados) → resumo (o quê/porquê) → critérios de aceite
(checklist verificável) → invariantes (C-01 multi-tenant, C-05 segurança) → NEEDS CLARIFICATION → dicas de
implementação (opcional) → eval/checkpoint.

### M4 — Checklist arquitetural de PR (gate de revisão)
Toda PR não-trivial responde: tem SPEC? respeita a SPEC? nova regra de negócio → está no GSD? nova métrica →
entra no HARNESS? violou artigo da Constitution → documentado? **Ação:** usar esse checklist nas validações
de PR (humano hoje; vira gate quando subirmos pra L2/auto-merge).

### M5 — Estados de ciclo de vida nos artefatos (leve)
Badges: 📝 Rascunho · 🔍 Revisão · ✅ Aceito · ⊘ Substituído · ⚠ Deprecado. Só specs ✅ Aceito são executadas
pelo driver. **Ação:** header de status nas task specs; o driver pode recusar rodar spec não-Aceita.

### M6 — "Violação justificada, nunca silenciosa" (Complexity Tracking)
A Constitution não impede flexibilidade — força flexibilidade *documentada*. Quando uma feature precisa
violar um princípio, registra a exceção e o porquê. **Ação:** campo "Exceções/Complexity Tracking" nas specs
que desviam de um C-NN.

## 6. Anti-patterns a evitar (do manual, mapeados a nós)

- **NEEDS CLARIFICATION resolvido em silêncio** → foi exatamente o task-002. Bloquear.
- **Constitution decorativa** → gates definidos mas pulados. O code review/CI bloqueia.
- **HARNESS sem baseline confiável** → compara consigo mesmo. Nosso harness de migrations usa Postgres real
  como baseline; o futuro eval de modelo precisa de dataset de validação nomeado (ver EVALS.md).
- **GSD que envelhece** → nomear owner e revisar.
- **ADR aspiracional** → sem ≥2 alternativas reais avaliadas, rejeitar.
- **SPEC com HOW demais** → para nós é nuance (o driver precisa de concretude), mas a intenção/critérios vêm primeiro.

## 7. Ordem de aplicação sugerida

1. **M1** (NEEDS CLARIFICATION no template + constituição) — barato, previne a classe de bug do task-002.
2. **M3** (reestruturar _TEMPLATE.md test-first) — junto com M1.
3. **M2** (glossário de domínio) — pode ser uma task do próprio driver.
4. **M4/M5/M6** — incorporar ao fluxo de revisão e ao driver conforme subimos para L2.

> Princípio final do manual: a combinação SPEC + PLAN + ADR + HARNESS + GSD + Constitution dá ao time uma
> **memória de longo prazo que sobrevive a turnover, refatoração e mudança de stack**. É exatamente o que
> protege o Recognition conforme a autonomia (agent-driver) acelera a produção.
