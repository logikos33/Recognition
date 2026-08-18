# D-026 · celery-worker deployado no DEV

**Seção:** Contrato e jurídico · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · ✅ vigente**

Decisão do Vitor (Bloco C3): o worker nunca teve deploy no env Desenvolvimento — sem ele nada assíncrono
roda (dataset COCO, treino, extração de frames, retenção/evidência). Deployado e `celery@… ready`
consumindo todas as filas. **Achado ao subir:** `railway_start.py` fazia `os.chdir('backend/')` — diretório
extinto no monorepo (ADR-0010/0014) — crashando qualquer deploy novo em loop; produção só sobrevivia num
snapshot antigo. Corrigido (PR #289) resolvendo o pacote `app` nos dois layouts reais (checkout
`services/api/` e imagem `Dockerfile.worker` com `services/api/` na raiz). Também: `DATABASE_URL` do worker
no DEV apontava para credencial inválida — corrigido por referência `${{Postgres.DATABASE_URL}}`.
