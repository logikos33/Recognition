# Inventário dos 32 canais — Intelbras iNVD 3032 · 2026-08-11

**O que é:** inventário do que está plugado hoje nos 32 canais do gravador da RVB.
**O que NÃO é:** ativação. ⛔ Zero câmera ativada, zero cadastro novo em `ip_cameras`, zero stream
aberto, zero snapshot baixado. O dicionário do contrato (§8) é explícito: **8 câmeras contratadas
(canais 1–8)** e *"a visibilidade técnica desses equipamentos na rede não implica autorização de
uso"* — expansão é por **aditivo**, decisão comercial do Vitor com a RVB.

## Execução e protocolo

| | |
|---|---|
| Executado de | Jetson Orin (`pandora`), VLAN das câmeras — nunca da nuvem (ADR-0020) |
| Data/hora | 2026-08-11, ~20h20 local (fora do horário de operação da fábrica) |
| Método | ONVIF `GetProfiles` via **media2** (lê configuração sem abrir stream) — valida ADR-0052 em hardware real pela 2ª vez |
| Auth | **1 credencial (a do edge-sync-agent), validada 1×** (`GetSystemDateAndTime`) — zero 401/403 |
| Chamadas | **34 SOAP**, sequenciais, pausa de 4 s entre cada — nunca rajada |
| Escrita | Nenhuma — somente `Get*` |
| Credencial | Nunca em argv/log/relatório — helper de redação (`redact.py`, cicatriz do #327) + assert no script |
| Script | `~/nvr-inventory-20260811/nvr_inventory_probe.py` no box (reusa `_ws_security_header`/`_soap_envelope` do código do produto) |

**NVR:** Intelbras iNVD 3032 · firmware `4.001.00IB000.1.T (build 2025-08-14)` · serial `DQN0009707690`
· serviços ONVIF media e media2 disponíveis.

## A tabela dos 32 canais

| Canal | Ocupado? | Modelo | Principal (res·fps·codec) | Sub (res·fps·codec) | Snapshot? | Já cadastrada? |
|---|---|---|---|---|---|---|
| 1 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ✅ RVB Camera 1 |
| 2 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ✅ RVB Camera 2 |
| 3 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ✅ Canal 3 |
| 4 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ✅ Canal 4 |
| 5 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ✅ Canal 5 |
| 6 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ✅ Canal 6 |
| 7 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ✅ Canal 7 |
| 8 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ✅ Canal 8 |
| 9 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 10 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 11 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 12 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 13 | ✅ | n/d¹ | 1920×1080 · 30fps · **H264** | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 14 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 15 | ✅ | n/d¹ | 1920×1080 · 30fps · **H264** | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 16 | ✅ | n/d¹ | 1920×1080 · 30fps · **H264** | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 17 | ✅ | n/d¹ | 1920×1080 · 30fps · **H264** | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 18 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 19 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 20 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 21 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 22 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 23 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 24 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 25 | ✅ | n/d¹ | 1920×1080 · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 26 | ✅ | n/d¹ | **2560×1440** · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 27 | ✅ | n/d¹ | **2560×1440** · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 28 | ✅ | n/d¹ | **2560×1440** · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 29 | ✅ | n/d¹ | **2560×1440** · 30fps · H265 | 704×480 · 30fps · H264 | ✅ | ❌ NOVA |
| 30 | — | — | — | — | — | — |
| 31 | — | — | — | — | — | — |
| 32 | — | — | — | — | — | — |

¹ O ONVIF do NVR não expõe modelo por câmera (só o do próprio gravador). Indícios indiretos de
hardware distinto: canais 26–29 são 4MP (2560×1440) e canais 13/15/16/17 entregam principal em
H264 — destoam das demais. Identificação de modelo por canal exige a UI do gravador ou snapshot
(pós-aditivo).

## Leituras da tabela

- **Ocupação:** 29 de 32 canais ocupados · **3 livres** (30–32) — a folga real até o limite do iNVD.
- **Novas:** **21 câmeras nos canais 9–29**, nenhuma cadastrada no sistema. Batem com as "~21
  câmeras ONVIF adicionais" observadas passivamente por WS-Discovery em 04/08
  (`ENDPOINTS_VLAN_NAO_CATALOGADOS.md`) — agora sabemos que estão plugadas **neste** gravador.
- **As 8 atuais:** sem evidência de troca ou mudança de posição — canais 1–8 seguem principal
  H265 1920×1080@30 (compatível com a medição do D-79 no canal 8) e o `channel_map` do edge segue
  1–8 (config_version `54a3c486`). **Ressalva:** ONVIF não prova identidade da câmera; o pareamento
  canal↔posição física segue pendente desde 04/08 (prova visual só com snapshot, pós-decisão).
- **🔴 Codec (o achado da rodada):**
  - Principal: **25× H265** (21 em 1080p + 4 em 2560×1440) e **4× H264** (canais 13, 15, 16, 17).
    A hipótese "as novas são H264" **não se confirmou** — só 4 de 21.
  - **Substream: H264 704×480@30 em TODOS os 29 canais, uniforme (1024 kbps).** Consequência
    direta do D-79: a grade preta (Firefox/Chromium puro/Linux sem VAAPI) é um problema
    **exclusivo do principal**; o `subtype=1` toca em qualquer navegador, para qualquer canal —
    inclusive os novos. Isso fortalece a troca da grade para substream, que segue decisão pendente
    do Vitor.
- Snapshot (`GetSnapshotUri`): disponível nos 29 canais ocupados (URI obtida; imagem **não**
  baixada).
- Bitrate configurado no gravador: principal 4096 kbps e sub 1024 kbps, **iguais em todos os
  canais** — inclusive nos 4MP, o que mantém a conta de banda linear.

## Capacidade — a conta com o número real (29)

| | Hoje (8) | Com 29 ocupados |
|---|---|---|
| Upload no principal | 37 Mbps (medido, D-74/D-78) | **~119–134 Mbps** (nominal 29×4,1 · medido-escalado 29×4,63) |
| Upload no substream | ~6 Mbps | **~22–30 Mbps** |
| Link disponível | 400 Mbps | 400 Mbps — principal+sub de 29 ≈ **35–41%** do link: cabe |
| Egress/mês (grade 8h/dia) | ~US$ 150 | **~US$ 545** (linear ×29/8, mesmas premissas) |

### O que precisa subir junto (antes de QUALQUER ativação)

1. 🔴 **`LIVE_VIEW_MAX_PARALLEL_PUSHES`** — default **8** (`live_view_loop.py`). Com mais câmeras
   na grade, o rodízio volta em versão mais curta. Precisa acompanhar o nº de câmeras ativas.
2. 🔴 **Rate limit do `POST /segment`** — a rota não tem bucket próprio; o device é tratado como
   anônimo e cai no **piso por IP de 900/min** (`rate_limiting.py`, `DEFAULT_IP_LIMIT`). 8 câmeras
   ≈ 720 req/min — **estoura com ~10 câmeras**; 29 ≈ 2.610 req/min. Precisa bucket dedicado por
   device/rota antes de escalar.
3. ⚠️ **Inferência no Orin — pergunta aberta (não medida nesta rodada, de propósito):** a
   capacidade nunca foi medida para >8 streams. O substream uniforme (H264 704×480) barateia o
   decode via NVDEC, mas não responde a pergunta — **ela decide se 29 câmeras cabem em um Orin ou
   se precisa de dois.**

## O lado bom — coleta multi-câmera para a volta 2

O pool de 31/07 é de **uma câmera só** (D-68) e por isso o modelo da volta 1 não generaliza.
**21 câmeras novas = a coleta multi-câmera que falta para a volta 2 valer alguma coisa.**

Sobre ângulos: as áreas físicas dos canais 9–29 são desconhecidas (pareamento canal↔posição nunca
foi feito nem para as 8). Os indícios de que há cobertura **diferente** — não só câmera a mais no
mesmo lugar: (a) canais 26–29 são 4MP, hardware de outra geração, típico de instalação nova em
área nova; (b) canais 13/15/16/17 em H264 sugerem outro lote/fabricante OEM. **Mapear canal→área
com a RVB (walkthrough ou snapshots pós-aditivo) é o próximo passo natural — ângulo diferente vale
mais que câmera a mais no mesmo lugar.**

## 🛑 Decisão do Vitor (depois desta tabela)

Ativar **quais** e **quando** depende do aditivo com a RVB. Com a tabela, a conversa tem número:
*são 21 câmeras a mais (29 no total), ~US$ 545/mês de egress na grade 8h/dia (vs ~US$ 150 hoje),
cabem no link de 400 Mbps, e exigem 2 ajustes de software (paralelismo do live view e bucket do
/segment) + 1 medição (inferência >8 streams no Orin).*

## Pendências registradas

- Pareamento canal↔posição física (nenhum canal, nem 1–8) — desde 04/08.
- Modelo por câmera não exposto via ONVIF do NVR — precisa UI do gravador ou snapshot.
- Capacidade de inferência do Orin >8 streams — nunca medida; decide 1 Orin vs 2.
- Titularidade dos 2 iMHDX 3132 (`.210`/`.211`) — **não sondados** nesta rodada (fora da
  autorização), seguem como em 04/08.

---

*Dados brutos: sondagem de 2026-08-11 ~20h20, 34 chamadas SOAP, resultado JSON íntegro no
scratchpad da sessão (58 perfis, 29 video sources). Decisão: D-85 no `REGISTRO_DE_DECISOES.md`.*
