# task-046 — Wizard de onboarding de câmera (multi-marca + caminho NAT/P2P)

**risk:security** (ingestão de URL de câmera → superfície SSRF/FFmpeg + relay de rede)
**modo:** AUTO (pausa na review de segurança — esperado)

## Objetivo
Reduzir a fricção de instalação de câmera para o nível da Camerite (que vence comercialmente
por isso). Um wizard guiado no frontend que: detecta/sugere a URL de substream por marca,
valida a conexão antes de salvar, e oferece um caminho para câmera **sem IP público / atrás de
NAT** (o "P2P" deles), sem exigir que o instalador configure port-forward.

## Por que (Camerite)
Camerite ingere câmeras de "dezenas de fabricantes" via RTSP/RTMP/**P2P** e trata onboarding
fácil como o principal argumento de venda. Nas 28 câmeras Intelbras da RVB, o custo de
instalação (IP fixo, port-forward, achar a URL RTSP certa) é o nosso gargalo real.

## Escopo
### Backend (`services/api`)
- **Verificar primeiro** o schema atual de `{tenant_schema}.cameras` (colunas
  `detection_stream_url`, `video_codec`, `max_auth_failures` da migration 060) — NÃO inferir.
- Endpoint `POST /api/cameras/probe` (role-gated: admin/operator): recebe host/credenciais,
  passa por `RTSPUrlValidator` (obrigatório, anti-SSRF), tenta abrir o stream com timeout curto,
  retorna `{ok, codec, resolution, fps, substream_url_sugerida}`. NUNCA logar credencial.
- Catálogo de "perfis de fabricante" (Intelbras, Hikvision, Dahua, etc.) em config/JSON: template
  de path RTSP de main/substream por marca → preenche a sugestão. Começar com Intelbras (RVB).
- Caminho NAT: documentar e implementar via o relay/gateway de site que já existe no roadmap
  (`site_gateways`, migration 057) — a câmera publica para o gateway local; o gateway empurra
  pro edge/cloud. NÃO abrir porta na internet. Se o gateway não existir para o tenant, o wizard
  cai no fluxo RTSP direto.

### Frontend
- Componente `CameraOnboardingWizard` (passos: marca → host/credenciais → probe/preview →
  confirma). Reusar o wrapper `api.ts` (não `fetch` raw).
- Mostrar preview do frame + codec/fps detectados antes de salvar.

## Fora de escopo
- Descoberta automática ONVIF na LAN (fase 2).
- Qualquer alteração no pipeline de inferência.

## Critérios de aceite
- `RTSPUrlValidator` aplicado em 100% das URLs antes de qualquer chamada a FFmpeg/probe.
- Probe com timeout e sem vazar credencial em log.
- Wizard cria câmera Intelbras de ponta a ponta em staging.
- Testes: validator rejeita URL interna/SSRF; probe retorna erro amigável em falha.

## Migration
Provável **nenhuma** (colunas já existem na 060). Se faltar coluna, criar migration aditiva
`ADD COLUMN IF NOT EXISTS` no padrão (numeração sequencial, backfill por tenant).
