"""
Constante compartilhada de RAJADA (dedup por câmera+classe+janela).

Achado da rodada UX2 (ux2/dedup): o acervo RVB tem 423 alertas mas boa parte
é o MESMO fato redetectado frame a frame — medido no filtro de Violações de
Eventos, 66 linhas de UMA câmera em 2 minutos eram só 2 situações reais (33
"Sem mascara" + 33 "Sem Luvas", 25/08 13:39-13:41). `VerificationService` já
tinha a regra (rodada 3, `_DEDUP_WINDOW_SECONDS`) para ORDENAR a fila; esta
constante é a fonte única para quem mais precisar da MESMA janela — não
duplicar o número em outro lugar, não inventar outra janela.

Usado por:
  - `VerificationService._DEDUP_WINDOW_SECONDS` (ordena a fila por rajada)
  - `AlertRepository.list_with_filters` (conta `total_situacoes`)
"""

#: Alertas da MESMA câmera+classe que se repetem dentro desta janela são uma
#: rajada — o modelo redetecta a mesma pessoa/situação frame a frame, não N
#: eventos distintos. Mudar isto é decisão consciente (documentar o novo
#: número medido), não um default trocado por acaso.
DEDUP_WINDOW_SECONDS = 60
