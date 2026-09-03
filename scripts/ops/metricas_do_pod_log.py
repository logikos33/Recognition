#!/usr/bin/env python3
"""metricas_do_pod_log.py — resgata a métrica que ficou só no log do pod.

POR QUE ISTO EXISTE
────────────────────────────────────────────────────────────────────────────────
`remote_train._collect_metrics` lia o dict de `on_fit_epoch_end`, e o RF-DETR
1.5.2 não põe mAP lá — ele IMPRIME. Resultado: TODO modelo deste sistema nasceu
com `map50=0/precision=0/recall=0`, e o ranking campeão×desafiante comparou
zeros com zeros. O conserto para os PRÓXIMOS está em `_metricas_do_log()`; este
script é para os que JÁ rodaram e já foram pagos — o job 04508616 custou
US$ 1,71 e seu mAP 0,4386 existia somente no `pod.log` do R2.

⛔ MÉTRICA EXTRAÍDA DE LOG NÃO É MÉTRICA REPORTADA PELO CALLBACK.
Toda linha que este script escreve leva `metrics.metric_source =
"pod_log_posthoc"` mais a chave do log de onde veio. Sem essa marca, daqui a um
mês ninguém distingue o número que o pod reportou do número que alguém garimpou
— e um censo futuro repetiria o erro que este script está consertando.

    DATABASE_URL=... R2_*=... python3 scripts/ops/metricas_do_pod_log.py <job_id> [--gravar]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "services" / "api"))
sys.path.insert(0, str(_RAIZ / "training" / "vast"))

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"


def extrair(texto: str) -> dict:
    """Métricas DA ÉPOCA QUE VIROU O ARTEFATO — não as da última época.

    Padrões importados de `remote_train`, nunca recopiados: se o formato do log
    mudar, os dois mudam juntos.

    A sutileza que quase passou: varrer o log inteiro e ficar com a ÚLTIMA
    ocorrência devolve a avaliação FINAL, que no job 04508616 dava map=0,277 —
    enquanto o checkpoint entregue (`checkpoint_best_total`) é o da época 8, com
    EMA 0,4386. Gravar 0,277 seria descrever um artefato que não é o servido.
    Então: acha o `Best` máximo, localiza onde o run registrou tê-lo atingido, e
    lê o bloco COCO IMEDIATAMENTE ANTERIOR — a avaliação daquela época.
    """
    import remote_train  # noqa: PLC0415

    metrics: dict = {}
    ema = remote_train._RE_EMA.findall(texto)
    if not ema:
        # Sem sinal de early-stop, o melhor esforço é a última avaliação — e o
        # chamador fica sabendo por `metric_epoch_anchor` ausente.
        for iou, valor in remote_train._RE_AP.findall(texto):
            metrics["map" if iou == "0.50:0.95" else "map50"] = float(valor)
        return metrics

    melhor = max(float(b) for _a, b in ema)
    metrics["map_ema_best"] = melhor
    marco = texto.rfind(f"mAP improved to {melhor}")
    if marco > 0:
        anteriores = remote_train._RE_AP.findall(texto[:marco])
        for iou, valor in anteriores[-12:]:  # o bloco COCO daquela época
            metrics["map" if iou == "0.50:0.95" else "map50"] = float(valor)
        metrics["metric_epoch_anchor"] = "bloco COCO anterior ao melhor EMA"
    return metrics


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    job_id = sys.argv[1]
    gravar = "--gravar" in sys.argv

    from app.infrastructure.database.connection import DatabasePool, get_database_url
    from app.infrastructure.database.repositories.annotation_repository import (
        AnnotationRepository,
    )
    from app.infrastructure.storage.local_storage import get_storage

    if DatabasePool.get_instance() is None:
        DatabasePool.initialize(get_database_url())
    repo = AnnotationRepository(DatabasePool.get_instance())

    texto = get_storage(TENANT_RVB).download_bytes(f"jobs/{job_id}/pod.log").decode(
        "utf-8", "replace"
    )
    m = extrair(texto)
    if not m:
        raise SystemExit(f"job {job_id}: nenhuma métrica no pod.log — nada gravado.")

    modelo = repo._execute_one(
        "SELECT id::text AS id, display_name, map50 FROM trained_models "
        "WHERE job_id = %s", (job_id,),
    )
    saida = {"job": job_id, "extraido": m, "modelo": modelo, "gravado": False}
    if gravar and modelo:
        marca = {**m, "metric_source": "pod_log_posthoc",
                 "metric_source_key": f"jobs/{job_id}/pod.log"}
        repo._execute_mutation_no_return(
            "UPDATE trained_models SET map50 = %s, "
            "metrics = COALESCE(metrics,'{}'::jsonb) || %s::jsonb WHERE id = %s",
            (m.get("map50", 0.0), json.dumps(marca), modelo["id"]),
        )
        # O job também: é dele que sai o relatório de treino.
        repo._execute_mutation_no_return(
            "UPDATE training_jobs SET metrics = COALESCE(metrics,'{}'::jsonb) || %s::jsonb "
            "WHERE id = %s", (json.dumps(marca), job_id),
        )
        saida["gravado"] = True
    print(json.dumps(saida, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
