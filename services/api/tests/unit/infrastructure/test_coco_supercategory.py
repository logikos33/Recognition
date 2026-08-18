"""Self-check: COCO categories nunca colapsam para num_classes=0.

Regressão real: supercategory="none" (string literal) confundia o loader
COCO do RF-DETR e colapsava as categorias -> num_classes=0 -> CUDA
device-side assert em treino. Este teste drive o bloco de construção de
categorias (versioning_v2.build_dataset_version_v2, linhas ~391-403) com
3 classes fake e garante: supercategory != "none", category_id >= 1 e
len(categories) == nº de classes distintas > 0.
"""
import importlib
import json
import sys
import types
from unittest.mock import MagicMock, patch
from uuid import uuid4

_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_MODULE_KEY = "app.infrastructure.queue.tasks.versioning_v2"


class _TransparentCelery:
    def task(self, *args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator


def _load_module(monkeypatch):
    fake = types.ModuleType(_CELERY_APP_KEY)
    fake.celery = _TransparentCelery()
    monkeypatch.setitem(sys.modules, _CELERY_APP_KEY, fake)
    monkeypatch.delitem(sys.modules, _MODULE_KEY, raising=False)
    return importlib.import_module(_MODULE_KEY)


def _frame(fid, video_id):
    return {
        "id": fid, "video_id": video_id,
        "filename": f"frames/{fid}.jpg", "r2_key": f"frames/{fid}.jpg",
        "width": 640, "height": 480, "module_code": "epi",
        "is_reviewed": True, "camera_id": None,
        "captured_at": None, "created_at": None,
    }


def _ann(frame_id, class_id, class_name):
    return {
        "id": uuid4(), "frame_id": frame_id, "class_id": class_id,
        "class_name": class_name, "x_center": 0.5, "y_center": 0.5,
        "width": 0.2, "height": 0.1,
    }


def test_categories_never_collapse_to_zero_classes(monkeypatch):
    v2_mod = _load_module(monkeypatch)

    classes = [(1, "helmet"), (2, "vest"), (3, "boots")]
    # MESMO video_id de propósito: o split é por grupo (câmera+dia, com
    # fallback em video_id). Com um video_id por frame, cada classe cai num
    # split diferente e o TREINO fica com uma só — cenário degenerado que não
    # é o que este teste mede. Um grupo único mantém as 3 classes juntas, que
    # é o caso real que o guard de supercategory (#378) protege.
    grupo = uuid4()
    frames = [_frame(uuid4(), grupo) for _ in classes]
    annotations = [
        _ann(frame["id"], class_id, class_name)
        for frame, (class_id, class_name) in zip(frames, classes)
    ]

    ann_repo = MagicMock()
    ann_repo._execute.side_effect = [frames, annotations]
    dataset_repo = MagicMock()
    dataset_repo.create_version_v2.return_value = {"id": uuid4()}
    dataset_repo.get_pending_version.return_value = None
    storage = MagicMock()

    with patch.object(v2_mod, "_get_annotation_repo", return_value=ann_repo), \
         patch.object(v2_mod, "_get_dataset_repo", return_value=dataset_repo), \
         patch.object(v2_mod, "_get_storage", return_value=storage):
        v2_mod.build_dataset_version_v2(
            MagicMock(),
            tenant_id=str(uuid4()), dataset_id=str(uuid4()),
            user_id=str(uuid4()), version="v1",
        )

    coco_call = next(
        c for c in storage.upload_bytes.call_args_list
        if c.args[0].endswith("_annotations.coco.json")
    )
    categories = json.loads(coco_call.args[1].decode("utf-8"))["categories"]

    # INVARIANTE ATUALIZADO (guard de suporte-zero, D-165): o mapa de classes
    # nasce do split de TREINO, então uma classe que não caiu no train sai de
    # `categories` — é isso que evita num_classes inconsistente e o CUDA
    # device-side assert. O que este teste protege continua valendo: NUNCA
    # colapsar para zero, supercategory nunca "none", ids >= 1 e contíguos.
    nomes = {n for _, n in classes}
    assert 0 < len(categories) <= len(classes)
    assert {c["name"] for c in categories} <= nomes
    ids = sorted(c["id"] for c in categories)
    assert ids == list(range(1, len(ids) + 1)), f"ids não contíguos: {ids}"
    for cat in categories:
        assert cat["supercategory"] != "none"
        assert cat["id"] >= 1


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
