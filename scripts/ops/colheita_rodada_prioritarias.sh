#!/bin/bash
# Colheita das câmeras que o DONO priorizou (pedido de 02/09).
# Duas passadas SEQUENCIAIS — nunca duas sessões de playback ao mesmo tempo
# contra o gravador (anti-lockout, D-160).
cd "$HOME/colheita-full-0902" || exit 1

echo "############ DISCO/LINK ANTES DA RODADA ############"
df -h /; grep enP8p1s0: /proc/net/dev

echo
echo "############ PASSADA A — ch2 Corredor Lateral + ch1 Entrada Expedição ############"
echo "############ 1 dia (a busca do recon dá ~1,5 frame/janela no ch2) ############"
CANAIS=2,1 PRIORIDADE=2 DIAS=2026-09-02 \
  TURNO_INI=07:00 TURNO_FIM=17:00 PULL_MIN=10 TURNO_NOME=operacao \
  ./medir.sh
echo "RC_A=$?"

echo
echo "############ PASSADA B — ch7 Preparação + ch21 Expedição 02 + ch8 Usinagem Madeira 01 ############"
echo "############ 2 dias: são os de menor movimento, precisam de mais janela ############"
CANAIS=7,21,8 PRIORIDADE=7,21 DIAS=2026-09-01,2026-09-02 \
  TURNO_INI=07:00 TURNO_FIM=17:00 PULL_MIN=10 TURNO_NOME=operacao \
  ./medir.sh
echo "RC_B=$?"

echo
echo "############ DISCO/LINK DEPOIS DA RODADA ############"
df -h /; grep enP8p1s0: /proc/net/dev
echo "############ FIM ############"
