# D-106 · Rodada RunPod: as sete decisões do Vitor — e a flag NÃO é o controle

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**10/08 · Vitor (decisões) + Claude (execução) · ✅**

1. **`training_third_party_cloud_enabled` LIGA** para o RVB no DEV — mas registrado com clareza:
   **a flag habilita a capacidade; quem impede imagem de operação de sair é a lista
   materializada de `frame_id` do job de propagação** (guard fail-closed, D-108). Flag ligada +
   job mal configurado ≠ vazamento: frame fora da lista **aborta o job**.
2. **RF-DETR ponta a ponta** (Apache 2.0). Caminho Hub/ultralytics **deletado** (D-107).
   Variantes XL/2XL (licença PML, não-Apache) **travadas em código** — dispatch rejeita.
3. **Teto de gasto: US$ 2/job, timeout 1h**, RTX 4090 community — **por tipo de carga**
   (`RUNPOD_MAX_USD_TRAIN` / `RUNPOD_MAX_USD_PROPAGATE`).
4. **Vast apagado** (client + provider + legado; nunca entregou treino — 404 desde 12/07).
   `remote_train.py` preservado como executor. **D-72 fecha**: o dicionário do contrato nomeia
   RunPod e o código agora bate — **um único suboperador (D-38)** para treino E propagação.
5. **Sementes anotadas nos frames de 31/07** (encenação): as 17 caixas de frames de operação
   continuam válidas mas **não vão para nuvem** antes da conversa com a advogada.
6. **Fila de aprovação MVP nesta rodada, com status de rejeitada dentro do MVP** (sem ele a
   fila nunca esvazia e "não revisada" vira indistinguível de "recusada").
7. RunPod em **Pods on-demand** (reusa `remote_train.py` via onstart; zero build de imagem) com
   **3 camadas de garantia de morte**: timeout+trap no pod · watchdog Celery · reconciliador
   beat lendo o Postgres (sobrevive a restart da API). Serverless fica como endurecimento futuro.

Entregue em: #337 (split/linhagem) · #338 (aprovação) · #339 (SCA drift) · #340 (honestidade) ·
#341 (runner) · #342 (propagação) · ADR-0061 · ADR-0062.
