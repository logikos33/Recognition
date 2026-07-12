# VMS + Monitoramento ao Vivo + Configurabilidade (experiência do operador)

**Data:** 2026-06-24 · Requisitos de produto/UX. A plataforma É TAMBÉM um VMS — a experiência de
monitoramento ao vivo é central pro operador e não pode travar nem confundir. CV = braço direito do
operador (técnico de segurança, especialista de qualidade, etc.), nunca uma barreira.

## 1. Monitoramento ao vivo (VMS) — a tela que não pode morrer
- **Grid/mosaico** de todas as câmeras ao vivo, **filtrável por módulo** (Qualidade, Estacionamento/
  Contagem, EPI). Uma tela de operação onde dá pra acompanhar cada módulo de forma entendível.
- **Overlay de reconhecimento on/off:** ligar/desligar as bounding boxes pra ver o que ESTÁ e o que
  NÃO está sendo reconhecido.
- **Clicar numa câmera → expandir** (single-camera view) com todas as infos + **logs ao vivo do que
  está sendo reconhecido** naquela câmera. Fechar e voltar ao grid sem recarregar.
- Filtros/visões por câmera única ou por módulo.

## 2. Performance sob volume alto (não travar — requisito duro)
Mesmo com muito dado ao vivo, a UI tem que ser fluida. Estratégias obrigatórias:
- O **edge faz o processamento**; ao cloud/UI chegam **eventos/overlays**, não vídeo pesado.
- Vídeo ao vivo via **substream leve** (HLS/WebRTC do edge/gateway), não frames no DOM.
- **Virtualização do grid** (renderizar só o visível), **throttle/debounce** de updates,
  **WebSocket com backpressure**, **paginação/streaming** dos logs. Detecção vira evento, não re-render por frame.
- Meta: grid grande + câmera expandida + logs correndo, sem travar.

## 3. Configurabilidade pela UI (sem script)
- **Qualidade/compressão de imagem por câmera** selecionável na UI.
- **Controle de FPS por câmera** na UI (ex.: baixar Qualidade de 10 → 5 fps).
- **Avisos inteligentes (health-aware):** quanto de FPS há disponível, e o IMPACTO na "vida" do
  edge/worker se aumentar (GPU/decode/VRAM/térmica). O usuário decide informado.
- Config reflete no edge via comando cloud→edge (task-030/edge_commands). Nada de script.

## 4. Saúde do Edge/Worker (integrada à config)
- Painel de saúde do edge (fleet/heartbeats já existem): GPU/decode/VRAM/térmica, quantos fps cabem,
  alertas de saturação. A config de FPS/qualidade é amarrada a essa saúde (não deixa estourar o device).

## 5. Perfis / Permissões CUSTOMIZÁVEIS (UX boa até pro admin)
- A matriz de permissões existe mas não é customizável (ou é ruim de mexer). Refazer: **criar/editar
  perfis (roles)** e escolher **quais funcionalidades** cada um tem, com UX boa pro próprio admin.
  Por tenant. Super-admin vê tudo.

## 6. Isolamento de tenant (inegociável)
- Dois clientes NUNCA veem os dados um do outro (câmeras, modelos, treinos, evidências). Super-admin
  vê tudo. Treinos/modelos isolados por tenant.

## 7. Padrão de CONTÊINER (modal/drawer) — padrão de design da plataforma
- Executar uma funcionalidade num **contêiner** (modal/drawer/painel deslizante) que abre sobre o
  contexto atual **sem atrapalhar o que roda atrás**, e fecha voltando ao lugar (ex.: abrir config de
  uma câmera, editar um perfil, ver logs — e fechar sem sair da tela). Abrir/fechar fluido e bonito.
  A reforma visual deve adotar esse padrão como base.

## 8. Filosofia
Cada módulo mostra o que aquele profissional precisa (qualidade da peça, EPI, contagem) E o informa
do sistema. Intuitivo pro público-alvo leigo em visão computacional. Configurável pra rodar bem sem
travar, mas simples de usar.

## 9. Captura contínua de ideias
Este doc acumula novas ideias de produto/UX conforme surgem — não deixar ideia congelada fora da produção.
