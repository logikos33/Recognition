# ADR-0031 — Training Studio: ciclo de vida de modelo (MLOps na UI)

**Status:** Aceita (aprovada 2026-07-07) · **Data:** 2026-07-07
**Estende:** ADR-0027 (training-environment-ui) · **Relaciona:** `docs/architecture/TRAINING_PIPELINE_DESIGN.md`
(flywheel 11 estágios), ADR-0024 (scenario-editor/model-config), ADR-0025 (roles/permissões)

## Contexto

O treinamento atual (ver `screens/epi-training.md`) é um fluxo **linear e raso**: upload manual de
imagens → anotar (AnnotationInterface) → configurar um job (modelo base/epochs) → ativar um modelo da
lista. Lacunas:

- As imagens vêm **só de upload manual** — o que o sistema **captura** (frames de alertas/detecções das
  câmeras) NÃO vira dado de treino. Perde o *data flywheel*.
- Não há **dataset versionado** nem **linhagem** (qual conjunto rotulado → qual treino → qual modelo).
- Não há **avaliação/comparação** (modelo novo × ativo, por classe) antes de promover.
- Editar as **classes** do cliente (a taxonomia que define o modelo dele) está com navegação quebrada.
- Não há **active learning** (sistema sugerir o que rotular pra melhorar).

Ou seja: hoje o usuário "escolhe um modelo pronto", não **cria/edita o próprio modelo a partir dos
próprios dados** — que é o valor central do produto (cada cliente treina o que importa pra ele).

## Decisão

Redesenhar o treinamento como um **Training Studio** — um **ciclo de vida de modelo (MLOps)** completo
na UI. Aplicar a VISÃO no design AGORA (Claude Designer / Onda 3), mesmo sem endpoints de backend ainda
(backend evolui depois; as telas que dependem de backend inexistente ficam como visão/roadmap, mas o
fluxo visual existe).

### Decisões de escopo (aprovadas)
- **Fonte de dados (4 fontes):** (a) captura automática (frames/alertas das câmeras → dado de treino);
  (b) **gravações do NVR/DVR** do cliente — acessar tudo que já está gravado, não só os alertas (ver
  subseção dedicada); (c) upload manual; (d) extração de frames de vídeo. **+ active learning** (sistema
  sugere quais imagens rotular por baixa confiança/incerteza).
- **Anotação:** **na plataforma** (AnnotationInterface) **+ pré-anotação assistida** (IA propõe as
  caixas, humano revisa — HITL). Importar dataset externo não é o caminho primário.
- **Ciclo:** **completo (MLOps)** — dataset versionado → treinar → **avaliar/comparar (campeão ×
  desafiante)** → promover, com linhagem.
- **Quem treina:** **híbrido** — Logikos treina o inicial (interno/super admin); o **cliente** pode
  ajustar/retreinar (self-service, gated por permissão `training:write/approve`).

### Estágios do Training Studio (design/UX)

1. **DADOS** — galeria de imagens de treino vinda de 4 fontes: (a) **captura automática** dos
   alertas/detecções das câmeras (botão "Adicionar ao treino" no alerta; ingestão contínua),
   (b) **gravações do NVR/DVR** (minerar o que já está gravado — subseção abaixo), (c) upload manual,
   (d) extração de frames de vídeo. Fila de **active learning**: "N imagens sugeridas pra rotular"
   (as de menor confiança/maior incerteza), priorizadas.

### Fonte de dados: NVR/DVR (gravações) — como funciona

**Por quê:** o NVR/DVR do cliente já guarda dias/semanas de vídeo de todas as câmeras. Em vez de esperar
os alertas ao vivo acumularem, dá pra **minerar esse histórico** e montar o dataset inicial em horas, não
semanas. É a fonte que mais acelera o bootstrap de um modelo novo.

**Como acessar (técnico — para o backend futuro):**
- Conectar ao NVR/DVR como se conecta a uma câmera (credenciais + IP), mas usando o canal de **replay/
  playback** (não o stream ao vivo). Caminhos possíveis, por ordem de robustez:
  - **ONVIF Profile G** (busca e replay de gravação) — padrão aberto; o ideal quando o aparelho suporta.
  - **SDK/API do fabricante** — Hikvision ISAPI (playback por câmera+intervalo), Dahua/Intelbras (mesma
    base). Mais confiável nos aparelhos deles, porém proprietário.
  - **RTSP com parâmetro de tempo** — alguns NVRs expõem `rtsp://.../playback?starttime=...&endtime=...`.
    Varia muito por fabricante.
- **Realidade honesta:** acesso a gravação é **dependente de fabricante** e às vezes chato (a gente já
  apanhou de um DVR genérico). NVR bom (Hikvision/Intelbras) → tranquilo via SDK/ONVIF; DVR no-name →
  pode não expor replay e cair só no que dá.
- **Onde processa:** se houver **edge (Jetson) no site**, ele acessa o NVR **localmente** e extrai só os
  frames selecionados (não sobe vídeo inteiro pra nuvem — economia de banda). Sem edge, o pull é pela
  rede do cliente (túnel/gateway).

**UX no Training Studio (o que desenhar agora):**
- Fonte "Gravações do NVR/DVR": escolher **câmera + intervalo de data/hora** → o sistema busca as
  gravações disponíveis (respeitando a **retenção** do aparelho — só existe o que ainda não foi
  sobrescrito) → **extrai frames** (por intervalo, ex. 1 a cada N seg, ou em momentos de movimento) →
  joga na fila de anotação.
- Mostrar linha do tempo das gravações por câmera (o que existe vs buracos), e um preview antes de
  extrair. Marcar como **"em breve"** onde o backend ainda não existe.

**Considerações:** banda/armazenamento (extrair frames, não baixar tudo); privacidade (vídeo tem
pessoas — tratar conforme política de dados/retenção); performance (fazer a extração no edge quando
possível). Casa com ADR-0026 (CFTV access) e o gateway/edge.
2. **CLASSES** — criar/editar as **classes do cliente** (nome humano + cor), data-driven. É o que define
   o modelo. Consertar o acesso (hoje quebrado). Cada classe mostra quantas amostras rotuladas tem.
3. **ANOTAÇÃO** — AnnotationInterface (desenhar/editar caixas por classe) com **pré-anotação** (auto-
   sugestão de caixas que o humano confirma/corrige). Progresso de rotulagem por classe (balanceamento).
4. **DATASET (versão)** — agrupar imagens rotuladas num **dataset versionado** (snapshot imutável):
   split treino/val/teste, augmentations, contagem por classe. Cada versão tem ID e linhagem.
5. **TREINAR** — configurar o treino **a partir de uma versão de dataset** (modelo base, epochs, batch,
   LR, presets). **Treino ao vivo** (loss/mAP em tempo real, log, ETA) — já existe, integrar. GPU via
   Integrações.
6. **AVALIAR / COMPARAR** — pós-treino: métricas **por classe** (precision/recall/mAP), matriz de
   confusão, e **comparação campeão × desafiante** (modelo novo × ativo) — decidir promover com dado, não
   no escuro.
7. **PROMOVER / IMPLANTAR** — ativar o modelo, **atribuir a câmeras/módulo**, rollback. Registro de
   modelos com **linhagem completa**: dataset (versão) → treino (job) → modelo (versão) → onde está em uso.

### Acesso por papel
- **Super admin (Logikos):** studio completo, treina/promove pra qualquer tenant.
- **Cliente com `training:write`:** rotular, versionar dataset, treinar, comparar.
- **Cliente com `training:approve`:** promover/ativar modelo.
- Operador sem permissão de treino: não vê o studio (nav adapta — ADR-0025).

## Consequências

- **Positivo:** transforma "escolher modelo" em "criar/editar o próprio modelo com os próprios dados";
  vende o flywheel (o modelo melhora com o uso); linhagem e comparação dão confiança pra promover.
- **Custo/risco:** vários estágios dependem de **backend que ainda não existe** (captura automática,
  active learning, dataset versioning, champion/challenger). No design são a VISÃO; no backend viram
  roadmap (alinhar com TRAINING_PIPELINE_DESIGN.md). Marcar claramente o que é "em breve" vs funcional.
- **Migração:** o design (Onda 3) já contempla o studio; a implementação backend segue por etapas.

## Adendo — Pré-anotação: histórico e decisão de backend plugável (2026-07-12)

A pré-anotação assistida (item 3 acima) já teve uma implementação real: um proxy
`POST /api/frames/<id>/pre-annotate` chamando um microserviço DINO+SAM
(`pre-annotation-service/`), removido em `e5582c9` ("DINO+SAM nunca usado em
prod") por custo computacional (GPU por chamada) desproporcional à qualidade
das sugestões observada em uso real.

Ao retomar o tema (WS-B4 da pipeline de treinamento), a decisão é: **backend
plugável, feature flag OFF por padrão** (`tenants.feature_flags.pre_annotation_enabled`,
mesmo padrão JSONB por-tenant do módulo fueling, ver ADR-0035). A flag nasce
desligada exatamente por causa desse histórico — reativar DINO+SAM como
default sem repensar o modelo repetiria o mesmo custo sem resolver o problema
de qualidade que motivou a remoção.

O que muda desta vez: a interface (`PreAnnotationBackend`) é desacoplada do
modelo escolhido. DINO+SAM continua disponível como uma implementação
concreta (não como o único caminho), e o **Jetson Platform Services** (VLM/
zero-shot nativo do hardware edge da Logikos) é candidato a avaliar como
alternativa antes de qualquer tenant ligar a flag de verdade — evita pagar
custo de GPU cloud quando o processamento pode acontecer no próprio edge,
mais perto do dado e sem esse trade-off. A escolha de qual backend vira o
default fica para quando a flag for ativada pela primeira vez, com dado real
de custo×qualidade em mãos — não nesta PR.

## Referências

- `docs/architecture/TRAINING_PIPELINE_DESIGN.md` (flywheel 11 estágios), `screens/epi-training.md`,
  `screens/training-classes.md`, ADR-0027 (training env UI), ADR-0024 (model config), ADR-0025 (papéis).
