# Task 060 — Arquitetura de Streaming para Escala (gateway dedicado / transcode no edge)

**Status**: PENDING (FOLLOW-UP — não bloqueia o teste de dev da 059)
**Risk**: P0-CRITICO (arquitetura multi-serviço; toca o caminho de vídeo em produção)
**Branch**: feat/task-060-streaming-architecture-scale

## Por quê

A task-059 desbloqueou o live view rodando FFmpeg **no próprio container da API** (LocalStreamManager
singleton). Isso funciona em **DEV/single-replica**, mas **não escala**:

- Singleton-por-container: com 2+ réplicas da API, `serve_hls` da réplica B não acha os segmentos
  escritos pela réplica A → volta o **mesmo 404 cross-container**, agora entre réplicas.
- Transcode (1 FFmpeg por câmera) roda no **tier HTTP** → 28 câmeras = 28 processos competindo com o
  atendimento de requisição; escalar horizontal fica impossível.

Decisão registrada em **ADR-0030** (a 059 deve criar): "transcode no tier da API = solução de dev,
não de produção". Esta task entrega a arquitetura de produção.

## Objetivo

Mover o transcode RTSP→HLS pra fora do tier web, de forma que escale e não reintroduza o bug de
isolamento — coerente com o modelo de borda (RVB usa Jetson, onde a nuvem nem puxa a câmera).

## Caminhos a avaliar (ADR-0030 decide)

1. **Serviço `camera-gateway` dedicado** (o que `_is_gateway_online()` espera e hoje não existe):
   processo(s) de transcode separados da API, com storage de segmentos **compartilhado/roteável**
   (não `/tmp` local por réplica) — ex.: volume compartilhado, ou cada gateway serve seu próprio HLS
   e a API só redireciona/proxya pra instância certa (afinidade câmera→gateway).
2. **Transcode no edge (Jetson)**: no site do cliente, o edge já decodifica o RTSP; expor o HLS a
   partir do edge (via túnel MikroTik/WireGuard, ADR-0020) — a nuvem não transcoda nada. É o modelo
   da RVB.
3. **Híbrido**: edge quando há edge no site; gateway na nuvem para câmeras conectadas direto à nuvem.

## Entregáveis

- [ ] **ADR-0030** finalizado: modelo de streaming de produção + por que o LocalStreamManager é só dev.
- [ ] Serviço/roteamento de transcode fora do tier web (caminho escolhido no ADR).
- [ ] Afinidade câmera→instância OU storage de segmentos roteável — sem 404 cross-réplica.
- [ ] Teste de escala: live view de N câmeras (alvo alinhar com task-052) sem estourar o tier web.
- [ ] Guard de disco/reserved-space (casa com ADR-0028 / edge) no serviço de transcode.

## Aceite

- Live view funciona com a **API em 2+ réplicas** (prova de que o 404 cross-réplica não volta).
- Transcode isolado do tier HTTP; medição de carga sob N câmeras.
- Coerência com o modelo de borda (RVB: nuvem não transcoda).

## Referências

- task-059 (fix de dev + guard-rails), ADR-0030 (a criar), ADR-0020 (MikroTik/WireGuard),
  ADR-0028 (evidência cloud-first + reserved-space), task-052 (escala), `docs/product/VMS_MONITORING_UX.md`
