# D-085 · iNVD 3032 inventariado: 29 canais ocupados, 21 câmeras novas, substream 100% H264 — inventário, NÃO ativação

**Seção:** Rodada 11/08 — inventário dos 32 canais do gravador (D-85) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**11/08 · Claude (sondagem do Orin) · ✅ inventário concluído · 🛑 ativação = decisão do Vitor, por aditivo com a RVB**

- **Como:** ONVIF `GetProfiles` via media2, do Orin (nunca da nuvem, ADR-0020), ~20h20 (fora do
  horário de operação). Protocolo anti-lockout cumprido: **1 credencial validada 1×, 34 chamadas
  SOAP sequenciais com pausa de 4 s, zero 401/403, somente leitura** — nada ativado, nada
  cadastrado, nenhum stream/snapshot baixado. Valida a ADR-0052 em hardware real pela 2ª vez.
- **O que tem lá:** **29 de 32 canais ocupados** (30–32 livres). Canais 1–8 = as 8 contratadas
  (§8 do dicionário). **Canais 9–29 = 21 câmeras além do contratado** — batem com as ~21 do
  WS-Discovery de 04/08; agora sabemos que estão plugadas neste gravador. Sem evidência de troca
  ou mudança de posição das 8 (canais 1–8 seguem H265 1080p30, compatível com D-79; pareamento
  canal↔posição física segue pendente para todos os canais).
- **Codec (o achado):** principal = 25× H265 (21× 1080p, 4× **2560×1440** nos canais 26–29) e
  4× **H264** (canais 13/15/16/17). A hipótese "as novas são H264" não se confirmou. Mas
  **o substream é H264 704×480@30 uniforme nos 29 canais** — a grade preta do D-79 é problema
  exclusivo do principal; `subtype=1` toca em qualquer navegador, em qualquer canal. Fortalece a
  troca da grade para substream (decisão segue com o Vitor).
- **Capacidade com 29:** principal ~119–134 Mbps + sub ~22–30 Mbps ≈ 35–41% do link de 400 Mbps
  (cabe); egress da grade 8h/dia ~**US$ 545/mês** (vs ~US$ 150 com 8, linear — bitrate igual em
  todos os canais, 4096k/1024k). **Sobe junto, antes de qualquer ativação:**
  `LIVE_VIEW_MAX_PARALLEL_PUSHES` (default 8 → rodízio volta) e bucket dedicado pro
  `POST /segment` (piso de 900/min/IP estoura com ~10 câmeras; 29 ≈ 2.610 req/min). **Pergunta
  aberta registrada, não medida:** inferência no Orin >8 streams — decide 1 Orin ou 2.
- **O lado bom:** 21 câmeras novas = a **coleta multi-câmera** que falta para a volta 2 (o pool
  de 31/07 é de 1 câmera só, D-68). Indícios de ângulo/área novos: canais 26–29 são 4MP (outra
  geração de hardware) e 13/15/16/17 outro lote (H264). Mapear canal→área com a RVB é o próximo
  passo — ângulo diferente vale mais que câmera a mais no mesmo lugar.
- **Regra que fica:** *"visibilidade técnica não implica autorização de uso"* — ativar **quais**
  e **quando** é decisão comercial (aditivo), com a tabela na mão: *21 câmeras a mais, ~US$ 545/mês
  de egress em grade 8h/dia, cabem no link, exigem 2 ajustes de software + 1 medição no Orin.*
  Relatório completo: `docs/edge/INVENTARIO_INVD_3032_2026-08-11.md`.
