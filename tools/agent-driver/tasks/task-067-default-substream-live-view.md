# Task 067 — Default substream (subtype=1) para o Live View + fallback

**Status**: PENDING (recurso/latência; parte da nova leva)
**Risk**: P1-ALTO (toca onboarding + pull de vídeo; cuidado pra não degradar detecção)
**Branch**: fix/task-067-default-substream-live-view

## Contexto (medido em teste real — 2026-07-06/07)

`build_stream_url_for_lazy_start` usa `camera.get("subtype", 0)` e a migration tem **DEFAULT 0**. Logo,
toda câmera nova puxa o **stream PRINCIPAL (1080p)** no live view. Consequências medidas nos logs:
segmentos `.ts` de **~2s / ~550KB** (GOP do principal = 2s) → **latência alta** + mais banda/memória.
O substream já foi setado com **I-frame = 1s** e daria segmentos de ~1s → latência ~metade.

## Objetivo

Fazer o **live view** usar o **substream (subtype=1)** por padrão, sem depender de setar na mão em cada
câmera — com fallback seguro.

## Nuance CRÍTICA (não degradar detecção)

- **Live VIEW** (visualização no browser) → substream (leve, baixa latência). ✅ é o alvo desta task.
- **Inferência/detecção de EPI** pode precisar do **stream principal** (resolução maior — capacete/óculos
  pequenos à distância). NÃO forçar o substream no caminho de inferência às cegas. Manter o subtype do
  live view **separado** do subtype usado pela detecção/gravação (ou configurável por câmera).

## Fix

- **Onboarding**: câmera nova nasce com o live view em **subtype=1** (default), não 0.
- **Lazy-start**: preferir o substream quando existir; **fallback pro principal** se a câmera não tiver
  substream (tentar subtype=1 → se falhar/None, subtype=0), logando via GR-1.
- **Migration aditiva** pros registros existentes (setar o subtype de live view = 1 onde apropriado;
  forward-only, IF NOT EXISTS, backfill por tenant). Não quebrar quem só tem principal.
- Manter o subtype de **inferência** intocado (ou expor os dois campos).

## Aceite

- Câmera nova onboarded → live view usa substream (segmentos ~1s, latência menor; medir).
- Câmeras existentes migradas; câmera sem substream cai no principal sem erro (fallback testado).
- Caminho de detecção NÃO é degradado (subtype de inferência preservado/independente).
- Latência do live view medida com substream (alvo 2-4s). Suíte verde. PR develop. Gate humano staging.

## Referências

- task-059/061 (live view, latência), task-046 (onboarding wizard), Intelbras substream I-frame=1s
  (config de câmera), `docs/product/VMS_MONITORING_UX.md`
