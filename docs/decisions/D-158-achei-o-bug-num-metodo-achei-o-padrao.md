# D-158 · "Achei o bug num método" ≠ "achei o PADRÃO"

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **lição de processo**

O #392 consertou `delete_camera` (`camera["tenant_id"]` comparado com `user_id`) e **declarou o bug
resolvido**. Tinha **três irmãos vivos** com a linha idêntica:

| Método | Efeito |
|---|---|
| `update_camera` | 🔴 **editar câmera falhava sempre para não-admin** — user-facing, nunca reportado |
| `build_rtsp_url` | idem |
| `build_stream_url` | idem |

O Vitor relatou *"não consigo remover câmeras"*. **Editar provavelmente também falhava**, e foi
atribuído a outra coisa.

**Regra:** quando o bug nasce de **nome de parâmetro que mente** (aqui, `user_id` recebendo `tenant_id`),
o defeito é copiável por leitura — grepe o **padrão inteiro** antes de declarar consertado, não só o
método que apareceu no relato. Os quatro agora respondem **404** em cross-tenant (C-01).
