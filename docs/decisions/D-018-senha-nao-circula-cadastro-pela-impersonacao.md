# D-018 · Senha não circula — cadastro pela impersonação

**Seção:** Segurança e multi-tenancy · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · 🔄**

A senha do admin do DEV não é enviada ao Claude, nem colocada em prompt, log, commit ou `argv`.
Caminho: a conta superadmin `vitor@logikos.com` assume o contexto da RVB (D-03) e cadastra de lá.
Alternativa: fluxo de recuperação de senha (ADR-0042 Fase 1) — confirmar se está na `develop`.
