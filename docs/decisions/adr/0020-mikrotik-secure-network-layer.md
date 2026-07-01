# ADR-0020 — MikroTik WireGuard como camada de conectividade segura padrão (edge + cloud)

## Status
Aceito · Data: 2026-06-04 · Autores: Vitor Emanuel (Logikos)
Relacionado: ADR-0004 (HTTP polling edge↔cloud), ADR-0007 (deployment modes), ADR-0008 (device tokens RS256),
ADR-0016 (edge tables placement). Companion: `docs/architecture/HARNESS_EXPLORATORIO.md` / `HARNESS_PLANO_IMPLEMENTACAO.md`.

## Context
Os clientes ficam atrás de NAT/firewall. As câmeras (Hikvision/Intelbras) **não podem ser expostas à internet**:
após poucas tentativas de senha erradas elas **travam** (lockout anti-brute-force) — então port-forwarding/IP
público é inviável e inseguro. Precisamos, de forma uniforme:
- **Edge:** acessar remotamente o Mini PC (operar/diagnosticar) sem abrir porta — realizar o O2.
- **Cloud-only:** alcançar as câmeras na LAN do cliente pra puxar RTSP, sem expô-las.
- **Futuro:** configurar toda a operação (rede, câmeras, edge) pelo nosso front.

## Decision
Adotar o **MikroTik (RouterOS v7, WireGuard nativo) como a camada de rede/VPN padrão de TODO site cliente**,
edge ou cloud-only. Topologia **hub-and-spoke**: o MikroTik disca **outbound** para um WG hub público no cloud
(funciona atrás de CGNAT/NAT duplo, sem porta aberta no cliente). Sobre essa overlay:
- **Edge:** alcançamos o Mini PC, as câmeras e o próprio MikroTik → o MikroTik **realiza o O2** (acesso remoto seguro).
- **Cloud-only:** o MikroTik é o relay que leva o RTSP da câmera ao cloud (inferência no cloud, Ultralytics).
- **Gerenciável pelo front:** provisionamento de chaves WG + config via **RouterOS REST API** a partir do cloud;
  o MikroTik "se inscreve" no mesmo padrão de enrollment dos device tokens.
- **Segurança:** câmera nunca exposta; firewall na borda restringe (só a overlay alcança a porta RTSP);
  autenticação com **retry-seguro anti-lockout** (em falha de auth, parar e alertar — nunca re-tentar em loop).

## Alternativas consideradas
- **A) Mesh VPN turnkey (Tailscale/Netbird):** control plane pronto + NAT traversal automático + API de chaves.
  Contras: custo por nó (Tailscale) ou self-host (Netbird), dependência de terceiro, menos controle.
  → **Anotada como fallback** para sites sem MikroTik (melhoria futura).
- **B) Hikvision ISUP/Ehome (zero-caixa):** o NVR Hik disca outbound pro nosso servidor (:7660), sem caixa extra.
  Contras: proprietário **só-Hikvision**; exige integrar receptor ISUP (SDK) no cloud.
  → **Anotada como otimização futura** para sites 100% Hikvision.
- **C) Port-forwarding / IP público na câmera:** **REJEITADO** — causa lockout (brute-force de bots) e é inseguro.

## Consequences
**Positivas:** acesso remoto seguro uniforme (edge + cloud) numa caixa que a equipe domina; firewall na borda;
custo zero de licença de VPN; mesma plataforma/banco/painel nos dois modos; base para configurar a operação pelo front.
**Negativas / trade-offs:** WireGuard puro perde o control-plane turnkey → automação via RouterOS API (mais DIY);
o MikroTik vira **ponto único de falha no site** → precisa de plano de self-healing/recuperação remota;
**config-de-rede-pelo-front é alto risco** (firewall errado corta o site / abre brecha) → tem que ser
**capacidade gated, auditada e estagiada** (`risk: security`, com rollback).
**Custo (consequência do modo):** edge é default ≥~6 câmeras (capex único amortiza em ~2-3 meses); cloud-only é
nicho (poucas câmeras / sem hardware / upload suficiente). Ver modelo de break-even no `HARNESS_PLANO_IMPLEMENTACAO`.

## Modelo de dados (previsto — migration-gated)
Tabela `site_gateways` (entidade gerenciável de primeira classe): `id, tenant_id, site_id, type ('mikrotik'),
wg_public_key, overlay_ip, mgmt_status, last_seen_at, routeros_cred_ref (segredo), created_at`. Toda nova tabela
tem `tenant_id` (multi-tenant, C-01). Criada pelo fluxo de migration com checkpoint humano (não autônomo).

## Timing (em que momento)
1. **Agora:** este ADR + o conceito `site_gateways` + a spec do `camera-gateway` em modo cloud (software, fila).
2. **Quando o Mini PC chegar (~semana de 2026-06-09):** MikroTik físico no RVB = roteador do site + WG hub → realiza o O2.
3. **Pós go-live:** relay cloud-only em produção + **config-de-rede-pelo-front** (capacidade gated) + fallbacks (mesh/ISUP).

## Critérios de aceite
- [ ] Conexão sempre **outbound** do site; nenhuma porta aberta; câmera nunca exposta.
- [ ] Edge: Mini PC alcançável pela overlay (O2) sem Tailscale no box.
- [ ] Cloud-only: RTSP da câmera alcançável pelo cloud via o MikroTik, com retry-seguro anti-lockout.
- [ ] `site_gateways` previsto no schema (quando implementado, multi-tenant + segredo de credencial protegido).
- [ ] Config-pelo-front entregue como comando gated/auditado (nunca aplicação direta sem revisão).
