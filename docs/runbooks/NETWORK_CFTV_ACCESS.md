# Acesso ao CFTV + Rede do Edge — Runbook (Hikvision / Intelbras)

> Como o Orin NX se conecta às câmeras do cliente **sem travar o CFTV existente** e **sem expor nada
> à internet**. Esta etapa mal definida = risco de perder o sistema; por isso o **site survey
> (seção 5) é pré-requisito de go-live**. Referenciado por tasks 031 (site_gateways), 033 (edge
> stack + MikroTik), 046 (onboarding/probe), 037 (go-live).

## 1. Princípio que elimina o medo de "travar a câmera"
Ler RTSP **não trava** a câmera nem para a gravação do DVR/NVR. O que trava é:
(a) abrir o **stream principal** (alta resolução) e saturar o encoder/uplink da câmera, ou
(b) estourar o **limite de conexões RTSP simultâneas** da câmera (tipicamente 4–10).

**Regra de ouro:** o edge consome **APENAS o substream** (baixa resolução, 5fps, H.265). O substream
existe justamente para clientes secundários. O DVR/NVR continua gravando o principal **intocado** —
nós só assinamos um feed paralelo leve. Antes de escalar, confirmar no site o **máximo de conexões**
por câmera e que o substream está habilitado.

## 2. De onde puxar o vídeo (decidir por site no survey)
- **Opção A — direto da câmera (preferida):** câmera → switch → Orin NX, RTSP substream por IP.
  Mais paralelo, menor latência, independe do NVR.
- **Opção B — do NVR/DVR:** alguns NVRs expõem RTSP por canal. Uma só integração, mas adiciona
  dependência do NVR e tem limite de conexões próprio. Usar se não tivermos credencial das câmeras.
A escolha depende da topologia e de quais credenciais o cliente fornece.

## 3. URLs por marca (o wizard task-046 já tem perfis)
- **Hikvision** — principal: `rtsp://user:pass@IP:554/Streaming/Channels/101` ·
  **substream: `.../Streaming/Channels/102`**. ONVIF + ISAPI suportados.
- **Intelbras** — principal: `rtsp://user:pass@IP:554/cam/realmonitor?channel=1&subtype=0` ·
  **substream: `subtype=1`**. ONVIF suportado.
- Sempre passar pelo `RTSPUrlValidator` (anti-SSRF, IP pinning) antes do FFmpeg/probe (task-046).

> ⚠️ **Pegadinha Hikvision — H.265+ / H.264+.** Por padrão a Hikvision usa codec **proprietário**
> (H.265+/H.264+) que FFmpeg/DeepStream **não decodificam de forma confiável**. No survey/onboarding,
> trocar o substream para **H.265 ou H.264 padrão** (config da câmera via web/ISAPI). Sem isso, o
> stream conecta mas a inferência recebe lixo. Itens mistos (RVB = Intelbras + Hikvision) → checar
> codec **câmera a câmera**.

## 4. Topologia de rede e MikroTik (seguro por design)
```
Câmeras (VLAN CFTV)  ──┐
NVR/DVR              ──┤── switch ── [Orin NX]──┐
                       │  (LAN/VLAN do cliente) │ WireGuard OUTBOUND-only
                    MikroTik ───────────────────┘──► Cloud (Railway hub) + R2
```
- **Câmeras NUNCA recebem IP público.** Zero port-forwarding. O único caminho de entrada é a
  **overlay WireGuard** que o **MikroTik disca pra fora** (hub-and-spoke, ADR-0020 / task-031/033).
- **RTSP fica na LAN** entre câmera e Orin NX. Só **saem da rede**: eventos de detecção + evidência
  (pra R2), por **TLS**. Vídeo bruto do CFTV não trafega pra internet.
- **Isolamento:** câmeras idealmente em **VLAN própria**; o MikroTik impede a VLAN CFTV de falar
  direto com a internet — só o Orin NX sai. Protege o CFTV do cliente como vetor de ataque.
- **Credenciais das câmeras** ficam cifradas no edge (Fernet, `CAMERA_SECRET_KEY`), nunca no payload
  nem no repo.
- Acesso remoto nosso (suporte) e o frontend alcançam o edge **só pela overlay** — nunca porta aberta.

## 5. SITE SURVEY — preencher ANTES do go-live (pré-requisito, por cliente)
- [ ] Marca/modelo e **quantidade** por câmera (RVB: frota **mista Intelbras VIP + Hikvision** ·
      Roccabela: confirmar). Mapear **câmera a câmera** porque a marca muda a URL e o codec.
- [ ] Substream habilitado? Resolução/fps configuráveis? Codec **padrão** (H.265/H.264, **não** H.265+/H.264+)?
- [ ] **Máximo de conexões RTSP** por câmera (e quantas o DVR/NVR já usa).
- [ ] Existe NVR/DVR? Expõe RTSP por canal? Temos credencial das câmeras OU do NVR?
- [ ] Topologia: VLAN do CFTV? Faixa de IP das câmeras? Há DHCP ou IP fixo?
- [ ] Onde o Orin NX entra na rede (porta do switch / VLAN)? Há uplink de internet pra overlay?
- [ ] Quem é o responsável de TI/segurança do cliente que autoriza o acesso.

## 6. Plano de de-risco (ordem segura, não "tudo de uma vez")
1. Survey preenchido + credenciais combinadas.
2. **Probe read-only de 2–3 câmeras** (task-046 `/probe`): confirma que conecta no substream **sem
   perturbar** o CFTV. É o teste mais seguro — só assina, não muda nada.
3. Escalar pro lote completo medindo banda (28 substreams ≈ 15–30 Mbps, trivial pra GbE) e conexões.
4. MikroTik provisionado (task-033) + overlay validada antes de processar.
5. Bench do Orin NX (EDGE_HARDWARE_ACCEPTANCE.md) com a carga real.

## 7. Riscos reais e mitigação (resumo)
| Risco | Mitigação |
|-------|-----------|
| Travar câmera / DVR por excesso de conexão | Só substream; confirmar limite no survey; probe gradual |
| Saturar rede/encoder | Substream + H.265 + 5fps; nunca o principal |
| Expor câmera à internet | Zero port-forward; WireGuard outbound-only; VLAN isolada |
| Vazar credencial de câmera | Fernet no edge; derivar tenant do device token; nunca no payload |
| GbE única saturando | Substream mantém ~15–30 Mbps; folga enorme em GbE |
