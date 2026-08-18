# D-009 · Sondagem de gravador: ONVIF primeiro, do Orin, anti-lockout estrito

**Seção:** Segurança e multi-tenancy · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**03/08 · Claude → aceito · ✅ vigente**

A sondagem roda **do Orin**, nunca da nuvem — a VLAN de câmeras é isolada (ADR-0020) e sondar da nuvem
devolve timeout, que seria lido como "não há câmera".
**Uma credencial, validada uma vez. Qualquer 401/403 encerra a sessão — sem retentativa, sem variante.**
O gatilho de lockout é falha de autenticação, não volume.
Resultado 04/08: iNVD 3032, 8 canais, 7 requisições, zero 401/403, RTSP nunca necessário.
