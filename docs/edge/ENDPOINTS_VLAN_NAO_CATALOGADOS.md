# Endpoints VLAN não catalogados — Descoberta de 2026-08-04

**Data da observação:** 2026-08-04  
**Método:** WS-Discovery passivo (UDP multicast 239.255.255.250:3702)  
**Executado do:** Jetson Orin NX (pandora, 100.93.126.76 via Tailscale)  
**Autorização:** Protocolo anti-lockout autorizado para sondagem de VLAN de câmeras (ADR-0020, decisão de Vitor, 2026-08-04)  
**Fonte:** `tools/agent-driver/tasks/DEV-FECHAR-A-PRIMEIRA-VOLTA-DO-FLYWHEEL-PROMPT.md:155-168`

---

## ⚠️ IMPORTANTE: Titularidade desconhecida

Os endpoints listados abaixo foram **observados passivamente** via WS-Discovery na VLAN de câmeras da RVB. **Não foi realizada qualquer conexão ativa** (RTSP, HTTP, ONVIF request) a nenhum deles.

**A titularidade destes dispositivos é desconhecida.** O protocolo anti-lockout que autorizou a sondagem da VLAN valia explicitamente para:
- Gravador **Intelbras iNVD 3032** (8 canais, IPs .9/.21/.29/.30/.31/.33/.34/.35) — cliente (RVB), acesso autorizado

Para os endpoints não catalogados (.210, .211, e câmeras adicionais), **a decisão de qualquer contato posterior é do Vitor, após confirmação com a RVB de quem são.**

**⛔ Nenhuma tentativa de autenticação, sondagem de porta ou coleta de configuração deve ser realizada sem essa confirmação e reautorização.**

---

## Descoberta: tabela consolidada

| IP VLAN | Modelo (se conhecido) | Tipo | Método de descoberta | Observação |
|---|---|---|---|---|
| `.210` | **iMHDX 3132** | Gravador | WS-Discovery | Não catalogado em DB nem em config/poll · titularidade desconhecida |
| `.211` | **iMHDX 3132** | Gravador | WS-Discovery | Não catalogado em DB nem em config/poll · titularidade desconhecida |
| `.9` | — | Câmera ONVIF | WS-Discovery | Vinculada ao iNVD 3032 (canais 1–8; pareamento canal↔IP individual não confirmado) · **online** |
| `.21` | — | Câmera ONVIF | WS-Discovery | Vinculada ao iNVD 3032 (canais 1–8; pareamento canal↔IP individual não confirmado) · **online** |
| `.29` | — | Câmera ONVIF | WS-Discovery | Vinculada ao iNVD 3032 (canais 1–8; pareamento canal↔IP individual não confirmado) · **online** |
| `.30` | — | Câmera ONVIF | WS-Discovery | Vinculada ao iNVD 3032 (canais 1–8; pareamento canal↔IP individual não confirmado) · **online** |
| `.31` | — | Câmera ONVIF | WS-Discovery | Vinculada ao iNVD 3032 (canais 1–8; pareamento canal↔IP individual não confirmado) · **online** |
| `.33` | — | Câmera ONVIF | WS-Discovery | Vinculada ao iNVD 3032 (canais 1–8; pareamento canal↔IP individual não confirmado) · **online** |
| `.34` | — | Câmera ONVIF | WS-Discovery | Vinculada ao iNVD 3032 (canais 1–8; pareamento canal↔IP individual não confirmado) · **online** |
| `.35` | — | Câmera ONVIF | WS-Discovery | Vinculada ao iNVD 3032 (canais 1–8; pareamento canal↔IP individual não confirmado) · **online** |
| **(~21 adicionais)** | — | Câmera ONVIF | WS-Discovery | **Não identificadas individualmente** · titularidade desconhecida · contagem aproximada |

---

## Resumo da descoberta

### Equipamentos catalogados (conhecidos do cliente)
- **Gravador:** Intelbras iNVD 3032, 8 canais, todos **online**
- **Câmeras afiliadas:** 8 câmeras ONVIF (uma por canal), IPs .9 a .35 (conforme tabela)
- **Status:** apenas **2 de 8** cadastradas no banco (canais 1 e 2, `public.cameras`); as 6 restantes aguardam mapeamento canal↔posição↔módulo do Vitor (rodada 2026-08-04) · box consome o mapa de canais via config/poll (ADR-0058, PR #281)

### Equipamentos não catalogados (descobertos por WS-Discovery, titularidade desconhecida)
- **2 gravadores iMHDX 3132** (`.210`, `.211`)
  - Modelo diferente do iNVD 3032 conhecido
  - Não aparecem no banco de dados de câmeras (`public.cameras`, com `tenant_id`)
  - Não aparecem em `RECORDER_CHANNEL_MAP` do edge
  - **Status:** Observado passivamente · não contactado

- **~21 câmeras ONVIF** adicionais
  - Além das 8 do iNVD 3032 já catalogadas
  - Identidades individuais não levantadas (escopo: apenas documentar a existência, não sondar)
  - Titularidade desconhecida
  - **Status:** Observado passivamente · não contactado

---

## Insumo para o contrato

A distinção entre *o que o Recognition consegue ver na rede* e *o que está contratado para processar* é fundamental para redação de responsabilidades:

- **Escopo contratual:** módulo EPI (câmeras do iNVD 3032), módulo Qualidade, pátio/estacionamento — conforme `docs/negocio/MODULOS_RVB.md`
- **Escopo de visibilidade de rede:** inclui todos os dispositivos ONVIF que respondem a WS-Discovery neste subnet
- **Relevância jurídica:** a existência de endpoints adicionais não implica que o Recognition acesse ou processe dados deles, mas precisa estar refletida em cláusulas de escopo e segurança

Veja: `docs/negocio/DICIONARIO_CONTRATO_RECOGNITION.md` (seção sobre visibilidade vs. escopo contratual).

---

## Próximos passos

1. **Vitor confirma com RVB** de quem são os dois iMHDX 3132 e as ~21 câmeras adicionais
2. **Caso confirmado que são do cliente:**
   - Avaliar se devem ser incluídos no escopo contratual e mapeamento de módulos
   - Revalidar a capacidade do Orin com a contagem total de câmeras
   - Decidir ordem de onboarding (rampa)
3. **Caso confirmado que não são do cliente ou são inoperantes:**
   - Registrar a descoberta como achado de auditoria de rede
   - Documentar recomendação de segurança: isolar ou desativar dispositivos não utilizados
4. **Segurança:** manter o protocolo anti-lockout — qualquer contato futuro requer reautorização explícita por escopo

---

## Referências

- **Protocolo anti-lockout:** `tools/agent-driver/tasks/DEV-DESCOBERTA-NVR-E-FECHAMENTO-RODADA-PROMPT.md:1.1`
- **ADR-0052 (ONVIF/WS-Discovery):** `docs/decisions/adr/0052-onvif-discovery-camera-plug-and-play.md`
- **ADR-0020 (MikroTik/WireGuard):** `docs/decisions/adr/0020-mikrotik-wireguard-hub-and-spoke.md`
- **Contrato/dicionário:** `docs/negocio/DICIONARIO_CONTRATO_RECOGNITION.md`
