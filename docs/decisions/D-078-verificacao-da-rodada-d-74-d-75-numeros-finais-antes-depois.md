# D-078 · Verificação da rodada D-74/D-75: números finais (antes → depois)

**Seção:** Rodada 08/08 — causa medida do congelamento cíclico + edge sai de caixa preta (D-74..D-77) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**09/08 · Claude**

- Deploy: PRs #325 (TTL 30s), #326 (logs), #327 (redação), #328 (push paralelo), #329 (fixup unit),
  #330 (playlist consistente) mergeados na develop; box RVB via OTA em `b75b37dc`, restart na janela
  autorizada (sábado ~22h30+).
- **Ciclo por câmera: ~19s → 0,8s** (mediana; p95 3,2s; 11.992 pushes, 8 câmeras, janela de 20 min).
- **Upload no NIC: 14 → 37,3 Mbps** (mediana; = o que o gravador entrega — zero perda por projeto).
- **Pushes aceitos: 11.996×201, 4×503** (0,03% falha, reabsorvida no tick seguinte).
- **425 no navegador: 2286 (17% das requests, contínuo) → 32, TODOS nos ~8s da junção fria** — zero em
  regime nos 20 min. A correção decisiva foi o #330: a decisão do gate era tomada na LISTAGEM mas os
  bytes da playlist eram lidos no PUSH — o ffmpeg atualizava o `.m3u8` no meio do job e a nuvem anunciava
  segmento que só subia ~1,7s depois (mediana medida da latência 425→200). Snapshot na listagem +
  truncamento do rabo ao prefixo já enviado = "anunciou ⇒ está no Redis" por construção.
- **Soaks (Playwright, 20 min cada, 8 câmeras, frontend DEV)**: zero navegação p/ /login, zero 401,
  cada player tocou ≥98,9% do tempo. Resíduo honesto: 2-3 eventos de 4-8s SINCRONIZADOS entre todos os
  players por soak, coincidindo com janelas de silêncio TOTAL de HTTP no navegador — e o log do box
  mostra push contínuo (10-15/s) nos mesmos segundos de parede. Veredito: caminho cliente↔Railway
  (Wi-Fi/conexão local do espectador), fora do sistema. Mitigação possível (tema futuro, custo =
  latência): aprofundar buffer do player (`liveSyncDurationCount`) + `hls_list_size` maior.
- Harness: Chromium bundled do Playwright NÃO decodifica o HEVC das câmeras (ver D-79) — soak roda
  headed com `channel: 'chrome'`. Primeira rodada headless "passou falso o portão inverso" (tráfego
  pleno, playback zero).
