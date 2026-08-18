# D-114 · Tela de classificação rápida por recorte + taxonomia estendida (adendo a D-103/D-104)

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-105→D-114** na consolidação do merge #384 (D-105 já em uso na develop).

**Problema.** 22 de 29 câmeras têm zero anotação e desenhar caixa custa ~20 s. Anotação 100% automática
(SAM+DINOv2, 1005 propostas) **falhou** — metade das classes é AUSÊNCIA (*sem protetor*, *sem máscara*,
*uso incorreto*) e ausência não tem aparência para propagar. **Não repetir.**

**Decisão.** Nova aba **Classificar** em `TrainingPage` que tira o trabalho braçal do caminho do humano:
mostra UM recorte de pessoa (crop do bbox, via `crop_person` YOLOX-nano ONNX no edge) e o humano marca,
por **tipo de EPI**, um **estado** — em vez de desenhar. Evolução do `SearchFindingsPanel` (reusa
`cropStyle`, criação de classe inline), não uma segunda UI. Meta ≤3 s/recorte, teclado primeiro.

**Os 4 tipos e estados** (estados exclusivos DENTRO do tipo → impossível marcar "com" e "sem" na mesma
pessoa; multilabel ENTRE tipos):

| Tipo | Estados | Classe no banco |
|---|---|---|
| Proteção auditiva | Presente · Ausente · Não visível | `Protetor auditivo` / `Sem protetor de ouvido` ✅ |
| Máscara | Presente · Ausente · Uso incorreto · Não visível | `mascara` / `Sem mascara` ✅ · `Uso incorreto` ⚠ criar |
| Botas | Presente · Ausente · Não visível | `Botas` ⚠ · `Sem botas` (script r1a) ⚠ criar |
| Óculos de proteção | Presente · Ausente · Não visível | `Óculos` / `Sem óculos` ⚠ criar |

**Óculos entra** (decisão Vitor, 15/08) — presente e ausente. Nenhum outro EPI (luvas/uniforme/respirador
descartados). **Não visível / Não sei / Pular / Reprovar ⛔ não entram no dataset.** Aprovar grava 1
`frame_annotation` por estado presente/ausente ativo, todos no bbox da pessoa, `source='manual'` (D-39).

**Estado da tela ≠ classe do banco.** Mapa `estado→class_id` derivado em runtime de `GET /api/classes`
(`versioning_v2`), nunca hardcoded. Estado sem classe → tela **grava e sinaliza "classe a criar"**, e o
recorte **fica na fila** — jamais perde o julgamento do humano por falta de linha no banco.

**Classes novas.** `Sem botas` pronto via `scripts/ops/add_epi_classes_rvb.py` (env-gated, `CONFIRM_OPS=1`,
seed manual — não migration, D-84). `Óculos`/`Sem óculos`/`Uso incorreto`: **pendente de verificação no DB
real** antes de criar (a contagem só mostra classes com caixas; classe vazia não apareceria — risco de
duplicata). r1a documenta que `Óculos`(6)/`Sem óculos`(7) podem já existir como `module_classes` globais
anotadas — **Vitor confirma no banco e cria só o que faltar**, seguindo a convenção do par auricular.

**Como aplicar.** Deep-link da matriz de Cobertura (D-104): célula/lacuna (já carrega `class_id`+`camera_id`)
leva à fila de classificação daquela câmera/classe. Minerador do DVR (bloco 2) alimenta a fila com recortes
`source='nvr'`. Split de treino por câmera+dia já garantido (`versioning_v2._group_key`). O gate de docs
(regra 6, PR #376) ainda não está na develop; quando entrar, sincronizar a lista de classes em `CLAUDE.md`
e `ROTEIRO_ANOTACAO_VITOR.md`.
