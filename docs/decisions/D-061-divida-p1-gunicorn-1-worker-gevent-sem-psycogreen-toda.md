# D-061 · Dívida P1: gunicorn 1 worker gevent SEM psycogreen — toda query trava o event loop

**Seção:** Rodada 4 — a caça ao congelamento (04/08, noite) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (varredura) · 📌 dívida técnica (não corrigida nesta rodada)**

`railway_start.py` sobe `GeventWebSocketWorker` com `workers=1` e NÃO existe `psycogreen`/wait_callback no
app: `psycopg2` é extensão C — cada query BLOQUEIA o event loop inteiro (todas as conexões SocketIO e
requests HTTP juntas). `POST /segment` faz 1 query por push; com 8 câmeras ~1–2 push/s isso serializa tudo
— explica a latência bimodal 0,05 s × 0,50 s medida. Com as 28 câmeras da RVB vira teto duro. Fix proposto
(PR futuro, tema próprio): `psycogreen.gevent.patch_psycopg()` no boot do worker + client Redis singleton
por processo. Registrado aqui para não se perder.
