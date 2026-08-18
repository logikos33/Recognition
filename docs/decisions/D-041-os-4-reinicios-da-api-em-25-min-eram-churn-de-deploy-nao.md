# D-041 · Os "4 reinícios da API em 25 min" eram churn de deploy, não falha de plataforma

**Seção:** Rodada de 04/08 — Live view fluido + canal 6 · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ⚠️ SUBSTITUÍDA por [[D-51]] (3ª rodada, 04/08)**

> **Substituída — não apagada.** A *direção* estava certa (era churn de deploy, não crash de plataforma),
> mas duas coisas estavam erradas e a 3ª rodada as corrigiu com evidência: (1) a **atribuição** — não eram
> os merges #288–#292 de uma rodada anterior, e sim a cascata de `railway up` da própria rodada; (2) a
> **prova** — o "soak" que sustentou esta conclusão capturou só **22 segundos** de log (não 15 min), então
> nunca observou a cascata das 18:32–18:58. Ver [[D-51]] para a causa raiz provada. Texto original mantido
> abaixo como registro do que foi concluído na hora.

O padrão start→SIGTERM~7s no log de 04/08 entre 16:29 e 16:53 era o Railway subindo container novo e
desligando o antigo a cada merge (#288–#292) somado aos redeploys manuais da rodada anterior. Não houve
OOM nem healthcheck reprovando. Confirmado: API estável e `/health` 200 desde 16:49Z; a janela sem
gunicorn depois de 16:53 foi só o fim da sequência de deploys, não um crash.

Lição: **correlacionar reinício com a timeline de deploy antes de suspeitar de crash de plataforma.**
