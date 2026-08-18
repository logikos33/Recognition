# D-095 · Cota do coletor PROVADA: trava a CAPTURA (não só a contagem) — banco, R2, log e rede imóveis

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · Claude (medição passiva, DEV/RVB) · ✅ provado**

Medo específico do Vitor: *"câmera que bateu 1.000 não pode continuar mandando para o R2 —
parar de contar e continuar subindo seria pior que não ter cota"*. **Descartado com prova
empírica de ~9h** (janela natural, mais forte que os 30 min planejados):

| Evidência | T0 (11/08 23:10) | T1 (12/08 08:30) |
|---|---|---|
| Banco por câmera (8 originais, source=nvr) | 8.667 (988–1.679 cada) | **8.667 — idêntico, câmera a câmera** |
| Contadores no state file (8 originais) | 988–1.679 | **idênticos** |
| R2 `training-images/{tenant}/nvr/` | 9.000 objetos | 9.724 — crescimento **casado 1:1 com frames novos do banco, zero das 8** |
| Log (delta 4.520 linhas) | — | **0 linhas `collector_*` para os 8 UUIDs** vs 150–330/câmera nova (controle positivo: mesmo processo capturando ao lado) |
| Sampler 35 min (2s, fase 100% congelada) | — | **0 filhos ffmpeg, 0 conexões** do coletor (captura spawna ffmpeg — sem processo, sem RTSP) |

O pulo é **antes de abrir RTSP** (`collector_loop.py:275-276`); upload é síncrono, sem
fila/retry (`frame_uploader.py:31-67`) — não existe caminho de subir sem contar. State
(9.333) = linhas do banco (9.333), exato.

**As 3 perguntas da campanha (D-91):**
1. **Subir alvo reativa?** Sim, mecanicamente: `contador < alvo` reavaliado por tick; alvo é
   lido do env **uma vez no boot** → **cada troca de janela (50→100→150) exige restart da
   unit**. Corte exato no teto — hoje de manhã **10 câmeras novas pararam EXATAMENTE em 50**
   (`collector_target_reached` é a última linha de cada uma; burst re-checa por frame,
   `collector_loop.py:232`). As 8 antigas (988–1.679) não reativam com alvo ≤150 — **é o
   desenhado em D-91**.
2. **Novas começam do zero?** Sim (código: `collector_state.py:35-69`; empírico: restart de
   00:22 com 28 câmeras logou `frames_ja_contados=8667` = só as antigas; as 20 novas partiram
   de 0). Canal 9 segue draft → fora do channel_map (filtro no config_poller:209-214).
3. **Frame excluído conta na cota?** **SIM — e fica decidido que é o comportamento desejado
   por ora**: o contador é local, incrementa pós-upload e nunca decrementa nem consulta o
   banco; a cota mede **esforço de captura** (RTSP no gravador, banda, R2), não dataset
   curado. Empírico: 2a683620 tem 100 excluídas e o contador segue 988. Mudar (decrementar
   por comando, contar do banco) é decisão de produto futura — nada implementado.

**Anomalia registrada (não investigada):** R2 tem **391 objetos órfãos** sob `nvr/` sem linha
no banco (333 pré-existentes em T0, +57 entre 23:11–23:17 com o coletor comprovadamente
congelado — candidato: task cloud `nvr_extraction`, mesmo prefixo). Custo só de storage;
não afeta cota nem contagem. Fica para rodada própria.
