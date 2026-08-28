# Handoff v2 — as 4 funções que faltam no módulo EPI

Rascunhos de design para as quatro funções que a comparação de paridade
(`docs/migration/PARIDADE-ANTIGO-VS-NOVO.md`) confirmou como perdidas no front
novo e que o handoff original **não desenhou**. Enquanto elas não existirem, as
telas antigas correspondentes não podem ser apagadas.

| artboard | função | tela antiga que ainda segura |
|---|---|---|
| `Main.dc.html` | ajustar câmera (FPS, qualidade, resolução da coleta) + saúde do equipamento | `CameraFpsConfig` em Câmeras e Monitoramento |
| `CorrigirCaixa.dc.html` | corrigir a caixa da detecção, por arrasto e por teclado | `AlertDetailPage` |
| `ParedeCameras.dc.html` | montar a parede: câmera por quadro, arrastar, layouts salvos | `CameraGrid` + `cameraGridStore` |
| `RankingCameras.dc.html` | ranking das câmeras com mais eventos | `TopCamerasWidget` |

## Os campos são reais

Nenhum campo foi inventado — os VALORES são de exemplo, os CAMPOS saíram do
código:

- telemetria: `gpu_pct`, `gpu_mem_pct`, `cpu_pct`, `queue_depth`,
  `inference_fps`, `inference_latency_ms`, `gpu_temp_c`, `decode_pct`
  (`components/cameras/CameraFpsConfig.tsx`)
- FPS 1/5/10/15/30 · qualidade `low`/`medium`/`high` · coleta
  `Principal (máxima)` / `Substream (704×480)`
- caixa: `[x, y, largura, altura]` em PIXELS do frame original, canto superior
  esquerdo; grava por `PATCH /alerts/:id/violations` com
  `{correcoes:[{index, bbox}]}`; autoria em `correcao_ultima.por`
- ranking: `by_camera` de `GET /api/v1/events/summary`
- layouts da parede: máximo 10 (hoje em `localStorage` `epi-camera-grid`)

## Como mexer

Os `.dc.html` são a fonte. Para atualizar o canvas publicado, edite-os e
re-semeie — não edite o `.html` gerado.

## Decisões tomadas no rascunho, para conferência

1. O aviso de **coleta em alta com operação em baixa** virou bloco âmbar
   explícito: é o caso em que o modelo treina em imagem melhor do que a que ele
   vê rodando, e isso merece peso na tela.
2. No ranking, só as **três primeiras** posições recebem ciano. Pintar as dez de
   acento gastaria o acento e furaria a regra do ≤10%.
3. O **shell está inline** em cada artboard porque o canvas do preview não
   resolve os `dc-import` do handoff. No projeto do handoff, trocar por
   `<dc-import name="EPI Topbar">` e `<dc-import name="EPI Sidebar">`.

## Em aberto (decisão do Vitor)

O layout salvo da parede hoje vive no navegador de quem salvou. Deve ser por
**usuário** (no servidor) ou por **site** (a parede da portaria é a mesma para
quem sentar ali)? A resposta decide se precisa de endpoint novo.
