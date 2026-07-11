# ADR-0034 — Acesso a gravação NVR/DVR: timeline + seleção de gravador/câmera/horário

**Status:** Aceita (2026-07-07) · **Estende:** ADR-0031 (Training Studio — fonte de dados NVR/DVR),
ADR-0026 (acesso CFTV) · **Relaciona:** gateway/edge, task de câmeras.

## Contexto (ponto E7)

A ADR-0031 definiu o NVR/DVR como fonte de dados de treino, mas de forma rasa. Pra ser útil, o usuário
precisa: **selecionar o gravador**, **a câmera** e **o horário**, ver uma **timeline** do que está
gravado, e extrair frames dali. Isso precisa ser **funcional no backend**, não só visual.

## Decisão

- **Cadastrar gravadores (NVR/DVR)** como um recurso (credenciais + IP), separado das câmeras — um
  gravador tem N câmeras/canais.
- **Busca de gravação (replay):** dado gravador + câmera + intervalo de data/hora → o backend consulta
  as gravações disponíveis e devolve a **timeline** (segmentos existentes vs buracos, respeitando a
  retenção do aparelho). Caminhos de acesso, por robustez: **ONVIF Profile G** → **SDK do fabricante**
  (Hikvision ISAPI / Dahua-Intelbras) → **RTSP com starttime/endtime**.
- **Extração:** a partir da timeline, extrair frames (1 a cada N seg, ou em movimento) → fila de
  anotação do Training Studio. Processar no **edge** (Jetson) quando houver, pra não subir vídeo inteiro.
- **Backend funcional (roadmap):** endpoints `POST /recorders`, `GET /recorders/{id}/recordings?camera=
  &from=&to=` (timeline), `POST /recorders/{id}/extract-frames`. Realidade: acesso a replay é
  dependente de fabricante (NVR bom = tranquilo; DVR no-name = pode não expor).

## Front (avançar agora)
- Cadastro de gravador; seletor **gravador → câmera → intervalo data/hora**; **timeline** das gravações
  (o que existe/buracos) com preview; botão "Extrair frames pro treino". Marcar "em breve" onde o
  backend ainda não existe — mas desenhar o fluxo completo.

## Consequências
- Acelera o bootstrap de modelo (minerar semanas de gravação). Complexidade de integração por fabricante
  e banda (extrair no edge). Segurança/privacidade do vídeo gravado (política de dados).
