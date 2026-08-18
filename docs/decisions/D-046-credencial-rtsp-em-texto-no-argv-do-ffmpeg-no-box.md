# D-046 · Credencial RTSP em texto no `argv` do ffmpeg no box

**Seção:** Rodada de 04/08 — Live view fluido + canal 6 · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (achado) · 📌 dívida**

Qualquer processo com `ps` no Orin vê a senha do gravador na URL RTSP (`rtsp://user:pass@host/...`) — a
credencial trafega em texto claro na linha de comando do processo ffmpeg. Pré-existente, não introduzido
nesta rodada. Mitigação sugerida: passar a credencial via variável de ambiente do processo ffmpeg em vez
de embuti-la na URL. **Não corrigido agora — registrado.**
