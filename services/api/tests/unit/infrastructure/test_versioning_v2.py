"""Tests: versioning_v2.py — build oficial de dataset_version COCO (WS-A3).

Cobertura:
  - snapshot: LEFT JOIN training_videos + reviewed primeiro (ajuste #4);
  - split por grupo: video_id ou 'frame:{id}' (frames soltos entram);
  - conversão YOLO normalizado → COCO absoluto via width/height;
  - fallback de dimensões: baixa imagem do R2 e lê com PIL (ajuste #11);
  - INSERT via DatasetRepository.create_version_v2 com status 'building'
    e transição para 'ready' com coco_r2_key (prefixo R2);
  - erro pós-INSERT marca a versão como 'error' antes do retry.

celery é stubado com um app transparente escopado (mesmo padrão de
test_versioning_dataset_versions.py) — sem poluição de sys.modules.
"""
import importlib
import json
import sys
import types
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_MODULE_KEY = "app.infrastructure.queue.tasks.versioning_v2"

TENANT_ID = str(uuid4())
DATASET_ID = str(uuid4())
USER_ID = str(uuid4())
DV_ID = uuid4()


class _TransparentCelery:
    def task(self, *args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator


@pytest.fixture
def v2_mod(monkeypatch):
    """Importa versioning_v2 fresh sob celery transparente, sem vazar estado."""
    fake = types.ModuleType(_CELERY_APP_KEY)
    fake.celery = _TransparentCelery()
    monkeypatch.setitem(sys.modules, _CELERY_APP_KEY, fake)
    monkeypatch.delitem(sys.modules, _MODULE_KEY, raising=False)
    mod = importlib.import_module(_MODULE_KEY)
    yield mod
    sys.modules.pop(_MODULE_KEY, None)


def _make_frame(video_id, frame_num, width=640, height=480, reviewed=True,
                 camera_id=None, captured_at=None, created_at=None):
    fid = uuid4()
    key = f"frames/{USER_ID}/{video_id or 'solto'}/frame_{frame_num:04d}.jpg"
    return {
        "id": fid,
        "video_id": video_id,
        "filename": key,
        "r2_key": key,
        "frame_number": frame_num,
        "width": width,
        "height": height,
        "module_code": "epi",
        "is_reviewed": reviewed,
        "camera_id": camera_id,
        "captured_at": captured_at,
        "created_at": created_at,
    }


def _make_ann(frame_id, class_id=1, class_name="helmet",
              cx=0.5, cy=0.5, w=0.2, h=0.1):
    return {
        "id": uuid4(),
        "frame_id": frame_id,
        "class_id": class_id,
        "class_name": class_name,
        "x_center": cx,
        "y_center": cy,
        "width": w,
        "height": h,
    }


def _make_ann_with_provenance(frame_id, source, reviewed_by, **kwargs):
    """Como _make_ann, mas com source/reviewed_by explícitos (migration
    095) — usado pelos testes do gate de procedência D-39."""
    ann = _make_ann(frame_id, **kwargs)
    ann["source"] = source
    ann["reviewed_by"] = reviewed_by
    return ann


def _run(v2_mod, frames, annotations, storage=None, dataset_repo=None,
         pending_version=None, **kwargs):
    ann_repo = MagicMock()
    ann_repo._execute.side_effect = [frames, annotations]

    dataset_repo = dataset_repo or MagicMock()
    dataset_repo.create_version_v2.return_value = {"id": DV_ID}
    # Default: nenhuma versão 'building'/'error' pré-existente — caminho de
    # criação (comportamento pré-existente). pending_version simula um retry.
    dataset_repo.get_pending_version.return_value = pending_version

    storage = storage or MagicMock()
    mock_self = MagicMock()
    mock_self.retry.side_effect = RuntimeError("retry-called")

    with patch.object(v2_mod, "_get_annotation_repo", return_value=ann_repo), \
         patch.object(v2_mod, "_get_dataset_repo", return_value=dataset_repo), \
         patch.object(v2_mod, "_get_storage", return_value=storage):
        result = v2_mod.build_dataset_version_v2(
            mock_self,
            tenant_id=TENANT_ID,
            dataset_id=DATASET_ID,
            user_id=USER_ID,
            version=kwargs.pop("version", "v1"),
            **kwargs,
        )
    return result, ann_repo, dataset_repo, storage


class TestSnapshotQuery:
    """Ajuste #4: LEFT JOIN + reviewed primeiro + escopo tenant/módulo."""

    def test_left_join_and_reviewed_first(self, v2_mod):
        frames = [_make_frame(uuid4(), i) for i in range(5)]
        anns = [_make_ann(frames[0]["id"])]
        _, ann_repo, _, _ = _run(v2_mod, frames, anns)

        query = ann_repo._execute.call_args_list[0].args[0]
        assert "LEFT JOIN training_videos" in query
        assert "validated_at IS NOT NULL) DESC" in query
        params = ann_repo._execute.call_args_list[0].args[1]
        assert params == (TENANT_ID, "epi")

    def test_no_frames_raises_value_error(self, v2_mod):
        with pytest.raises(ValueError, match="Nenhum frame rotulado"):
            _run(v2_mod, [], [])


class TestProvenanceGate:
    """D-39 (docs/REGISTRO_DE_DECISOES.md): dataset de treino só recebe
    anotação humana direta ou pré-anotação de IA aprovada por humano
    (migration 095 — frame_annotations.source/reviewed_by). Espelha o
    accept_pre_annotations do annotation_repository.py, que grava
    source='pre_annotation' + reviewed_by=quem aceitou a sugestão."""

    def test_manual_annotation_enters_dataset(self, v2_mod):
        frames = [_make_frame(uuid4(), 0)]
        ann = _make_ann_with_provenance(
            frames[0]["id"], source="manual", reviewed_by=None
        )
        result, _, _, _ = _run(v2_mod, frames, [ann])
        assert result["class_distribution"] == {"helmet": 1}

    def test_unreviewed_pre_annotation_is_excluded(self, v2_mod):
        frames = [_make_frame(uuid4(), 0)]
        ann = _make_ann_with_provenance(
            frames[0]["id"], source="pre_annotation", reviewed_by=None
        )
        result, _, _, _ = _run(v2_mod, frames, [ann])
        assert result["class_distribution"] == {}

    def test_reviewed_pre_annotation_enters_dataset(self, v2_mod):
        frames = [_make_frame(uuid4(), 0)]
        ann = _make_ann_with_provenance(
            frames[0]["id"], source="pre_annotation", reviewed_by=str(uuid4())
        )
        result, _, _, _ = _run(v2_mod, frames, [ann])
        assert result["class_distribution"] == {"helmet": 1}

    def test_legacy_annotation_without_source_key_still_enters(self, v2_mod):
        """Anotações gravadas antes da migration 095 (dict sem a chave
        'source', equivalente ao default histórico da coluna) continuam
        entrando no dataset — nada some do que já existia."""
        frames = [_make_frame(uuid4(), 0)]
        ann = _make_ann(frames[0]["id"])  # sem source/reviewed_by
        result, _, _, _ = _run(v2_mod, frames, [ann])
        assert result["class_distribution"] == {"helmet": 1}


class TestSplitGroups:
    """Split por grupo: video_id ou 'frame:{id}' — sem leakage."""

    def test_null_video_frames_are_included(self, v2_mod):
        frames = [_make_frame(None, i) for i in range(6)]
        anns = [_make_ann(f["id"]) for f in frames]
        result, _, _, _ = _run(v2_mod, frames, anns)

        total = (
            result["train_count"] + result["val_count"] + result["test_count"]
        )
        assert total == 6
        assert result["total_frames"] == 6

    def test_same_video_frames_stay_in_same_split(self, v2_mod):
        vid_a, vid_b, vid_c = uuid4(), uuid4(), uuid4()
        frames = (
            [_make_frame(vid_a, i) for i in range(4)]
            + [_make_frame(vid_b, i) for i in range(4)]
            + [_make_frame(vid_c, i) for i in range(4)]
        )
        anns = [_make_ann(f["id"]) for f in frames]

        groups = {}
        for frame in frames:
            groups.setdefault(v2_mod._group_key(frame), []).append(frame)
        # 3 grupos → 1 grupo por split (sem acionar fallback de val/test,
        # que realoca frames individuais como na task legada)
        splits = v2_mod._split_by_group(
            frames, {"train": 0.4, "val": 0.4, "test": 0.2}
        )
        for split_frames in splits.values():
            vids = {str(f["video_id"]) for f in split_frames}
            for vid in vids:
                # todos os frames do vídeo estão neste split
                assert all(
                    any(str(g["id"]) == str(f["id"]) for g in split_frames)
                    for f in groups[vid]
                )
        # sanity: nada perdido
        result, _, _, _ = _run(v2_mod, frames, anns)
        assert result["total_frames"] == 12


class TestGroupKeyCases:
    """_group_key: os 3 casos de prioridade (video_id > camera+dia >
    'frame:{id}') — split por câmera/dia para frames soltos de NVR."""

    def test_video_id_wins_over_camera(self, v2_mod):
        vid = uuid4()
        cam = uuid4()
        frame = _make_frame(
            vid, 1, camera_id=cam,
            captured_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        )
        assert v2_mod._group_key(frame) == str(vid)

    def test_camera_plus_captured_at_day(self, v2_mod):
        cam = uuid4()
        frame = _make_frame(
            None, 1, camera_id=cam,
            captured_at=datetime(2026, 8, 7, 23, 59, tzinfo=timezone.utc),
        )
        assert v2_mod._group_key(frame) == f"cam:{cam}:2026-08-07"

    def test_camera_plus_created_at_fallback_when_no_captured_at(self, v2_mod):
        cam = uuid4()
        frame = _make_frame(
            None, 1, camera_id=cam,
            captured_at=None,
            created_at=datetime(2026, 8, 10, 8, 0),
        )
        assert v2_mod._group_key(frame) == f"cam:{cam}:2026-08-10"

    def test_no_video_no_camera_falls_back_to_frame_id(self, v2_mod):
        frame = _make_frame(None, 1, camera_id=None, captured_at=None, created_at=None)
        assert v2_mod._group_key(frame) == f"frame:{frame['id']}"

    def test_camera_without_resolvable_day_falls_back_to_frame_id(self, v2_mod):
        cam = uuid4()
        frame = _make_frame(None, 1, camera_id=cam, captured_at=None, created_at=None)
        assert v2_mod._group_key(frame) == f"frame:{frame['id']}"

    def test_fallback_to_frame_id_logs_warning(self, v2_mod, caplog):
        import logging
        frame = _make_frame(None, 1, camera_id=None, captured_at=None, created_at=None)
        with caplog.at_level(logging.WARNING):
            v2_mod._group_key(frame)
        assert any(
            "split_group_key_fallback_frame_id" in rec.message
            for rec in caplog.records
        )

    def test_video_id_or_camera_day_never_log_warning(self, v2_mod, caplog):
        import logging
        cam = uuid4()
        frame = _make_frame(
            None, 1, camera_id=cam,
            captured_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        )
        with caplog.at_level(logging.WARNING):
            v2_mod._group_key(frame)
        assert not caplog.records


class TestSameCameraDayNeverSplits:
    """Frames da mesma câmera no mesmo dia nunca se separam entre splits —
    o mesmo teste de não-leakage de TestSplitGroups.test_same_video_frames_
    stay_in_same_split, mas para o caso de frames soltos de NVR (sem
    video_id) agrupados por câmera+dia."""

    def test_same_camera_day_frames_stay_together(self, v2_mod):
        cam_a, cam_b, cam_c = uuid4(), uuid4(), uuid4()
        day = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
        frames = (
            [_make_frame(None, i, camera_id=cam_a, captured_at=day) for i in range(4)]
            + [_make_frame(None, i, camera_id=cam_b, captured_at=day) for i in range(4)]
            + [_make_frame(None, i, camera_id=cam_c, captured_at=day) for i in range(4)]
        )
        anns = [_make_ann(f["id"]) for f in frames]

        groups: dict[str, list] = {}
        for frame in frames:
            groups.setdefault(v2_mod._group_key(frame), []).append(frame)
        assert len(groups) == 3  # 1 grupo por câmera (mesmo dia p/ todas)

        splits = v2_mod._split_by_group(
            frames, {"train": 0.4, "val": 0.4, "test": 0.2}
        )
        for split_frames in splits.values():
            split_ids = {str(f["id"]) for f in split_frames}
            groups_touched = {
                key for key, group_frames in groups.items()
                if split_ids & {str(f["id"]) for f in group_frames}
            }
            for key in groups_touched:
                # todos os frames do grupo (câmera+dia) estão neste split
                group_ids = {str(f["id"]) for f in groups[key]}
                assert group_ids <= split_ids

        result, _, _, _ = _run(v2_mod, frames, anns)
        assert result["total_frames"] == 12

    def test_different_days_same_camera_are_different_groups(self, v2_mod):
        cam = uuid4()
        day1 = datetime(2026, 8, 7, tzinfo=timezone.utc)
        day2 = datetime(2026, 8, 8, tzinfo=timezone.utc)
        frame1 = _make_frame(None, 1, camera_id=cam, captured_at=day1)
        frame2 = _make_frame(None, 2, camera_id=cam, captured_at=day2)
        assert v2_mod._group_key(frame1) != v2_mod._group_key(frame2)


class TestCocoConversion:
    """YOLO cx/cy/w/h normalizado → COCO absoluto [x, y, w, h]."""

    def test_bbox_math(self, v2_mod):
        ann = _make_ann(uuid4(), cx=0.5, cy=0.5, w=0.2, h=0.1)
        assert v2_mod._yolo_to_coco_bbox(ann, 100, 200) == [40.0, 90.0, 20.0, 20.0]

    def test_uploaded_coco_json_is_valid(self, v2_mod):
        frames = [_make_frame(uuid4(), i, width=100, height=200) for i in range(5)]
        anns = [
            _make_ann(frames[0]["id"], class_id=7, class_name="vest",
                      cx=0.5, cy=0.5, w=0.2, h=0.1)
        ]
        _, _, _, storage = _run(v2_mod, frames, anns)

        coco_uploads = {
            call.args[0]: call.args[1]
            for call in storage.upload_bytes.call_args_list
            if call.args[0].endswith("_annotations.coco.json")
        }
        assert len(coco_uploads) == 3  # train/val/test sempre gerados

        merged_anns = []
        for payload in coco_uploads.values():
            doc = json.loads(payload.decode("utf-8"))
            # Formato Roboflow: placeholder id 0 (supercategory "none") +
            # classe real id 1 com supercategory != "none" (senão RF-DETR
            # conta 0 classes — achado TREINO 1).
            assert doc["categories"] == [
                {"id": 0, "name": "recognition", "supercategory": "none"},
                {"id": 1, "name": "vest", "supercategory": "recognition"},
            ]
            merged_anns.extend(doc["annotations"])

        assert len(merged_anns) == 1
        assert merged_anns[0]["bbox"] == [40.0, 90.0, 20.0, 20.0]
        assert merged_anns[0]["area"] == 400.0
        assert merged_anns[0]["category_id"] == 1
        assert merged_anns[0]["iscrowd"] == 0

    def test_upload_prefix_uses_dataset_exports(self, v2_mod):
        frames = [_make_frame(uuid4(), i) for i in range(5)]
        anns = [_make_ann(frames[0]["id"])]
        _, _, _, storage = _run(v2_mod, frames, anns)

        expected_base = f"dataset-exports/{TENANT_ID}/{DATASET_ID}/v1"
        for call in storage.upload_bytes.call_args_list:
            assert call.args[0].startswith(expected_base)
        for call in storage.copy_object.call_args_list:
            assert call.args[1].startswith(expected_base)


class TestDimensionFallback:
    """Ajuste #11: frames sem width/height leem dimensões do R2 com PIL."""

    def _png_bytes(self, width, height):
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (width, height)).save(buf, format="PNG")
        return buf.getvalue()

    def test_dimensions_read_from_r2_image(self, v2_mod):
        frames = [_make_frame(uuid4(), i) for i in range(4)]
        frames.append(_make_frame(None, 99, width=None, height=None))
        anns = [_make_ann(frames[-1]["id"])]

        storage = MagicMock()
        storage.download_bytes.return_value = self._png_bytes(320, 240)
        result, _, _, storage = _run(v2_mod, frames, anns, storage=storage)

        storage.download_bytes.assert_called_once_with(frames[-1]["r2_key"])
        assert result["total_frames"] == 5
        assert frames[-1]["width"] == 320
        assert frames[-1]["height"] == 240

    def test_unresolvable_frames_are_dropped(self, v2_mod):
        frames = [_make_frame(uuid4(), i) for i in range(4)]
        frames.append(_make_frame(None, 99, width=None, height=None))
        anns = []

        storage = MagicMock()
        storage.download_bytes.side_effect = OSError("R2 offline")
        result, _, _, _ = _run(v2_mod, frames, anns, storage=storage)

        assert result["total_frames"] == 4
        assert len(result["dimension_errors"]) == 1


class TestLineageInsert:
    """INSERT create_version_v2 (building) → update_version_status (ready)."""

    def test_insert_building_then_ready_with_coco_key(self, v2_mod):
        frames = [_make_frame(uuid4(), i) for i in range(5)]
        anns = [_make_ann(frames[0]["id"])]
        result, _, dataset_repo, _ = _run(
            v2_mod, frames, anns,
            split={"train": 0.7, "val": 0.2, "test": 0.1},
            augmentations={"flip": True},
        )

        payload = dataset_repo.create_version_v2.call_args.args[0]
        assert payload["status"] == "building"
        assert payload["tenant_id"] == TENANT_ID
        assert payload["dataset_id"] == DATASET_ID
        assert payload["module_code"] == "epi"
        assert payload["export_format"] == "coco"
        assert payload["split"] == {"train": 0.7, "val": 0.2, "test": 0.1}
        assert payload["augmentations"] == {"flip": True}
        assert payload["class_distribution"] == {"helmet": 1}
        assert payload["frame_count"] == 5

        args = dataset_repo.update_version_status.call_args
        assert args.args[2] == "ready"
        assert args.kwargs["coco_r2_key"] == (
            f"dataset-exports/{TENANT_ID}/{DATASET_ID}/v1"
        )
        assert result["dataset_version_id"] == str(DV_ID)
        assert result["status"] == "ready"

    def test_failure_after_insert_marks_error_and_retries(self, v2_mod):
        frames = [_make_frame(uuid4(), i) for i in range(5)]
        anns = [_make_ann(frames[0]["id"])]

        storage = MagicMock()
        storage.upload_bytes.side_effect = OSError("R2 write failed")

        with pytest.raises(RuntimeError, match="retry-called"):
            _run(v2_mod, frames, anns, storage=storage)

        # o repo usado dentro de _run é criado lá; refaz com repo próprio
        dataset_repo = MagicMock()
        dataset_repo.create_version_v2.return_value = {"id": DV_ID}
        with pytest.raises(RuntimeError, match="retry-called"):
            _run(
                v2_mod, frames.copy(), anns, storage=storage,
                dataset_repo=dataset_repo,
            )
        status_call = dataset_repo.update_version_status.call_args
        assert status_call.args[2] == "error"


class TestRetryReusesExistingVersion:
    """Achado da revisão adversarial: sem UNIQUE(dataset_id, version), um
    retry do Celery após falha transiente (ex.: upload R2) reINSERTava
    dataset_versions com o MESMO label — a row da 1ª tentativa ficava
    órfã em 'error' e uma segunda nascia a cada nova tentativa. Fix:
    reaproveitar a row via get_pending_version (status building/error)."""

    def test_reuses_pending_row_instead_of_inserting_new(self, v2_mod):
        frames = [_make_frame(uuid4(), i) for i in range(3)]
        anns = [_make_ann(frames[0]["id"])]

        # Simula uma tentativa anterior que falhou após o INSERT — row
        # existente em status 'error' com o mesmo dataset_id+version.
        existing_row = {"id": DV_ID, "status": "error"}
        dataset_repo = MagicMock()
        dataset_repo.get_pending_version.return_value = existing_row
        dataset_repo.update_version_status.return_value = existing_row

        result, _, dataset_repo, _ = _run(
            v2_mod, frames, anns, dataset_repo=dataset_repo,
            pending_version=existing_row,
        )

        # NÃO cria uma segunda row — reaproveita a existente.
        dataset_repo.create_version_v2.assert_not_called()
        # Reseta 'error' → 'building' antes de reprocessar.
        building_calls = [
            c for c in dataset_repo.update_version_status.call_args_list
            if c.args[2] == "building"
        ]
        assert building_calls, "deveria resetar a row existente para 'building'"
        assert result["dataset_version_id"] == str(DV_ID)
        assert result["status"] == "ready"

    def test_no_pending_version_still_inserts_new(self, v2_mod):
        """Sanidade: sem retry em andamento, comportamento de criação
        permanece intacto (create_version_v2 chamado normalmente)."""
        frames = [_make_frame(uuid4(), i) for i in range(3)]
        anns = [_make_ann(frames[0]["id"])]

        result, _, dataset_repo, _ = _run(v2_mod, frames, anns)

        dataset_repo.create_version_v2.assert_called_once()
        assert result["dataset_version_id"] == str(DV_ID)


class TestBuildCategoriesDedup:
    """_build_categories: a mesma classe física salva com dois class_id
    (catálogo <OFFSET e namespaced >=OFFSET) vira UMA categoria COCO
    (achado TREINO 1 — antes rachava 'mascara'/'Protetor auditivo' em duas)."""

    def test_dup_encodings_collapse_to_one_category(self, v2_mod):
        # Caso real RVB: 'mascara' como 6 e 100006; 'Protetor auditivo' como
        # 4 e 100004; 'Botas' só como 100010.
        anns = [
            {"class_id": 6, "class_name": "mascara"},
            {"class_id": 100006, "class_name": "mascara"},
            {"class_id": 4, "class_name": "Protetor auditivo"},
            {"class_id": 100004, "class_name": "Protetor auditivo"},
            {"class_id": 100010, "class_name": "Botas"},
        ]
        categories, cat_id_by_class = v2_mod._build_categories(anns)

        real = [c for c in categories if c["supercategory"] != "none"]
        names = [c["name"] for c in real]
        assert names.count("mascara") == 1
        assert names.count("Protetor auditivo") == 1
        assert len(real) == 3
        # Ambos os encodings apontam para a MESMA category_id.
        assert cat_id_by_class[6] == cat_id_by_class[100006]
        assert cat_id_by_class[4] == cat_id_by_class[100004]
        # category_id distintos entre classes distintas.
        assert cat_id_by_class[6] != cat_id_by_class[4] != cat_id_by_class[100010]
        # Classes reais em 1..N; nenhuma anotação referencia o placeholder id 0.
        assert sorted(c["id"] for c in real) == [1, 2, 3]
        assert min(cat_id_by_class.values()) >= 1

    def test_roboflow_placeholder_category_present(self, v2_mod):
        # RF-DETR (_load_classes) descarta supercategory=="none"; precisa do
        # placeholder id 0 + classes reais com supercategory != "none", senão
        # conta 0 classes -> CUDA device-side assert (achado TREINO 1).
        cats, _ = v2_mod._build_categories([{"class_id": 6, "class_name": "mascara"}])
        placeholder = [c for c in cats if c["supercategory"] == "none"]
        assert len(placeholder) == 1 and placeholder[0]["id"] == 0
        real = [c for c in cats if c["supercategory"] != "none"]
        assert real and all(c["supercategory"] != "none" for c in real)

    def test_canonical_class_id(self, v2_mod):
        assert v2_mod._canonical_class_id(6) == 6
        assert v2_mod._canonical_class_id(100006) == 6
        assert v2_mod._canonical_class_id(100000) == 0
