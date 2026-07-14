# Postmortem Template — [Título curto do incidente]

**Status:** Rascunho — preencher em até 48h após resolução
**Criado em:** _[data de criação deste documento]_

> Copiar este arquivo para `docs/runbooks/postmortem-YYYY-MM-DD-slug.md` e preencher todas as seções.
> Este é um processo **blameless**: o objetivo é entender falhas de sistema e processo, nunca atribuir culpa
> a pessoas. Ver skill `engineering:incident-response` para o workflow completo de resposta a incidentes
> (triagem → comunicação → postmortem).

---

## Metadados

| Campo | Valor |
|-------|-------|
| **Data do incidente** | _[preencher — YYYY-MM-DD HH:MM]_ |
| **Autor do postmortem** | _[preencher]_ |
| **Participantes da resposta** | _[preencher]_ |
| **Severidade** | _[P0 / P1 / P2 / P3 — ver tabela de Classificação de Impacto no CLAUDE.md]_ |
| **Serviços afetados** | _[ex: api-v3, worker, frontend, inference-service...]_ |
| **Ambiente** | _[staging (produção) / develop / local]_ |
| **Duração total** | _[preencher — do primeiro impacto à resolução]_ |

---

## Resumo executivo

_2-3 frases: o que aconteceu, impacto principal, como foi resolvido. Deve ser legível por alguém sem
contexto técnico do incidente._

_[preencher]_

---

## Impacto

_Quantificar o dano real, não o potencial. Ser específico._

- **Usuários/tenants afetados:** _[preencher — quantos, quais, todos ou subset]_
- **Dados:** _[perda, corrupção ou exposição de dados? Se sim, detalhar. Se não, declarar explicitamente "nenhum impacto em dados"]_
- **Downtime:** _[preencher — serviço totalmente indisponível vs degradado]_
- **SLA/SLO violado:** _[preencher, ou "N/A"]_

---

## Linha do tempo

_Todos os horários em UTC-3 (horário de Brasília), salvo indicação contrária. Basear em logs/alertas reais,
não em memória._

| Horário | Evento |
|---------|--------|
| _[HH:MM]_ | Detecção — _[como foi detectado: alerta, health check, relato de usuário...]_ |
| _[HH:MM]_ | Escalonamento — _[quem foi acionado, como]_ |
| _[HH:MM]_ | Diagnóstico — _[hipótese inicial da causa]_ |
| _[HH:MM]_ | Mitigação — _[ação que estancou o impacto, ex: rollback, feature flag, restart]_ |
| _[HH:MM]_ | Resolução — _[quando o serviço voltou ao normal confirmado]_ |
| _[HH:MM]_ | Postmortem publicado | _[preencher]_ |

---

## Causa raiz

_Descrição técnica da causa. Preferir causa raiz de sistema/processo sobre "erro humano" — se um humano
cometeu um erro, perguntar por que o sistema permitiu que esse erro chegasse a produção._

_[preencher]_

### 5 whys (opcional)

1. Por que o incidente aconteceu? _[preencher]_
2. Por que isso foi possível? _[preencher]_
3. Por que isso não foi pego antes? _[preencher]_
4. Por que o processo/sistema permitiu isso? _[preencher]_
5. Causa raiz sistêmica: _[preencher]_

---

## O que funcionou bem / o que não funcionou

_Blameless: foco em sistemas, ferramentas e processos — nunca em nomes de pessoas ou "quem errou".
Se um passo manual falhou, a pergunta é "por que dependíamos de um passo manual", não "quem esqueceu"._

**Funcionou bem:**
- _[preencher]_

**Não funcionou / lacunas:**
- _[preencher]_

---

## Ações corretivas

_Cada ação relevante deve virar uma task rastreável em `tools/agent-driver/tasks/` (usar `_TEMPLATE.md`
como base) ou um item de ADR em `docs/decisions/adr/` se envolver decisão arquitetural. Se a mitigação
envolveu rollback, referenciar `docs/ROLLBACK.md`._

| Ação | Dono | Prazo | Status | Task/ADR |
|------|------|-------|--------|----------|
| _[preencher]_ | _[preencher]_ | _[preencher]_ | _[Pendente/Em andamento/Concluído]_ | _[link para tools/agent-driver/tasks/task-NNN-*.md]_ |

_Lembrar de registrar a resolução do incidente no `docs/CHANGELOG.md` quando aplicável (fix de bug em produção)._

---

## Lições aprendidas

_O que a organização deve levar deste incidente além das ações corretivas pontuais — padrões a evitar,
processos a revisar, monitoramento a reforçar._

_[preencher]_

---

## Nota de rodapé

Este documento segue o princípio de **postmortem blameless**: o valor de um postmortem vem de as pessoas
se sentirem seguras para descrever exatamente o que aconteceu, sem medo de punição. Erros individuais são
sintomas de lacunas em sistemas, testes, revisões ou automações — é isso que este documento deve corrigir.
Para o processo completo de resposta a incidentes (triagem, comunicação, escrita de postmortem), usar a
skill `engineering:incident-response` como referência.
