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
BATCH = 16          # `train_rfdetr` capa em 4 + grad_accum 4 (batch efetivo 16)
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


def projetar_timeout(train: int, val: int) -> dict[str, float]:
    """Timeout do pod POR MEDIÇÃO, com o pior caso histórico — nunca a mediana.

    Escala linear no volume (train+val, porque o RF-DETR valida a cada época),
    multiplicada pelo fator de loteria medido, mais o setup, vezes a margem.
    """
    imagens = train + val
    s_bom = REF_S_POR_EPOCA * imagens / REF_IMAGENS
    s_pior = s_bom * FATOR_LOTERIA
    bruto = s_pior * EPOCAS_TETO + SETUP_E_EXPORT_S
    return {
        "imagens": imagens,
        "s_por_epoca_bom": round(s_bom, 1),
        "s_por_epoca_pior": round(s_pior, 1),
        "timeout_s": int(bruto * MARGEM),
        "horas": round(bruto * MARGEM / 3600, 2),
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

    proj = projetar_timeout(dsv["train_count"], dsv["val_count"])
    if str(os.environ.get("RUNPOD_TIMEOUT_SECONDS_TRAIN", "")) == "":
        raise SystemExit(
            "RUNPOD_TIMEOUT_SECONDS_TRAIN não setado — o default 3600 MATA um "
            f"treino de 100 épocas. Projeção desta variante: {proj}"
        )

    job_id = str(uuid.uuid4())
    repo._execute_mutation_no_return(
        "INSERT INTO training_jobs (id, user_id, name, status, model_size, "
        " total_epochs, tenant_id, dataset_version_id, framework, base_model, "
        " hyperparams) VALUES (%s, %s, %s, 'pending', 'rfdetr', %s, %s, %s, "
        " 'rfdetr', 'base', %s::jsonb)",
        (job_id, USER_RVB, f"v2-{variante} {meta['resumo']}", EPOCAS_TETO,
         TENANT_RVB, dsv["id"],
         json.dumps({
             "experimento": "v2-tres-variantes", "variante": meta["versao"],
             "imgsz": IMGSZ, "gpu": os.environ.get("RUNPOD_GPU_TYPE", "4090"),
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
        "SELECT tj.id::text AS id, tj.name, tj.status, tj.current_epoch, "
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
            "job": r["id"][:8], "nome": r["name"], "status": r["status"],
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
    p = projetar_timeout(3560, 1175)
    assert p["imagens"] == 4735
    # Volume 11% maior que a referência -> s/época 11% maior.
    assert 165 < p["s_por_epoca_bom"] < 180, p
    # Pior caso = bom × fator de loteria medido (3,31×), NUNCA a mediana.
    assert abs(p["s_por_epoca_pior"] / p["s_por_epoca_bom"] - FATOR_LOTERIA) < 0.01
    # E tem de sobreviver ao pior caso de 100 épocas com folga.
    assert p["timeout_s"] > p["s_por_epoca_pior"] * EPOCAS_TETO, p
    # O teto de custo dos 3 treinos tem de caber nos US$ 40 da rodada.
    assert teto_custo(p["timeout_s"], 0.34) * 3 < 40, teto_custo(p["timeout_s"], 0.34)
    # Um timeout dimensionado pelo caso BOM seria menor que o pior caso real —
    # exatamente o erro que matou o job 5894a860 na época 16.
    assert p["s_por_epoca_bom"] * EPOCAS_TETO * MARGEM < p["s_por_epoca_pior"] * EPOCAS_TETO
    print(json.dumps({"projecao": p, "teto_usd_por_treino": teto_custo(p["timeout_s"], 0.34)}))
    print("autoteste OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("comando", choices=[
        "autoteste", "plano", "exportar", "nomes", "disparar", "status",
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
        p = projetar_timeout(3560, 1175)
        print(json.dumps({
            "referencia": {"job": REF_JOB, "imagens": REF_IMAGENS,
                           "s_por_epoca": REF_S_POR_EPOCA},
            "fator_loteria_medido": round(FATOR_LOTERIA, 2),
            "projecao": p,
            "teto_usd_por_treino_4090": teto_custo(p["timeout_s"], 0.34),
            "teto_usd_3_treinos": round(teto_custo(p["timeout_s"], 0.34) * 3, 2),
        }, indent=2))
    elif args.comando == "exportar":
        if not args.variante:
            raise SystemExit("--variante obrigatório")
        print(json.dumps(
            exportar(args.variante, somente_registro=args.somente_registro),
            indent=2, ensure_ascii=False,
        ))
    elif args.comando == "nomes":
        print(json.dumps(nomes(), indent=2, ensure_ascii=False))
    elif args.comando == "disparar":
        if not args.variante:
            raise SystemExit("--variante obrigatório")
        print(json.dumps(disparar(args.variante), indent=2, ensure_ascii=False))
    elif args.comando == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
