# Monitor Andon — spec visual

**Rota:** `/quality/andon/:cameraId` (capturado em `/quality/andon/cam-0042`). `/quality/andon` sem `:cameraId` NÃO existe (catch-all → cameras). Apesar do comentário "sem JWT, acesso por IP interno", a rota vive DENTRO do `QualityLayout` autenticado (submenu visível nos screenshots).
**Fontes:** `apps/frontend/src/modules/quality/pages/QualityAndonDisplay.tsx` · rota: `src/modules/quality/QualityLayout.tsx:85`
**Screenshots:**

| Estado  | Dark | Light |
|---------|------|-------|
| default | `../screenshots/quality-andon/dark-default.png` | `../screenshots/quality-andon/light-default.png` |
| empty   | `../screenshots/quality-andon/dark-empty.png`   | `../screenshots/quality-andon/light-empty.png`   |

Nota: a área do Andon é 100% hardcoded (`#0a0a0a` etc.) — **light == dark** dentro do painel; só o chrome do app muda (visível no light).

## Layout — regiões

- Container: `minHeight:100vh` (dentro do `main` do QualityLayout → extrapola a viewport), `background: #0a0a0a` (flash NOK: `#3a0a0a` por 1.5s, transition 0.3s), flex column centralizado, `fontFamily: monospace`, `color: #fff`, padding 32.
- Pilha vertical central: eyebrow "ANDON MONITOR" → nome da câmera → status gigante → linha de 3 métricas (`gap 48px`) → pill CEP → tira de últimas inspeções (5 quadrados 40×40, gap 8) → rodapé de atualização.

## Árvore de componentes

- `QualityAndonDisplay` (sem UI kit — tudo inline)
  - Eyebrow: 14px `#555`, letterSpacing 0.1em — `ANDON MONITOR`
  - Nome da câmera: 22px/700 `#aaa`
  - Status: 96px/900, letterSpacing −4px — `OK` `#43D186` · `NOK` `#EF5350` · `—` `#555`
  - Métricas: valor 48px/700 (`#43D186` aprovados, `#EF5350` reprovados, `#FFB74D` taxa) + label 12px `#555` uppercase
  - Pill CEP: 16px/600, border 2px + texto na mesma cor — `#EF5350` (fora de controle) / `#43D186` (em controle) / `#888` (sem baseline), radius 4
  - Últimas inspeções: quadrados com bg `rgba(67,209,134,0.2)`/`rgba(239,83,80,0.2)`, border 2px + ✓/✗ 14px/700
  - Rodapé: 11px `#333` — `Atualizado a cada 15s · {hh:mm:ss}`
  - Erro: `#EF5350` 18px

## Copy exata

- `ANDON MONITOR` · `{camera_name}` (fallback: cameraId)
- Status: `OK` / `NOK` / `—`
- Labels: `APROVADOS` · `REPROVADOS` · `TAXA NOK/1H`
- CEP: `⚠ PROCESSO FORA DE CONTROLE` · `✓ PROCESSO EM CONTROLE` · `CEP: SEM BASELINE`
- Rodapé: `Atualizado a cada 15s · 23:51:57`
- Erro: `Erro de comunicação com o servidor`

## Dados de exemplo (fixtures)

- default: `Câmera Bancada A — Close-up`, OK, 318 aprovados, 14 reprovados, 4.2% (nok_rate_1h 0.042), `in_control`, 5 inspeções (✓✓✗✓✓).
- empty: 0 / 0 / 0.0%, status `—`, `cep_status: 'unknown'` → `CEP: SEM BASELINE`, sem tira de inspeções.

## Estados

- **default**: OK gigante verde, CEP verde.
- **empty**: `—` cinza `#555`, contadores zerados, CEP cinza.
- **flash NOK**: fundo vira `#3a0a0a` por 1.5s quando `last_result` muda para nok.
- **erro**: apenas a mensagem vermelha centralizada.
- Poll a cada 15s (`setInterval`); sem estado de loading distinto.

## Navegação e fluxos

- Nenhum elemento interativo — display puro de chão de fábrica.

## Problemas identificados (resumo)

1. **Contraste (ambos os temas, paleta fixa)**: labels 12px `#555` sobre `#0a0a0a` = 2.66:1 (APROVADOS/REPROVADOS/TAXA NOK/1H e eyebrow) — texto pequeno informativo abaixo de 4.5:1; rodapé `#333` = 1.57:1 (praticamente invisível — confirmado no screenshot).
2. **Status vazio `—` em `#555`** (96px, grande, 2.66:1) — abaixo até do mínimo 3:1 para texto grande.
3. **Hardcode intencional**: paleta inteira fixa (`#0a0a0a/#43D186/#EF5350/#FFB74D/#888`), imune ao white-label — aceitável para monitor de fábrica, mas apenas parte tem `// allow`; sem marcação, o guard-rail task-065 vai acusar.
4. **Layout**: `minHeight:100vh` dentro do `main` do QualityLayout soma com topbar/submenu → rolagem/overflow; o "fullscreen sem autenticação" prometido no comentário não existe — herda AppShell + JWT (mesma classe do bug do tablet kiosk).
5. Cores legadas `#43D186/#EF5350` divergem dos tokens `success/danger` do DS (inconsistência tolerada por ser display isolado).

## Findings (develop — 2026-07-07)

> Comparado com _baseline-staging/screens/quality-andon.md · screenshots analisados: dark-default, light-default, dark-empty, light-empty

| # | Severidade | Descrição | Status |
|---|-----------|-----------|--------|
| 1 | P1 | Labels de métricas 12px (`APROVADOS`, `REPROVADOS`, `TAXA NOK/1H`) e eyebrow `ANDON MONITOR` em `#555` sobre `#0a0a0a` = 2.66:1 — abaixo do mínimo WCAG AA para texto pequeno (4.5:1). Rodapé `#333` sobre `#0a0a0a` = 1.57:1 — praticamente invisível (confirmado em ambos os screenshots: rodapé não legível). | PERSISTE |
| 2 | P1 | Status vazio `—` em `#555` (96px, large text) sobre `#0a0a0a` = 2.66:1 — abaixo do mínimo 3:1 para texto grande. Confirmado em `dark-empty.png`: o traço `—` aparece como linha cinza quase invisível no centro da tela. | PERSISTE |
| 3 | P2 | Paleta fixa (`#0a0a0a`, `#43D186`, `#EF5350`, `#FFB74D`, `#555`, `#888`) sem marcação `// allow` completa para todos os literais — guard-rail task-065 vai acusar falsos-positivos. Apenas o fundo `#0a0a0a` tem comentário registrado. | PERSISTE |
| 4 | P2 | `minHeight:100vh` dentro do `main` do QualityLayout → não é fullscreen; submenu e topbar de Qualidade são visíveis em **ambos** os screenshots (dark e light), introduzindo rolagem/overflow vertical não intencional. | PERSISTE |
| 5 | P3 | `#43D186` (OK/aprovados) e `#EF5350` (NOK/reprovados) divergem dos tokens `success #10b981` e `danger #ef4444` do DS — inconsistência tolerada para display de fábrica mas impede reuso de componentes do kit. | PERSISTE |

**Resumo:** 0 resolvidos · 5 persistem · 0 novos. Display imune ao white-label por design; os problemas de contraste (#555/#333 sobre #0a0a0a) são reais mas requerem decisão de produto (paleta do Andon é intencional).
