# Provisionar token R2 SOMENTE-LEITURA (DEV) — caminho de 60s

> 🔴 **Ato humano do Vitor.** O agente NÃO cria credencial de nuvem (credencial criada
> sem ato humano é acesso auto-concedido). Aqui está o clique exato; o verificador
> (`scripts/ops/verify_r2_ro_access.py`) prova que funcionou no primeiro try.

⛔ **Não reusar `R2_KEY` / `R2_SECRET`** — essas são read-**write**. Este token é RO dedicado.

## Os 7 passos

1. **Cloudflare** → dashboard → **R2** → **Manage R2 API Tokens** (canto sup. dir. da tela R2)
   → **Create API Token**.
2. **Permissão:** **Object Read only** — ⛔ nada acima (não Admin, não Edit).
3. **Bucket:** **Apply to specific buckets only** → selecione **apenas o bucket DEV**
   (o valor de `R2_BUCKET` no serviço API-V3; default `epi-monitor`). ⛔ Nunca "Apply to all buckets".
4. **TTL:** sugerido **90 dias** (renovável; força rotação). Sem TTL = token eterno.
5. **Create.** Saem **3 valores** → cole em cada variável (ambiente do RUNNER, ⛔ não Railway):
   | Valor da Cloudflare | Variável |
   |---|---|
   | Access Key ID | `R2_RO_ACCESS_KEY` |
   | Secret Access Key | `R2_RO_SECRET` |
   | (endpoint) | **reusar `R2_ENDPOINT`** (já existe) |
   - `R2_BUCKET` também reusa o existente.
6. **Onde colar:** no **ambiente do runner de verificação/mineração** (o processo que roda
   `verify_r2_ro_access.py` / a campanha). ⛔ **NÃO** como variável do Railway — a API não usa
   esta credencial RO; ela é só do runner.
7. **Revogar:** Cloudflare → R2 → Manage R2 API Tokens → o token → **Revoke**. (Ou deixar o TTL expirar.)

## Verificar (primeiro try)

```bash
# creds via ENV (nunca argv/ps); o script não imprime chave nem nome de objeto
python3 scripts/ops/verify_r2_ro_access.py
# -> "R2_RO: OK — leitura confirmada ..."  (exit 0)  → pronto
# -> "R2_RO: FALHA — ..."                  (exit 1)  → diz qual variável/permissão falta
```
