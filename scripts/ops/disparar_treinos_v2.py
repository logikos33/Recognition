#!/usr/bin/env python3
"""disparar_treinos_v2.py — leva as 3 variantes do dataset-v2 até a GPU.

O QUE ESTE SCRIPT **NÃO** FAZ (e por quê)
────────────────────────────────────────────────────────────────────────────────
**Não monta zip nenhum.** A instrução original pedia "monte os três ZIPs e suba
pro R2". O código diz outra coisa, e o código vence:

  - `tasks/training.py::_run_runpod_train_job` chama
    `_build_training_dataset_zip(storage, ctx["coco_r2_key"])` e faz
    `storage.upload_bytes(f"{coco_r2_key}/dataset.zip", ...)` a CADA dispatch.
    Um zip pré-colocado por mim seria sobrescrito segundos depois.
  - `_preflight_artefato` valida os OBJETOS SOLTOS sob `{coco_r2_key}/{split}/`,
    NÃO o zip, e a própria docstring dele explica que "o zip é cache DERIVADO"
    (foi essa confusão que causou as 4 falhas de época 0 em 18/08).

Então o trabalho real é o mesmo que `versioning_v2.build_dataset_version_v2`
faz no passo 7: copiar as imagens **R2→R2** (server-side, egress zero) para
`{coco_r2_key}/{split}/{frame_id}.jpg` e subir o `_annotations.coco.json` ao
lado. Baixar 295 MB de imagem para reempacotar e devolver seria pagar banda
para chegar no mesmo lugar.

**Não reimplementa o disparo.** `disparar` monta a linha em `training_jobs` e
chama `dispatch_training` — a esteira inteira (preço → teto de custo → onstart
→ create_pod → watchdog → terminate → billing → INSERT em `trained_models` com
`display_name`) roda como em produção.

**Não roda o A/B.** O holdout não tem gabarito em frame cheio (Sem Luvas = 0
caixas) — `montar_dataset_v2.py` documenta a medição. Termina nos 3 modelos.

AS GUARDAS, E ONDE ELAS VIVEM
────────────────────────────────────────────────────────────────────────────────
épocas/early-stop   `remote_train.py` (EPOCHS=100, EARLY_STOPPING_PATIENCE=15,
                    artefato = `_checkpoint_best`)  — nada a fazer aqui.
timeout/teto        env `RUNPOD_TIMEOUT_SECONDS_TRAIN` / `RUNPOD_MAX_USD_TRAIN`,
                    lidas por `runpod_runner`. A conta que os justifica está em
                    `projetar_timeout()` — MEDIDA, não chutada.
morte do pod        3 camadas do `runpod_runner` (trap, watchdog, reconciler).
nome no nascimento  `_build_display_name`; `nomes` mostra o nome ANTES de gastar.
parcial não entra   `_verify_completed_fn` + `verify_model_artifact` na esteira.

USO
────────────────────────────────────────────────────────────────────────────────
    export DATABASE_URL=... R2_* ... RUNPOD_API_KEY=... PUBLIC_API_URL=...
    python3 scripts/ops/disparar_treinos_v2.py autoteste          # sem rede
    python3 scripts/ops/disparar_treinos_v2.py plano              # só a conta
    python3 scripts/ops/disparar_treinos_v2.py exportar --variante a
    python3 scripts/ops/disparar_treinos_v2.py nomes
    python3 scripts/ops/disparar_treinos_v2.py disparar --variante a
    python3 scripts/ops/disparar_treinos_v2.py status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "services" / "api"))

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"
DATASET_RVB = "96a88fef-fc7c-41cb-80fd-7c1170c90951"   # "EPI RVB operacao"
USER_RVB = "11111111-0000-0000-0000-000000000002"      # vitor@logikosvision.com.br
RAIZ_DATASET = Path(
    os.environ.get("DATASET_V2_DIR", "/Users/vitoremanuel/Logikos-mutirao/dataset-v2")
)
SPLITS = ("train", "val", "test")
COCO_JSON = "_annotations.coco.json"

# Rótulo da versão = nome da pasta em `coco_r2_key`. Segue a numeração do
# acervo (última era v16-volume) para não colidir nem confundir a ordem.
VARIANTES: dict[str, dict[str, str]] = {
    "a": {"versao": "v17a-presenca", "resumo": "presença (5 classes)"},
    "b": {"versao": "v17b-ausencia", "resumo": "presença + ausência como classe"},
    "c": {"versao": "v17c-partes", "resumo": "parte do corpo + EPI"},
}

# ── Hiperparâmetros do treino ──────────────────────────────────────────────────
# imgsz 560: RF-DETR exige múltiplo de 56 (`train_rfdetr` reajusta) e 560 é o
# que os jobs de referência (ab-536) usaram — trocar aqui invalidaria a
# projeção de tempo medida abaixo, que veio deles.
IMGSZ = 560
# BATCH pelo ambiente porque a RunPod NÃO entrega a placa pedida: em 02/09
# pedimos 4090 (24 GiB) nos dois braços e veio uma A6000 (47,4 GiB) no segundo,
# e o `_cap_de_batch()` do runner — certo para produção — liberou 16 num braço e
# 4 no outro. Num experimento isso é um hiperparâmetro decidido pelo sorteio da
# plataforma. Com BATCH=4 + BATCH_FIXO=1 o runner ABORTA se a placa não
# comportar, em vez de escolher outro valor calado. Batch efetivo segue 16
# (4 × grad_accum 4) em qualquer placa que venha.
BATCH = int(os.environ.get("BATCH", "16"))
EPOCAS_TETO = 100   # TETO, não alvo — quem encerra é o early-stop (paciência 15)


# ══════════════════════════════════════════════════════════════════ a conta ══
#
# Medições reais deste mesmo acervo, do próprio banco do DEV
# (`training_jobs` × `dataset_versions`, segundos/época = duração ÷ current_epoch):
#
#   job       variante        train+val   s/época   GPU
#   f5442076  v15-tudo            4260       154    RTX 4090
#   0307e2b1  v16-volume          2002       174    RTX 4090
#   28dc8844  v15-so-humano       2073       138    RTX 4090
#   a05becbe  v11-freeze          4549        88    RTX 4090
#   21ea3d00  v8-propositor       1596       105    RTX 4090
#   5894a860  v8-propositor       1596       348    ← MORREU no relógio, ép.16/50
#
# As duas últimas linhas são o MESMO dataset e o mesmo pedido: 105 vs 348 s/época.
# Isso não é variação de carga — é a COMMUNITY sorteando a máquina. Fator 3,31×.
# Foi essa mediana ignorada que matou o 5894a860, e é por isso que a projeção
# abaixo multiplica pelo pior caso em vez de pela média.
REF_JOB = "f5442076"          # o mais próximo em volume do nosso
REF_IMAGENS = 3611 + 649      # train+val do v15-tudo
REF_S_POR_EPOCA = 154.0
FATOR_LOTERIA = 348.0 / 105.0  # 3,31× — MESMO dataset, máquinas diferentes
SETUP_E_EXPORT_S = 1200        # pip install + download do zip + export/validação/upload
MARGEM = 1.5                   # a margem que a guarda pede

# ── O PREÇO QUE A ESTEIRA NÃO ENXERGA ─────────────────────────────────────────
# `RunPodClient.get_gpu_price` devolve `lowestPrice.uninterruptablePrice` — que é
# o preço da COMMUNITY — INDEPENDENTE do `cloud_type` com que o pod é criado.
# Medido em 02/09 pelo GraphQL, RTX 4090: communityPrice 0,34 · securePrice 0,74.
# Logo, rodando em SECURE, `check_cost_cap` protege contra um número 2,2× MENOR
# que a conta real. Quem define o orçamento aqui tem de usar o preço de VERDADE.
PRECO_REAL_USD_H = {"COMMUNITY": 0.34, "SECURE": 0.74}
TETO_RODADA_USD = 40.0
N_TREINOS = 3


# ── A MEDIÇÃO QUE SUBSTITUI A EXTRAPOLAÇÃO ────────────────────────────────────
# Medido NO POD REAL do treino A (job 04508616, pod tep7xhdt469zoy, RTX 4090
# SECURE, batch 4 × grad_accum 4, imgsz 560, 3.560 train + 1.175 val):
#     ép.3→4 = 274 s   ·   ép.4→5 = 288 s   →   281 s/época
#     setup (pod criado → época 1) = 444 s
# A extrapolação dizia 171 s/época — errou 1,64× para baixo, porque o nosso val
# é 1,8× o da referência e o RF-DETR valida a CADA época. Com medida na mão, o
# fator de loteria da COMMUNITY sai da conta: ele existia para cobrir a máquina
# sorteada, e esta máquina não é mais hipótese — está rodando. A margem de 1,5×
# FICA (cobre a variação entre épocas e o export final).
S_POR_EPOCA_MEDIDO = 281.0
SETUP_MEDIDO_S = 444


def projetar_timeout_medido(
    preco_usd_h: float = 0.74, teto_rodada: float = TETO_RODADA_USD,
) -> dict[str, Any]:
    """Timeout a partir do s/época MEDIDO no pod, não de extrapolação."""
    bruto = S_POR_EPOCA_MEDIDO * EPOCAS_TETO + SETUP_MEDIDO_S + 400  # +export/upload
    por_cobertura = int(bruto * MARGEM)
    por_orcamento = int(teto_rodada / N_TREINOS / preco_usd_h * 3600)
    timeout = min(por_cobertura, por_orcamento)
    return {
        "fonte": "medido no pod tep7xhdt469zoy",
        "s_por_epoca": S_POR_EPOCA_MEDIDO,
        "cem_epocas_s": int(bruto),
        "timeout_s": timeout,
        "horas": round(timeout / 3600, 2),
        "restricao": "orcamento" if por_orcamento < por_cobertura else "cobertura",
        "custo_estimado_usd": round(preco_usd_h * timeout / 3600, 2),
        "folga_sobre_cem_epocas": round(timeout / bruto, 2),
    }


def projetar_timeout(
    train: int, val: int, preco_usd_h: float = 0.74,
    teto_rodada: float = TETO_RODADA_USD,
) -> dict[str, Any]:
    """Timeout do pod POR MEDIÇÃO, com o pior caso histórico — nunca a mediana.

    Duas restrições, e vale a MENOR:

    1. **Cobrir o pior caso.** Escala linear no volume (train+val, porque o
       RF-DETR valida a cada época) × fator de loteria medido + setup, × margem.
    2. **Caber no orçamento.** O timeout é o teto de gasto REAL do pod
       (`timeout × preço`). Com 3 treinos e US$ 40, cada um pode no máximo
       `teto_rodada / 3 / preço` horas.

    Em COMMUNITY (0,34/h) a restrição 1 manda. Em SECURE (0,74/h) a 2 manda: a
    margem de 1,5× custaria US$ 53,6 nos três, acima do teto da rodada. O que
    sai é dito no campo `restricao`, nunca escondido — e mesmo o timeout
    orçamentário ainda cobre 100 épocas no PIOR s/época já medido (é o que
    `folga_sobre_pior_caso` prova).
    """
    imagens = train + val
    s_bom = REF_S_POR_EPOCA * imagens / REF_IMAGENS
    s_pior = s_bom * FATOR_LOTERIA
    pior_caso_s = s_pior * EPOCAS_TETO + SETUP_E_EXPORT_S

    por_cobertura = int(pior_caso_s * MARGEM)
    por_orcamento = int(teto_rodada / N_TREINOS / preco_usd_h * 3600)
    timeout = min(por_cobertura, por_orcamento)
    return {
        "imagens": imagens,
        "s_por_epoca_bom": round(s_bom, 1),
        "s_por_epoca_pior": round(s_pior, 1),
        "pior_caso_100_epocas_s": int(pior_caso_s),
        "timeout_por_cobertura_s": por_cobertura,
        "timeout_por_orcamento_s": por_orcamento,
        "restricao": "orcamento" if por_orcamento < por_cobertura else "cobertura",
        "timeout_s": timeout,
        "horas": round(timeout / 3600, 2),
        "preco_usd_h": preco_usd_h,
        "folga_sobre_pior_caso": round(timeout / pior_caso_s, 2),
    }


def teto_custo(timeout_s: int, preco_usd_h: float) -> float:
    """`estimate_cost_usd` calcula sobre o TIMEOUT, não sobre o tempo real —
    subir o timeout sobe o custo ESTIMADO e pode bater no teto. O teto tem de
    caber no orçamento da rodada: 3 treinos × teto ≤ US$ 40."""
    return round(preco_usd_h * timeout_s / 3600.0, 2)


# ═════════════════════════════════════════════════════════════════ infra ══

def _bootstrap() -> None:
    from app.infrastructure.database.connection import DatabasePool, get_database_url

    if DatabasePool.get_instance() is None:
        DatabasePool.initialize(get_database_url())


def _repo():
    from app.infrastructure.database.repositories.annotation_repository import (
        AnnotationRepository,
    )
    from app.infrastructure.database.connection import DatabasePool

    return AnnotationRepository(DatabasePool.get_instance())


def _storage():
    from app.infrastructure.storage.local_storage import get_storage

    return get_storage(TENANT_RVB)


def _coco(variante: str, split: str) -> dict[str, Any]:
    return json.loads(
        (RAIZ_DATASET / f"variante-{variante}" / split / COCO_JSON).read_text()
    )


def _base_key(versao: str) -> str:
    return f"dataset-exports/{TENANT_RVB}/{DATASET_RVB}/{versao}"


# ══════════════════════════════════════════════════════════════ exportar ══

def exportar(variante: str, somente_registro: bool = False) -> dict[str, Any]:
    """Copia imagens R2→R2 + sobe os COCO + cria a `dataset_versions`.

    Espelha o passo 7 de `build_dataset_version_v2` — de propósito: é o layout
    que `_preflight_artefato` e `_build_training_dataset_zip` sabem ler.
    Idempotente: `copy_object` sobrescreve, e a row é reusada se já existir.

    `somente_registro=True` refaz só a linha do banco (15 mil cópias R2 levam
    ~7 min por variante e não mudam quando o que mudou foi a contabilidade).
    """
    _bootstrap()
    versao = VARIANTES[variante]["versao"]
    base = _base_key(versao)
    st, repo = _storage(), _repo()

    cocos = {s: _coco(variante, s) for s in SPLITS}
    ids = sorted({
        img["file_name"].rsplit(".", 1)[0]
        for c in cocos.values() for img in c["images"]
    })
    linhas = repo._execute(
        "SELECT id::text AS id, r2_key FROM training_frames "
        "WHERE id = ANY(%s::uuid[]) AND tenant_id = %s",
        (ids, TENANT_RVB),
    )
    origem = {r["id"]: r["r2_key"] for r in linhas if r.get("r2_key")}
    faltando = [i for i in ids if i not in origem]
    if faltando:
        # Sem isto o COCO declararia imagem que nunca chegou ao R2 e o
        # `_conferir_zip_contra_coco` só reclamaria DEPOIS, no dispatch.
        raise SystemExit(
            f"{len(faltando)} frames sem r2_key no tenant RVB (ex.: {faltando[:3]}) "
            "— nada foi exportado."
        )

    def _copiar(par: tuple[str, str, str]) -> str | None:
        split, fid, dest = par
        try:
            st.copy_object(origem[fid], dest)
            return None
        except Exception as exc:  # noqa: BLE001
            return f"{split}/{fid}: {exc}"

    tarefas: list[tuple[str, str, str]] = []
    for split, coco in cocos.items():
        for img in coco["images"]:
            fid = img["file_name"].rsplit(".", 1)[0]
            tarefas.append((split, fid, f"{base}/{split}/{img['file_name']}"))

    if not somente_registro:
        with ThreadPoolExecutor(max_workers=16) as pool:
            erros = [e for e in pool.map(_copiar, tarefas) if e]
        if erros:
            raise SystemExit(f"{len(erros)} cópias falharam (ex.: {erros[:3]}) — abortado.")

        for split, coco in cocos.items():
            st.upload_bytes(
                f"{base}/{split}/{COCO_JSON}",
                json.dumps(coco).encode("utf-8"),
                "application/json",
            )

    # class_distribution = contagem REAL por classe desta variante. É daqui que
    # `_fetch_scope_info`/`_derive_scope` tiram o <escopo> do display_name —
    # cada variante tem taxonomia própria, então cada uma nasce com nome próprio.
    dist: dict[str, int] = {}
    declaradas: set[str] = set()
    for coco in cocos.values():
        nomes = {c["id"]: c["name"] for c in coco["categories"]}
        declaradas |= {n for n in nomes.values() if n != "recognition"}
        for ann in coco["annotations"]:
            n = nomes[ann["category_id"]]
            dist[n] = dist.get(n, 0) + 1

    # Classe DECLARADA na taxonomia com ZERO instância no acervo. O modelo ganha
    # o slot na cabeça e nunca prevê nada nele — quem ler as métricas depois
    # precisa ver isso, e não descobrir olhando o COCO. Mesma chave reservada de
    # `versioning_v2` (prefixo "__", filtrada por `_classes_treinadas`, então NÃO
    # entra no <escopo> do display_name).
    vazias = sorted(declaradas - set(dist))
    if vazias:
        dist["__sem_suporte_treino__"] = vazias

    contagens = {s: len(cocos[s]["images"]) for s in SPLITS}
    existente = repo._execute_one(
        "SELECT id::text AS id FROM dataset_versions "
        "WHERE tenant_id = %s AND dataset_id = %s AND version = %s",
        (TENANT_RVB, DATASET_RVB, versao),
    )
    if existente:
        repo._execute_mutation_no_return(
            "UPDATE dataset_versions SET class_distribution = %s::jsonb, "
            "coco_r2_key = %s, status = 'ready', frame_count = %s, "
            "train_count = %s, val_count = %s, test_count = %s WHERE id = %s",
            (json.dumps(dist), base, sum(contagens.values()),
             contagens["train"], contagens["val"], contagens["test"], existente["id"]),
        )
        dsv_id = existente["id"]
    else:
        from app.infrastructure.database.repositories.dataset_repository import (
            DatasetRepository,
        )
        from app.infrastructure.database.connection import DatabasePool

        row = DatasetRepository(DatabasePool.get_instance()).create_version_v2({
            "user_id": USER_RVB, "version": versao,
            "frame_count": sum(contagens.values()),
            "train_count": contagens["train"], "val_count": contagens["val"],
            "test_count": contagens["test"], "class_distribution": dist,
            "tenant_id": TENANT_RVB, "module_code": "epi",
            "dataset_id": DATASET_RVB,
            "split": {"train": 0.7, "val": 0.23, "test": 0.05},
            "coco_r2_key": base, "export_format": "coco",
            "status": "ready", "created_by": USER_RVB,
        })
        dsv_id = str(row["id"])

    return {
        "variante": variante, "versao": versao, "dataset_version_id": dsv_id,
        "coco_r2_key": base,
        "copiadas": 0 if somente_registro else len(tarefas),
        "contagens": contagens,
        "classes_com_anotacao": len([k for k in dist if not k.startswith("__")]),
        "classes_sem_instancia": vazias,
    }


# ═════════════════════════════════════════════════════════════════ nomes ══

def nomes() -> list[dict[str, str]]:
    """O display_name que CADA variante vai receber — antes de gastar um centavo.

    Usa as mesmas funções do dispatch (`_fetch_scope_info`/`_build_display_name`),
    nunca uma cópia: se o nome sair errado aqui, sai errado lá.
    """
    _bootstrap()
    from app.infrastructure.queue.tasks.training import (
        _build_display_name, _fetch_scope_info,
    )

    repo = _repo()
    saida = []
    for v, meta in VARIANTES.items():
        row = repo._execute_one(
            "SELECT id::text AS id FROM dataset_versions WHERE tenant_id = %s "
            "AND dataset_id = %s AND version = %s",
            (TENANT_RVB, DATASET_RVB, meta["versao"]),
        )
        if not row:
            saida.append({"variante": v, "display_name": "(sem dataset_version)"})
            continue
        mod, esc = _fetch_scope_info(repo, row["id"])
        saida.append({
            "variante": v, "versao": meta["versao"], "modulo": mod, "escopo": esc or "",
            "display_name": _build_display_name(0, module_code=mod, escopo=esc),
        })
    return saida


# ══════════════════════════════════════════════════════════════ disparar ══

def sondar() -> dict[str, Any]:
    """Cria e MATA um pod com o spec EXATO do treino, só pra saber se há máquina.

    Existe porque `_run_runpod_train_job` monta o `dataset.zip` (4.983 downloads
    sequenciais + upload de 349 MB ≈ 35 min) ANTES de chamar `create_pod`. O
    primeiro disparo gastou esses 35 minutos para receber "There are no
    instances currently available" — a resposta que esta sonda dá em 3 segundos.
    Custo: o pod vive menos de um segundo (fração de centavo).
    """
    import os as _os

    from app.infrastructure.gpu.runpod_client import RunPodClient
    from app.infrastructure.gpu.runpod_runner import (
        cloud_type_default, container_disk_gb_default, gpu_type_default,
    )

    cli = RunPodClient(_os.environ["RUNPOD_API_KEY"])
    spec = {
        "gpu": gpu_type_default(), "cloud": cloud_type_default(),
        "disco_gb": container_disk_gb_default(),
    }
    try:
        pod = cli.create_pod(
            name=f"recognition-sonda-{uuid.uuid4().hex[:8]}",
            image="runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
            gpu_type_id=spec["gpu"], env={},
            docker_start_cmd=["/bin/bash", "-c", "true"],
            container_disk_gb=spec["disco_gb"], cloud_type=spec["cloud"],
        )
    except Exception as exc:  # noqa: BLE001
        return {**spec, "capacidade": False, "erro": str(exc)[:300]}
    # Mata NA HORA — sonda que esquece o pod aceso é pior que sonda nenhuma.
    cli.terminate_pod(str(pod["id"]))
    return {**spec, "capacidade": True, "pod_sondado": str(pod["id"]),
            "preco_usd_h": cli.get_gpu_price(spec["gpu"])}


def disparar(variante: str) -> dict[str, Any]:
    """Cria a linha do job e roda `dispatch_training` SÍNCRONO neste processo.

    Síncrono de propósito: o watchdog do `runpod_runner` vive dentro do dispatch
    e é ele quem garante o `terminate_pod` no `finally`. Enfileirar no worker do
    DEV colocaria o ciclo de vida do pod num processo que eu não observo — e o
    worker roda o `remote_train.py` da develop, não o desta branch.
    """
    _bootstrap()
    from app.infrastructure.queue.tasks.training import dispatch_training

    meta = VARIANTES[variante]
    repo = _repo()
    dsv = repo._execute_one(
        "SELECT id::text AS id, train_count, val_count FROM dataset_versions "
        "WHERE tenant_id = %s AND dataset_id = %s AND version = %s",
        (TENANT_RVB, DATASET_RVB, meta["versao"]),
    )
    if not dsv:
        raise SystemExit(f"variante {variante}: exporte antes (`exportar`).")

    nuvem = os.environ.get("RUNPOD_CLOUD_TYPE", "COMMUNITY").upper()
    proj = projetar_timeout_medido(preco_usd_h=PRECO_REAL_USD_H.get(nuvem, 0.74))
    proj["nuvem"] = nuvem
    if str(os.environ.get("RUNPOD_TIMEOUT_SECONDS_TRAIN", "")) == "":
        raise SystemExit(
            "RUNPOD_TIMEOUT_SECONDS_TRAIN não setado — o default 3600 MATA um "
            f"treino de 100 épocas. Projeção desta variante: {proj}"
        )

    # ⚠️ SEM `name`: `public.training_jobs` (onde os 40 jobs reais vivem, e
    # onde a esteira lê — `BaseRepository` não mexe em search_path, então o
    # default `"$user", public` resolve pra public) NÃO tem essa coluna. Quem
    # tem é a cópia LEGADA em `{tenant_schema}.training_jobs` (rvb/dev/admin,
    # 15 colunas, ZERO linhas). A variante viaja em `hyperparams.variante`.
    # Tabela sem qualificar DE PROPÓSITO: é assim que `dispatch_training`
    # resolve, e a linha tem de cair onde ele vai lê-la.
    job_id = str(uuid.uuid4())
    repo._execute_mutation_no_return(
        "INSERT INTO training_jobs (id, user_id, status, model_size, "
        " total_epochs, tenant_id, dataset_version_id, framework, base_model, "
        " hyperparams) VALUES (%s, %s, 'pending', 'rfdetr', %s, %s, %s, "
        " 'rfdetr', 'base', %s::jsonb)",
        (job_id, USER_RVB, EPOCAS_TETO, TENANT_RVB, dsv["id"],
         json.dumps({
             "experimento": "v2-tres-variantes", "variante": meta["versao"],
             "imgsz": IMGSZ, "gpu": os.environ.get("RUNPOD_GPU_TYPE", "4090"),
             "batch": BATCH, "batch_fixo": os.environ.get("BATCH_FIXO", ""),
             "timeout_s": int(os.environ["RUNPOD_TIMEOUT_SECONDS_TRAIN"]),
             "projecao": proj,
         })),
    )
    print(json.dumps({"disparando": job_id, "variante": variante,
                      "dataset_version_id": dsv["id"], "projecao": proj}), flush=True)

    r = dispatch_training.apply(
        args=[job_id, dsv["id"], "rfdetr", EPOCAS_TETO, IMGSZ, BATCH], throw=False
    )
    return {"job_id": job_id, "variante": variante, "estado": r.state,
            "resultado": str(r.result)[:800]}


# ═══════════════════════════════════════════════════════════════ status ══

def status() -> list[dict[str, Any]]:
    _bootstrap()
    repo = _repo()
    linhas = repo._execute(
        "SELECT tj.id::text AS id, tj.hyperparams->>'variante' AS variante, "
        "       tj.status, tj.current_epoch, "
        "       tj.total_epochs, tj.progress, tj.gpu_instance_ref, "
        "       tj.started_at, tj.completed_at, tj.metrics, tj.error_message, "
        "       tm.display_name, tm.id::text AS model_id "
        "FROM training_jobs tj LEFT JOIN trained_models tm ON tm.job_id = tj.id "
        "WHERE tj.hyperparams->>'experimento' = 'v2-tres-variantes' "
        "ORDER BY tj.created_at",
        (),
    )
    saida = []
    for r in linhas:
        m = r["metrics"] or {}
        if isinstance(m, str):
            m = json.loads(m)
        seg = None
        if r["started_at"]:
            fim = r["completed_at"] or datetime.now(timezone.utc).replace(tzinfo=None)
            seg = round((fim - r["started_at"]).total_seconds())
        ep = r["current_epoch"] or 0
        saida.append({
            "job": r["id"][:8], "variante": r["variante"], "status": r["status"],
            "epoca": f"{ep}/{r['total_epochs']}", "progresso": r["progress"],
            "pod": r["gpu_instance_ref"], "segundos": seg,
            "s_por_epoca": round(seg / ep) if seg and ep else None,
            "map": m.get("map") or m.get("map50") or m.get("mAP50"),
            "epochs_ran": m.get("epochs_ran"),
            "gpu_cost": m.get("gpu_cost"),
            "display_name": r["display_name"], "model_id": r["model_id"],
            "erro": (r["error_message"] or "")[:200] or None,
        })
    return saida


# ════════════════════════════════════════════════════════════ autoteste ══

def autoteste() -> None:
    """Check mínimo do que este arquivo decide sozinho: a conta do timeout.

    O resto (early-stop, nome, morte do pod) é da esteira e já tem teste lá.
    """
    for preco in (PRECO_REAL_USD_H["COMMUNITY"], PRECO_REAL_USD_H["SECURE"]):
        p = projetar_timeout(3560, 1175, preco_usd_h=preco)
        assert p["imagens"] == 4735
        # Volume 11% maior que a referência -> s/época 11% maior.
        assert 165 < p["s_por_epoca_bom"] < 180, p
        # Pior caso = bom × fator de loteria medido (3,31×), NUNCA a mediana.
        assert abs(p["s_por_epoca_pior"] / p["s_por_epoca_bom"] - FATOR_LOTERIA) < 0.01
        # A REGRA QUE NÃO PODE CEDER: mesmo depois de cortado pelo orçamento, o
        # timeout ainda cobre 100 épocas no PIOR s/época já medido. Foi o
        # contrário disso que matou o job 5894a860 na época 16 de 50.
        assert p["timeout_s"] > p["pior_caso_100_epocas_s"], p
        # E os 3 treinos têm de caber nos US$ 40 da rodada, ao preço REAL.
        assert teto_custo(p["timeout_s"], preco) * N_TREINOS <= TETO_RODADA_USD, p
        print(json.dumps({"preco": preco, "projecao": p,
                          "teto_usd_por_treino": teto_custo(p["timeout_s"], preco)}))
    # A projeção MEDIDA (a que B e C usam) tem de cobrir 100 épocas do ritmo real
    # e caber no orçamento aos 3 treinos, ao preço REAL do tier em uso.
    m = projetar_timeout_medido(preco_usd_h=PRECO_REAL_USD_H["SECURE"])
    assert m["timeout_s"] > m["cem_epocas_s"], m
    assert m["custo_estimado_usd"] * N_TREINOS <= TETO_RODADA_USD, m
    # E tem de ser MAIOR que a extrapolação achava necessário por época: medir
    # revelou 281 s/época contra os 171 projetados — 1,64× de erro para baixo.
    assert S_POR_EPOCA_MEDIDO > projetar_timeout(3560, 1175)["s_por_epoca_bom"]
    print(json.dumps({"medido": m}))
    # Em SECURE quem manda é o orçamento; em COMMUNITY, a cobertura.
    assert projetar_timeout(3560, 1175, 0.74)["restricao"] == "orcamento"
    assert projetar_timeout(3560, 1175, 0.34)["restricao"] == "cobertura"
    print("autoteste OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("comando", choices=[
        "autoteste", "plano", "exportar", "nomes", "sondar", "disparar", "status",
    ])
    ap.add_argument("--variante", choices=list(VARIANTES))
    ap.add_argument(
        "--somente-registro", action="store_true",
        help="exportar: refaz só a linha do banco, sem recopiar o R2",
    )
    args = ap.parse_args()

    if args.comando == "autoteste":
        autoteste()
    elif args.comando == "plano":
        saida = {"referencia": {"job": REF_JOB, "imagens": REF_IMAGENS,
                                "s_por_epoca": REF_S_POR_EPOCA},
                 "fator_loteria_medido": round(FATOR_LOTERIA, 2), "nuvens": {}}
        for nuvem, preco in PRECO_REAL_USD_H.items():
            p = projetar_timeout(3560, 1175, preco_usd_h=preco)
            saida["nuvens"][nuvem] = {
                "projecao": p,
                "teto_usd_por_treino": teto_custo(p["timeout_s"], preco),
                "teto_usd_3_treinos": round(teto_custo(p["timeout_s"], preco) * N_TREINOS, 2),
            }
        print(json.dumps(saida, indent=2))
    elif args.comando == "exportar":
        if not args.variante:
            raise SystemExit("--variante obrigatório")
        print(json.dumps(
            exportar(args.variante, somente_registro=args.somente_registro),
            indent=2, ensure_ascii=False,
        ))
    elif args.comando == "nomes":
        print(json.dumps(nomes(), indent=2, ensure_ascii=False))
    elif args.comando == "sondar":
        print(json.dumps(sondar(), indent=2, ensure_ascii=False))
    elif args.comando == "disparar":
        if not args.variante:
            raise SystemExit("--variante obrigatório")
        print(json.dumps(disparar(args.variante), indent=2, ensure_ascii=False))
    elif args.comando == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
