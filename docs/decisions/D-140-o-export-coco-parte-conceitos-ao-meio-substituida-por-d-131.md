# D-140 · O export COCO parte conceitos ao meio  ↩ SUBSTITUÍDA por D-131 (não havia duplicata)

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Mantida por ser append-only. **A premissa desta entrada está errada** — ver D-131: os `class_id`
> pequenos são classes do CATÁLOGO, não duplicatas. O defeito real era o JOIN do export.

#### Texto original — `class_id` duplicado por nome

**Status:** ✅ vigente · **adendo a D-109** (que resolveu o "export devolvia ZERO classes custom" e, ao
resolver, deixou este resíduo)

O namespacing de classe custom **funciona** (`class_namespace.py`, `TENANT_CLASS_ID_OFFSET = 100_000`).
⚠️ **Correção de erro cometido dentro desta auditoria:** um subagente concluiu que as anotações apontavam
para classes inexistentes, porque juntou só contra `module_classes`. **Errado** — 12 das 13 resolvem.

O defeito real é outro: **o mesmo conceito tem dois `class_id`.**

| Conceito | `class_id` | Boxes |
|---|---|---|
| Protetor auditivo | 100004 **e** 4 | 197 + 5 |
| mascara | 100006 **e** 6 | 114 + 79 |
| Sem protetor de ouvido | 100007 **e** 7 | 45 + 26 |

E o export monta as categorias COCO **chaveando por `class_id`, não por nome**
(`versioning_v2.py:393-398`: `seen.setdefault(ann["class_id"], ...)`).
**O dataset sai com duas categorias homônimas por conceito, e os exemplos ficam partidos entre duas
classes que o modelo trata como diferentes.**

**466 dos 599 boxes (78%) estão afetados.**
Mais: `class_id=0` não resolve para nada (1 box), e `hardhat` (1) contraria D-103.

A duplicata está **viva, não é resíduo de migração**: os dois espaços foram gravados **nos mesmos dias**
(ambos até 13/08). Nasce em `ModuleClassesPage.tsx`, que oferece "Suas classes" e "Catálogo do módulo"
lado a lado, com nomes equivalentes.

**A decisão:** consolidar por nome no export **e** parar de oferecer as duas listas na anotação.
Duas frentes — corrigir o passado (export) e fechar a torneira (interface).
