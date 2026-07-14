# Análise do Código — Onde e Como Implementar o Carga & Descarga (Fase 1)

**Varredura de 11/06/2026** · Repo: EPI - CATH V2 · Cruzada com o backlog `tasks-carga-descarga-fase1.md`

---

## 1. O que a varredura encontrou (estado real vs. suposições)

| Suposição do planejamento | Realidade no código | Impacto |
|---|---|---|
| "Voto multi-amostra (038) implementado" | ❌ **Só especificado** — `counting_line.py` não tem `confirm_samples`/debounce (verificado por grep) | CD-01 cresce: implementa o 038 junto |
| "Pipeline DeepStream" | ❌ `deepstream/{epi,fueling,quality,shared}` estão **vazias** (.gitkeep) | Ver seção 3 — maior risco da entrega |
| "Sessões precisam ser criadas do zero" | ✅ **Melhor que o esperado**: `counting_sessions` + `counting_events` já existem (migration 049) com API e repository | CD-03 vira extensão, não criação |
| Tracker | DeepSORT em Python (`services/inference/inference/inference_engine.py`, `max_age=30, n_init=3`), 1 instância por câmera | CD-02 (bench ByteTrack) confirmado como troca isolada (~1 dia) |
| Contagem | `counting_line.py` usa **centroide** + produto vetorial, linha única, **sem histerese**, tracking best-effort por posição | CD-01 confirmado como necessário |
| Mock do fueling | `fueling_mock_service.py` — dados determinísticos por dia/slot de 5min, 6 baias fixas | Ponto exato de corte do CD-03 |
| 043 (relatórios) | ❌ Só especificado | CD-07 (validação/aceite) não tem base pronta |
| 045 (modelo por câmera) | ⚠️ Colunas existem (`model_counting_id` etc.), API não encontrada | Pequeno trabalho extra no CD-04 |
| Multi-tenant | ✅ Schema-per-tenant com whitelist cache (`core/tenant.py`), tenant via claims JWT | Conforme planejado |
| Auth de devices | ✅ **Já existe enrollment com token one-time (SHA-256) + JWT RS256** (`core/device_auth.py`), heartbeat e config polling | O "claim code" está 70% pronto! |
| Rate limiting | ⚠️ flask-limiter + Redis parcial; `RATE_LIMITING_PLAN.md` estima ~70min p/ fechar; **per-tenant por plano não existe** | Quick win |
| Seats/sessões concorrentes | ❌ Não existem | Backlog plataforma |
| Evidência | ✅ R2 com StorageStrategy (Mock/Local fallback) | CD-06 tem base |
| Alertas | ⚠️ Geração+ack existem; **sem webhook/email/notificação** | Fase 2 |

## 2. Mapa de implementação por task (arquivos exatos)

### CD-01 — Contagem com histerese (+ implementar o 038 de verdade)
- **Onde:** `services/api/app/domain/services/operations/canonical/counting_line.py`
- **O quê:** trocar centroide por **ponto inferior central** da bbox; adicionar `confirm_samples` (N frames de track antes de elegível) + `direction_debounce_frames` + zona de confirmação (linha+zona); estado por track_id com lista de já-contados.
- **Atenção:** a spec do 038 já define os campos de config — implementar conforme spec e cobrir com os testes previstos.
- Esforço estimado pela varredura: 2-3 dias.

### CD-02 — Bench de tracker
- **Onde:** `services/inference/inference/inference_engine.py` (DeepSORT isolado aqui).
- ByteTrack é troca de arquivo único (API diferente, sem impacto comportamental) — ~1 dia + bench com vídeo real.

### CD-03 — Sessões: ESTENDER `counting_sessions`, não criar `loading_sessions`
- **Onde:** migration 049 (`counting_sessions`/`counting_events`) + repository/API de counting já existentes.
- **O quê:** migration nova adicionando à `counting_sessions`: `bay_id`, `truck_plate`, `direction (load|unload)`, `expected_count NULL`, `divergence NULL`, `video_clip_url`; ingest liga evento de cruzamento → sessão aberta da baia.
- **Cortar o mock:** `fueling_mock_service.py` atrás de feature flag por tenant (superadmin demo continua, cliente real vê dado real).
- Decisão de design: **um produto = uma tabela de sessões** — evita dois conceitos de sessão divergindo.

### CD-04 — Dataset/active learning
- **Onde:** training-service + colunas 045 (`model_counting_id`).
- **O quê extra descoberto:** a API de atribuição modelo↔câmera do 045 não existe — criar junto (pequena).

### CD-05 — Abertura automática de sessão
- Classes truck/forklift/pallet vêm da migration 009 (041 renomeia `fuel_nozzle`→`forklift`). Detecção de `truck` parado na zona da baia abre sessão; `plate` via OCR vincula. Operation-type novo no registry (`operations/canonical/`), config JSONB na tabela `operations` com hot-reload Redis já suportado pelo motor (023). ✅ Arquitetura pronta pra receber.

### CD-06 — Evidência
- R2 + StorageStrategy prontos. Trabalho é gerar o **clipe da sessão** (hoje há frames/screenshots) e a URL presignada no dashboard.

### CD-07 — Validação/aceite
- Sem base (043 não implementado). Construir como tela simples sobre `counting_sessions` (sistema vs. manual por sessão). Não bloquear no 043 completo — versão mínima dedicada ao aceite.

### CD-08 — Dashboard real
- Cortar `fueling_mock_service.py`; os endpoints de counting reais existem — ligar o front neles. As 6 baias fixas do mock viram registro configurável (criar CRUD de baias se não existir).

## 3. ⚠️ Risco arquitetural nº 1 descoberto: o pipeline de frames

**Hoje:** camera-gateway → Redis pub/sub (`frame:{camera_id}`, **JPEG base64**) → inference Python (YOLO + DeepSORT) → `det:{camera_id}`.

**Problema para a Rocabella:** 12 câmeras × 10-15 fps = 120-180 frames/s de decode JPEG + inference em Python num Orin NX. O dimensionamento que fizemos (16 streams no NX) assumia DeepStream INT8 com decode em hardware (NVDEC). O caminho Redis/JPEG/Python:
- gasta CPU em decode (NVDEC fica ocioso)
- serializa base64 (overhead ~33% de banda/memória)
- DeepSORT em Python é o gargalo conhecido em multi-câmera

**Opções (decidir cedo, antes da instalação):**
1. **Validar throughput real em bancada** com o pipeline atual no NX (12 streams, 10-15fps, modelo de rolo). Se passar com folga → mantém, zero retrabalho. *(fazer já — 1 dia de bench)*
2. **Otimizações no pipeline atual:** decode via PyNvVideoCodec/GStreamer no gateway, frames como bytes (sem base64), batch inference, FP16/INT8 via TensorRT export — mantém arquitetura, ganha 2-4×.
3. **Pipeline DeepStream nativo** nas pastas vazias `deepstream/fueling/` — máxima performance (era o plano, pelo visto), mas é o maior item de esforço novo da Fase 1 se for necessário.

**Recomendação:** bench (opção 1) na semana 1; se reprovar, opção 2 antes de considerar a 3. Adicionar como **CD-00** no backlog, prioridade 🔴 P0.

## 4. Quick wins de plataforma encontrados (fora do caminho crítico)

1. **Rate limiting per-tenant:** o plano em `services/api/RATE_LIMITING_PLAN.md` está pronto e estima ~70 min de execução — fechar e adicionar tier por plano na sequência.
2. **Claim code:** o `device_auth.py` já tem enrollment token one-time + RS256. O "claim code do plug-and-play" é embrulhar isso numa UX (gerar código curto na web → instalador troca por enrollment token). Esforço pequeno, alinhado ao dogfooding da instalação Rocabella.
3. **Seats por tenant:** não existe — trigger simples em memberships/users por tenant + checagem no convite. Encaixar no mesmo PR do controle de sessões concorrentes.
4. **045 (modelo por câmera):** colunas órfãs sem API — fechar o gap junto do CD-04.

## 5. Resumo executivo

- A base é **melhor do que o documentado** em sessões (049 já existe), auth de devices (enrollment pronto) e motor de operations (hot-reload, registry).
- É **pior do que o documentado** em: 038 (não implementado), 043 (não implementado), DeepStream (inexistente).
- O **maior risco da entrega Rocabella não está no backlog atual**: é a capacidade do pipeline Redis/JPEG/Python no Jetson — bench obrigatório na semana 1 (novo CD-00).
- Ordem de ataque continua a do backlog, com CD-00 na frente e CD-03 ficando mais barato (estender 049 em vez de criar do zero).
