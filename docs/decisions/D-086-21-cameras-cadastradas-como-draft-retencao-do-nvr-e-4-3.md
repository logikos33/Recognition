# D-086 · 21 câmeras cadastradas como draft · retenção do NVR é ~4,3 dias (a reextração de 31/07 já era) · coleta ganha eixo próprio de qualidade

**Seção:** Rodada 11/08 (noite) — as 21 entram como draft (D-86) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**11/08 · Vitor (decisão) + Claude (execução) · ✅ cadastro executado no banco · 🛑 ativação = triagem do Vitor, pós-aditivo**

- **Decisão do Vitor:** *"pode incluir todas as câmeras novas que eu vou tirar as que não
  fazem parte do reconhecimento."* Executado no banco de **Desenvolvimento**: **21 câmeras
  (canais 9–29) cadastradas em lote**, todas `is_active=FALSE` — o estado *draft* que já
  existia (mesmo do import admin). Draft fica **fora do channel_map** que o ConfigPoller
  manda pro box ⇒ não transmite, não coleta, não infere (provado por consulta: 8 ativas,
  21 drafts, 0 sem site_id, 0 sem credencial). Credencial Fernet **copiada por
  INSERT..SELECT da câmera do canal 1 dentro do próprio banco** — plaintext nunca tocado;
  `site_id` herdado das 8 (sem ele a câmera é invisível pro edge). Idempotente: 2ª execução
  = 0 inseridas, 21 puladas. Script: `scripts/ops/import_nvr_channels_rvb.py` (PR #353,
  com a migration **113** `position_confirmed`).
- **Bloco 0 antes do cadastro** (PR #352): bucket dedicado `edge-live-ingest` pro
  `POST /segment` — **3.600/min** (32 canais × ~90 req/min + 25% de folga; sem ele o piso
  anônimo de 900/min estourava com ~10 câmeras e o 429 imitaria o congelamento de
  #325–#331) — e `LIVE_VIEW_MAX_PARALLEL_PUSHES` **proporcional ao site** (câmeras+2,
  piso 8): teto fixo envelhece. Prova: 29 câmeras ≈ 2.610/min (27% de folga); 32 ≈ 2.880
  (20%).
- 🔴 **Retenção do iNVD medida: ~4,3 dias** (FindRecordings: canal 1 main, earliest
  2026-08-07T15:41Z). **A encenação de 31/07 em 1080p JÁ FOI SOBRESCRITA** — a
  "oportunidade com prazo" expirou antes da rodada. **Regra que fica: material bom no
  disco do NVR tem ~3 dias úteis de vida — é extrair imediatamente ou perder.** (Vale
  para a próxima encenação: reservar a extração para o MESMO dia.)
- **Qualidade em DOIS eixos por câmera** (pedido do Vitor): OPERAÇÃO já existia
  (fps_target/quality_preset/live_view_subtype); nasce o eixo COLETA —
  `cameras.collection_subtype` (migration **114**), **default 0 = stream principal**:
  coleta é foto, custo ~zero, e 📌 **anotar em alta é melhor mesmo que o treino rode em
  baixa** — coordenada é normalizada; caixa precisa em 1080p continua precisa depois do
  downscale, caixa imprecisa em 480p é imprecisa para sempre. O edge aplica por câmera só
  no `capture_frame` (live view segue global/substream). UI avisa o desalinhamento
  (treino nítido × operação borrada → augmentation: downscale/blur/compressão no treino).
- **Resolução por frame: já estava resolvido desde a migration 094** — o upload grava
  width×height (PIL). Auditoria do acervo: **8.667 frames, 100% com resolução** (1.432
  cheios 704×480 + 7.235 crops de pessoa, tudo source=nvr) — **zero** a recuperar do R2.
- ⚠️ **Achado da auditoria de coleta: a cota re-arma a cada restart do coletor**
  (contador em memória, documentado no próprio collector_loop; visível no acervo: ~3,7k
  frames em 07/08 e de novo em 10/08 = cota 1000/câmera × 8 re-armada). Com 29 câmeras
  vira até **29k frames por restart**. Storage não é o problema (~2,3 GB/ciclo ≈
  US$ 0,03/mês no R2) — **acervo que ninguém anota é**. Persistir o contador (ou virar
  cota diária) é pré-requisito antes de ligar coleta nas 21. Coleta nas novas **NÃO foi
  ligada** (decisão do Vitor, com estes números).
- **Tela de triagem dos 29 canais** (PR próprio): preview **UM por vez** (draft ativa
  temporário e reverte ao fechar — ativar as 29 juntas é ~130 Mbps + 29 decodes HEVC),
  lote ativar/**arquivar** (nunca apagar), renome em linha ("Canal N" → nome de lugar),
  badge **"posição não confirmada"** para TODAS até o walkthrough (nem as 8 originais
  foram conferidas).
