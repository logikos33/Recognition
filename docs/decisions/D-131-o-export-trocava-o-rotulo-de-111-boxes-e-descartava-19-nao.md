# D-131 · O export trocava o rótulo de 111 boxes e descartava 19 — não havia duplicata nenhuma

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **↩ corrige D-123**, que estava errada de ponta a ponta

D-123 afirmava que o mesmo conceito tinha dois `class_id` e que 78% dos boxes estavam partidos.
**Não existe duplicata.** O `class_name` gravado na própria linha mostra o que o humano escolheu:
`class_id` 0/1/4/5/6/7 são **classes do catálogo** (`module_classes`: Capacete, Sem Capacete, Luvas,
Sem Luvas, Óculos, Sem Óculos). `class_id` 100004+ são as classes do tenant. **Classes diferentes.**

O defeito estava só no **export**, que reconstruía o nome via `JOIN yolo_classes` — violando a regra que o
próprio repositório documenta (*"class_name é armazenado na própria linha (task-077), NUNCA reconstruído
via JOIN em yolo_classes"*):

| Verdade gravada | Exportado como | Efeito | Boxes |
|---|---|---|---|
| Óculos | **mascara** | rótulo trocado | 79 |
| Sem Óculos | **Sem protetor de ouvido** | rótulo trocado | 26 |
| Luvas | **Protetor auditivo** | rótulo trocado | 5 |
| Sem Capacete | **hardhat** (tenant `e2e`) | rótulo trocado **cross-tenant** | 1 |
| Sem Luvas | — | descartado (classe arquivada) | 18 |
| Capacete | — | descartado (join não acha) | 1 |

**130 de 599 boxes (21,7%)** corrompidos ou perdidos em todo export. O modelo aprenderia "mascara" a
partir de fotos de óculos.

**Consertado:** `class_name` vem da linha; o `LEFT JOIN` sobrou só para checar classe custom aposentada,
**escopado por tenant** (fecha a leitura cross-tenant, C-01).

⛔ **NENHUM `UPDATE` em `frame_annotations` foi executado** — as anotações estavam corretas.
Backup preventivo mesmo assim em `~/Logikos-mutirao/backups/frame_annotations_pre_remap_2026-08-17.csv`
(857 linhas, fora do repositório).

⚠️ **"Protetor auricular" tem ZERO anotações** — a mescla autorizada em `Protetor auditivo` ficou sem
objeto. Nada foi mesclado.
