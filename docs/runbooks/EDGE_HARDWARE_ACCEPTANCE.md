# Aceitação de Hardware — Edge (Palit Pandora AI · Jetson Orin NX Super 16GB)

> Checklist a executar no bring-up de cada device, ANTES do go-live. Referenciado pelas tasks
> 032 (DeepStream/engines), 033 (edge stack) e 037 (provisionamento). Um device por cliente
> (RVB, Roccabela).

## 1. Software / Super mode
- [ ] **JetPack 6.2** flasheado (vem 6.1.1 de fábrica). Os 157 TOPS INT8 só existem no 6.2.
- [ ] Power mode **`MAXN_SUPER`** ativado e persistente após reboot (`nvpmodel` / `jetson_clocks`).
- [ ] Versão de JetPack/TensorRT registrada (vai no manifest dos engines — task-032).

## 2. Térmica
- [ ] Fan ativo (V1) funcionando. Sob carga **sustentada** 40W, **sem throttle** (monitorar `tegrastats`).
- [ ] Ponto de instalação dentro de 0–60°C; não é local quente/sem ventilação na fábrica.

## 3. Rede
- [ ] **Porta Ethernet GbE RJ45** presente e ligada ao switch/MikroTik — caminho das 28 câmeras (RTSP).
- [ ] Câmera nunca exposta à internet; acesso só via overlay (WireGuard/MikroTik, task-033).

## 4. Storage
- [ ] SSD de fábrica (**128GB**) reservado pro OS + engines.
- [ ] **NVMe adicional** (512GB–1TB) no slot M.2 Gen4x4 montado como buffer de evidência/cache (task-051).
- [ ] Evidência **não** grava no disco do OS; ring buffer limitado por tamanho/idade (task-051).

## 5. Benchmark de aceitação (gate de go-live)
Rodar o harness de RTSP sintético (task-027) simulando o nº real de câmeras a 5fps substream H.265,
no 6.2/MAXN_SUPER, e medir:
- [ ] **NVDEC**: decode de todos os streams sem frame drop.
- [ ] **GPU**: utilização com margem (não saturada 100% sustentado) com os modelos do site carregados.
- [ ] **VRAM (16GB unificada)**: cabe o(s) engine(s) do site — se rodar EPI+Qualidade+Counting juntos,
      medir os 3 engines carregados simultaneamente.
- [ ] **Latência por câmera** dentro do alvo; **evento no cloud < 5s**.
- [ ] **Disco estável** sob detecção contínua (buffer não cresce além do teto).
- [ ] Térmica estável (sem throttle) ao fim de uma janela longa.

## Por cliente
RVB (frota **mista Intelbras VIP + Hikvision**) e Roccabela (confirmar marca/qtd) têm devices
separados; rodar este checklist em cada um. Frota mista por site é o caso normal — o onboarding
por câmera (task-046) trata marca a marca. Ver `docs/runbooks/NETWORK_CFTV_ACCESS.md` para a
integração de rede/câmeras.
