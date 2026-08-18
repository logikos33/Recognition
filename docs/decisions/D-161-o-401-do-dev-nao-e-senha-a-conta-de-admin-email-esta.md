# D-161 · O 401 do DEV não é senha: a conta de `ADMIN_EMAIL` está INATIVA e no tenant errado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **exige ação do Vitor** · ⛔ nenhuma credencial lida, gerada ou adivinhada

Determinado **sem credencial**, só consultando o banco do DEV:

| Campo da conta de `ADMIN_EMAIL` | Valor |
|---|---|
| Existe | ✅ sim |
| `is_active` | ⛔ **false** |
| `role` | `admin` |
| `tenant` | 🔴 **`default`** — não `rvb` |
| Tem hash de senha | sim |

🔴 **Redefinir a senha não resolveria.** A conta está inativa; e mesmo ativada, está no tenant `default`
e não enxergaria os dados do RVB sem impersonação.

**Mapa das contas (sem e-mails), para escolher a certa:**

| tenant | role | ativa | qtd | é e2e |
|---|---|---|---|---|
| **`rvb`** | **admin** | ✅ **sim** | **1** | ⛔ **não** |
| `rvb` | admin | não | 1 | sim |
| `dev` | superadmin | sim | 3 | 1 é e2e |
| `admin` | superadmin | sim | 2 | não |
| `default` | admin | **não** | 1 | não |

✅ **Existe exatamente um admin ATIVO no tenant `rvb` que não é a conta e2e.** É essa que a variável
deveria apontar.

⛔ **A conta e2e NÃO foi usada** — nem para destravar. Ela está na fila para ser rebaixada de superadmin,
e usá-la agora entrincheiraria o problema que se quer remover. A do `rvb` está inativa de todo modo.

**Ação do Vitor:** apontar `ADMIN_EMAIL`/`ADMIN_PASSWORD` do serviço para o admin ativo do `rvb`
(ou ativar a conta de `default` **e** movê-la de tenant — pior caminho, porque cria um admin em
`default` que não deveria existir).
