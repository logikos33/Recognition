# D-075 · Amplificador: TTL do Redis (20s) empatava com o ciclo do rodízio (19s)

**Seção:** Rodada 08/08 — causa medida do congelamento cíclico + edge sai de caixa preta (D-74..D-77) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**08/08 · Claude**

- `services/api/app/api/v1/edge/routes.py:87`: segmento subia e expirava da nuvem na iminência da visita
  seguinte do uploader ([[D-74]]); a playlist anunciava segmentos mortos → 425 permanentes em índices
  fixos (`stream242.ts`, `stream188.ts`) + congela-e-volta a cada ~15s no navegador (o sintoma relatado).
- Correção: `_HLS_SEGMENT_TTL` 20→30s (> janela de 20s anunciada pelo edge). Atenção: `SEGMENTS_REDIS_URL
  == REDIS_URL` no DEV (Redis compartilhado) — regime estimado ~140MB de segmentos; monitorar.
