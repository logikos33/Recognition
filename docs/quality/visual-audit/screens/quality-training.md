# Treinamento (contexto Qualidade) — spec visual

**Rota:** `/quality/training` — renderiza a **mesma** `TrainingPage` compartilhada de `/epi/training` (`QualityLayout.tsx:83` → `import { TrainingPage } from '../../pages/TrainingPage'`). A cobertura completa de tabs Modelo/Treino ao Vivo, modais e hovers está na spec do grupo 16 (`epi-training.md`); aqui documenta-se o contexto Qualidade (tab Imagens rica + empty).
**Fontes:** `apps/frontend/src/pages/TrainingPage.tsx` (compartilhada) · `apps/frontend/src/modules/quality/QualityLayout.tsx` · **atenção:** `src/modules/quality/pages/QualityTrainingPage.tsx` existe mas NÃO é referenciado por nenhuma rota (dead code).
**Screenshots:**

| Estado  | Dark | Light |
|---------|------|-------|
| default | `../screenshots/quality-training/dark-default.png` | `../screenshots/quality-training/light-default.png` |
| empty   | `../screenshots/quality-training/dark-empty.png`   | `../screenshots/quality-training/light-empty.png`   |

## Layout — regiões

- AppShell + submenu Qualidade (item ativo: **Treinamento**).
- Título `Treinamento` (h1) + tabs horizontais: **Imagens (96)** (ativa, sublinhado ciano) · Modelo · Treino ao Vivo.
- Dropzone de upload full-width (borda tracejada, radius ~10): ícone upload + texto.
- Barra de filtro: `Filtro:` + 3 pills (Todas ativa em `primary`; Anotadas; Sem anotação) + contador "96 imagens" à direita.
- Grade de thumbnails 8 colunas × 2+ linhas (24 por página), cards com imagem SVG escura "bancada-a-closeup", rótulo `#210…#635`, badge circular verde (anotada) no canto inferior direito.
- Paginação central: `← Anterior` (disabled) · `Página 1 de 4` · `Próxima →`.

## Árvore de componentes

- `TrainingPage` (tabs) → tab Imagens: Dropzone, FilterPills, ImageGrid (thumb + label + badge de anotação), Pagination. Detalhes por componente na spec do grupo 16.

## Copy exata (visível neste contexto)

- `Treinamento` · tabs `Imagens (96)` / `Modelo` / `Treino ao Vivo`
- Dropzone: `Arraste imagens (JPG/PNG/WebP) ou clique — até 50 por vez`
- Filtro: `Filtro:` · `Todas` · `Anotadas` · `Sem anotação` · `96 imagens` / `0 imagens`
- Paginação: `← Anterior` · `Página 1 de 4` · `Próxima →`
- Vazio: `Nenhuma imagem de treino. Faça upload de imagens ou envie vídeos para extração de frames.`

## Dados de exemplo (fixtures)

- 96 frames (`total: 96, page_size: 24, total_pages: 4`), ids `#210` a `#635` (passo 25), `is_annotated: i % 4 !== 0` (3 de cada 4 com badge verde).
- Thumbnails: SVG mock via `GET /api/training/frames/<id>/image`.
- Empty: `frames: [], total: 0`.

## Estados

- **default**: grade rica, filtro "Todas" ativo.
- **empty**: dropzone + pills + "0 imagens" + frase de vazio (bom: orienta a ação — upload ou vídeo).
- Demais estados (upload em progresso, tab Modelo, modal de treino, hovers) → cobertos no grupo 16.
- `useTrainingSocket` degrada silenciosamente sem backend (sem erro visual).

## Navegação e fluxos

- Tabs alternam conteúdo local; pills filtram a listagem (`GET /api/training/images?...`); paginação avança páginas; dropzone abre file picker.
- Poll `GET /api/training/jobs/current/status` a cada 3s.

## Problemas identificados (resumo)

1. **Dead code com hardcodes**: `QualityTrainingPage.tsx` (215 linhas) não é roteado por nada, mas contém `#4FC3F7`, `#FFB74D`, `#43D18622` e `alert()` nativos — se um dia for ligado, reintroduz a paleta legada; candidato a remoção ou ao guard-rail task-065.
2. **Tema light OK nesta tela**: thumbnails permanecem escuros por serem imagens (fixture), não defeito.
3. Achados de contraste/hover da `TrainingPage` em si pertencem ao grupo 16 (mesmo componente em `/epi/training`) — não duplicados aqui.

## Findings (develop — 2026-07-07)

> Comparado com _baseline-staging/screens/quality-training.md · screenshots analisados: dark-default, light-default, dark-empty, light-empty

| # | Severidade | Descrição | Status |
|---|-----------|-----------|--------|
| 1 | P3 | `QualityTrainingPage.tsx` (dead code, 215 linhas) contém `#4FC3F7`, `#FFB74D`, `#43D18622` e `alert()` nativos — não é roteado por nada mas viola o guard-rail task-065 se o CI varrer arquivos não-exercitados. Candidato a remoção. | PERSISTE |

**Observações positivas:**
- `TrainingPage` compartilhada renderiza corretamente em ambos os temas neste contexto: título "Treinamento" visível no claro (`textPrimary` tokenizado), tab ativa com sublinhado ciano (`primary` do DS), pills de filtro e grid de thumbnails sem issues visuais.
- Empty state texto visível em dark (ciano) e light (textMuted) — ambos legíveis.
- Grid apresenta 9 colunas de thumbnails (viewport 1280px) — spec indicava 8; comportamento responsivo, não defeito.

**Resumo:** 0 resolvidos · 1 persiste · 0 novos. Tela bem comportada após WS1 — `TrainingPage` componente estava tokenizado previamente.
