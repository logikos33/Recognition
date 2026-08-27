# Delta pré-migração — Fase 0 (gate)

**Medido em 2026-08-27** contra `origin/develop @ 04078de8`. O design fechou
contra `98bff30e` (23/08); a develop correu 4 dias nos dois sentidos.

Este documento é o **contrato de funcionamento**: toda conexão mapeada aqui tem
de funcionar no fim da migração, sem exceção.

---

## 0 · Escala real dos dois lados

| | |
|---|---:|
| Front atual — arquivos `.ts/.tsx` (sem teste) | **394** |
| Front atual — linhas | **66.561** |
| Rotas de tela | **31** |
| Endpoints distintos chamados | **66** |
| Arquivos com SocketIO | **28** |
| Envs `VITE_*` | `VITE_API_URL`, `VITE_WS_URL` |
| Handoff — telas hi-fi | **30** |
| Contrato de migração — entradas | **421** |

**Decisão de escopo (Vitor, 27/08):** migração por rotas **coexistindo**; nada
do front atual é removido nesta rodada. Tudo que for do front antigo fica
**sinalizado** (ver §4) para uma etapa própria de remoção, depois que a
migração inteira estiver feita.

---

## 1 · Lado BACKEND — o contrato do design sobreviveu

Cruzamento programático de `contrato-dados.js` (421 entradas) contra o
`url_map` REAL da API de hoje (432 rotas, extraído de `create_app()`):

```
existe com o método certo : 421
rota existe, método difere:   0
rota AUSENTE na API       :   0
```

🟢 **421/421.** Zero divergência, apesar de **58 commits de backend** desde o
snapshot do design. Nenhum dos 16 pedidos ao backend virou bloqueio: as rotas
que o design assumiu existem todas.

Situação declarada no contrato, para referência:

| situação | n |
|---|---:|
| FRONT-ATUAL | 207 |
| GAP-DE-PRODUTO | 122 |
| ÓRFÃO | 61 |
| BACKEND-ONLY | 31 |

---

## 2 · Lado FRONT — o que a develop ganhou desde 23/08

**10 commits, 34 arquivos, +2.702 linhas.** Cruzados um a um com o handoff:

| # | o que a develop ganhou | onde | coberto pelo handoff? | decisão |
|---|---|---|---|---|
| 1 | **Colunas Evento × Veredito** separadas (polaridade ≠ julgamento humano) | `AlertsHistoryPage`, `VereditoHumano.tsx` | **conceito coberto**, detalhe ausente — o handoff tem coluna de veredito, não a disjunção de paleta | **implementar-na-migração** |
| 2 | **Badge de procedência** (`ProcedenciaBadge.tsx`) | histórico + detalhe | ausente | **implementar-na-migração** |
| 3 | **Viewer zoom + pan** com caixa ancorada (`lupaEvidencia.ts`) | `AlertDetailPage` | coberto (Evento Detalhe prevê evidência) — sem zoom | **implementar-na-migração** |
| 4 | **Deep-link do alerta** `/epi/alerts/:id` | `AlertDetailPage` (628 linhas novas) | coberto (`/epi/eventos/:id`) | **migrar de rota** |
| 5 | **Motivo do veredito** (campo + envio) | `AlertDetailPage` | ausente | **implementar-na-migração** |
| 6 | **Filtro por classe** nos eventos | `AlertsHistoryPage` | coberto | migrar |
| 7 | **Polaridade em /module-classes** (3 estados + catálogo só-leitura) | `ModuleClassesPage`, `PolaridadeClasse.tsx` | ausente (Estúdio F5) | **implementar-na-migração** (F5) |
| 8 | **Aba escopo por câmera** + rota em lote | `CameraModelScope.tsx` | ausente | **implementar-na-migração** (F3 Câmeras) |
| 9 | **Fila por incerteza** (`?ordenar=incerteza`) | backend + Estúdio | ausente | **implementar-na-migração** (F5) |
| 10 | **JWT no handshake do socket** (sai da query string) | 6 hooks de socket | n/a — infra | **preservar** |

⛔ **Nada disso pode se perder.** Cada item tem tela de destino nomeada acima.

---

## 3 · Rotas do front atual × handoff

| cobertura | n |
|---|---:|
| coberta por tela do handoff | **12** |
| **SEM DESENHO** → lista do design | **10** |
| redirect / técnica | 9 |

### 3.1 De-para das cobertas

| rota atual | rota nova | tela do handoff | fase |
|---|---|---|---|
| `/epi/dashboard` | `/epi/dashboard` | EPI Dashboard | F3 |
| `/epi/alerts` | `/epi/eventos` | EPI Eventos | F3 |
| `/epi/alerts/:alertId` | `/epi/eventos/:id` | EPI Evento Detalhe | F3 |
| `/epi/verification` | `/epi/verificacao` | EPI Verificação | F3 |
| `/epi/reports` | `/epi/relatorios` | EPI Relatórios | F3 |
| `/epi/cameras` | `/epi/cameras` | EPI Câmeras | F3 |
| `/epi/monitoring` | `/epi/live` | EPI Ao Vivo | F3 |
| `/epi/training` | `/estudio/*` | Estúdio | F5 |
| `/epi/training/classes` | `/estudio/classes` | Estúdio | F5 |
| `/epi/counting` · `/fueling/*` | `/carga/*` | Carga | F4 |

A maioria muda de caminho — **por isso a coexistência é natural**: as rotas
novas não colidem com as antigas.

### 3.2 🔴 SEM DESENHO — vão para a lista do design

Estas dez existem e funcionam hoje, e **não têm tela no handoff**:

| rota | componente | o que faz |
|---|---|---|
| `/modules` | `ModuleSelectionPage` | seleção de módulo |
| `/epi/cameras/triagem` | `CameraTriagePage` | triagem de câmeras |
| `/epi/cameras/:id/operations` | `EpiOperationsPage` | operações por câmera (zona EPI) |
| `/epi/cameras/:id/scenario` | `EpiScenarioEditorPage` | editor de cenário |
| `/epi/health` | `StreamHealthRedirect` | saúde de streams |
| `/epi/sites-health` | `SitesHealthRedirect` | saúde de sites |
| `/epi/sites` | `EpiSitesPage` | sites do tenant |
| `/epi/edge-observability` | `DashboardIntegradoPage` | observabilidade do edge |
| `/epi/investigation` | `InvestigationPage` | investigação |
| `/monitoring` | `EdgeMonitoringGate` | portão de monitoramento |

⛔ **Não se inventa tela sem desenho.** Enquanto o design não desenhar, elas
seguem **no front atual, acessíveis**, e a nav nova aponta para elas. Entram na
`LISTA-PARA-O-DESIGN-v2.md`.

---

## 4 · Marcação do front antigo (pedido do Vitor)

Nada é removido nesta rodada. Para a etapa de remoção ser mecânica e não
arqueologia, cada arquivo do front atual entra em
**`docs/migration/MANIFESTO-FRONT-ANTIGO.md`** com:

`caminho · rota que serve · status {MIGRADO | PENDENTE | SEM-DESENHO | INFRA}`

O status vira `MIGRADO` no PR da fase que o substitui. A remoção só pode
apagar o que estiver `MIGRADO`, e há teste que trava a remoção de qualquer
outro estado.

---

## 5 · Mapa de conexões — o contrato de funcionamento

O JSON completo (`rota de tela → endpoints → socket → env`) está em
`docs/migration/mapa-conexoes-front-atual.json`. Resumo:

- **66 endpoints** distintos chamados pelo front atual — todos existem na API
  (conferido no §1).
- **28 arquivos** usam SocketIO, via 6 hooks. Todos passaram a mandar o JWT no
  **handshake `auth`**, não na query string.
- **2 envs**: `VITE_API_URL`, `VITE_WS_URL`.

**Regra do aceite:** no fim da migração, cada uma dessas conexões tem de
funcionar pela tela nova ou continuar funcionando pela tela antiga marcada
`SEM-DESENHO`. Nenhuma pode simplesmente sumir.
