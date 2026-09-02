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
        """A proposta sem revisão não entra — e o frame dela também não.

        Antes o frame sobrevivia com zero caixas, o que ensina o detector a
        NÃO ver o que a IA acha que está lá: nunca houve decisão humana
        dizendo "aqui não tem nada". Segundo frame com anotação humana só
        para o export não colapsar a zero.
        """
        frames = [_make_frame(uuid4(), 0), _make_frame(uuid4(), 1)]
        sem_revisao = _make_ann_with_provenance(
            frames[0]["id"], source="pre_annotation", reviewed_by=None
        )
        humana = _make_ann_with_provenance(
            frames[1]["id"], source="manual", reviewed_by=None
        )
        result, _, _, _ = _run(v2_mod, frames, [sem_revisao, humana])

        assert result["class_distribution"] == {"helmet": 1}
        # Dos dois frames entregues, só o que tem caixa humana sobrevive.
        assert result["total_frames"] == 1

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
            # A ÂNCORA `id:0` vem primeiro (raiz do COCO, supercategory "none"),
            # e as classes reais penduram nela. Sem a âncora o RF-DETR desloca
            # todos os índices de classe em UM, e serve o rótulo errado sem
            # erro nenhum.
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


class TestMembresiaDoSplitCongelada:
    """O build grava QUEM caiu em cada split (migration 131).

    `dataset_versions.split` só guarda a proporção. Sem esta gravação o
    holdout do A/B é irrecuperável — o build 42023066 sorteou com
    `random.shuffle` sem semente e nem re-executar o código recupera.
    """

    def test_grava_membresia_com_os_ids_exatos_de_cada_split(self, v2_mod):
        frames = [_make_frame(uuid4(), i) for i in range(9)]
        result, _, dataset_repo, _ = _run(v2_mod, frames, [_make_ann(frames[0]["id"])])

        membresia = dataset_repo.update_split_membership.call_args.args[2]
        assert set(membresia) == {"train", "val", "test"}

        # Os ids gravados são exatamente os frames do export — nem um a mais,
        # nem um a menos, e nenhum em dois splits.
        gravados = [i for nome in membresia for i in membresia[nome]]
        assert sorted(gravados) == sorted(str(f["id"]) for f in frames)
        assert len(gravados) == len(set(gravados))

        # E as contagens gravadas na row batem com o tamanho das listas.
        for nome in ("train", "val", "test"):
            assert len(membresia[nome]) == result[f"{nome}_count"]

    def test_membresia_gravada_antes_do_ready(self, v2_mod):
        """Versão 'ready' é imutável — se a membresia entrasse depois, o
        artefato ficaria pronto sem a prova que o define."""
        ordem = []
        dataset_repo = MagicMock()
        dataset_repo.create_version_v2.return_value = {"id": DV_ID}
        dataset_repo.get_pending_version.return_value = None
        dataset_repo.update_split_membership.side_effect = (
            lambda *a, **k: ordem.append("membresia")
        )
        dataset_repo.update_version_status.side_effect = (
            lambda *a, **k: ordem.append(f"status:{a[2]}")
        )
        frames = [_make_frame(uuid4(), i) for i in range(5)]
        _run(v2_mod, frames, [_make_ann(frames[0]["id"])], dataset_repo=dataset_repo)

        assert ordem.index("membresia") < ordem.index("status:ready")


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


class TestClasseSemSuporteNoTreino:
    """Classe presente só em val/test entrava em `categories` com ZERO
    instâncias no train, e o RF-DETR quebrava na época 0 (família do
    incidente de supercategory, #378). Medido: `Capacete`, 1 box no mundo,
    caiu no test, treino falhou. Ver D-165."""

    def _coco(self, cat_map, frames, anns):
        from app.infrastructure.queue.tasks.versioning_v2 import _build_coco_split
        return _build_coco_split(frames, anns, [], cat_map, "vtest")

    def test_anotacao_de_classe_dropada_e_ignorada_em_todos_os_splits(self):
        frames = [{"id": "f1", "width": 100, "height": 100, "filename": "f1.jpg"}]
        anns = {"f1": [
            {"class_id": 7, "class_name": "mascara",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
            {"class_id": 99, "class_name": "Capacete",   # fora do mapa
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]}
        d = self._coco({7: 1}, frames, anns)
        assert len(d["annotations"]) == 1, "classe dropada não pode virar anotação"
        assert d["annotations"][0]["category_id"] == 1

    def test_remap_identico_nos_tres_splits(self):
        # O MESMO cat_id_by_class serve os três splits: se divergisse, a
        # métrica de avaliação mediria outra classe que não a treinada.
        cat_map = {4: 1, 7: 2, 11: 3}
        out = []
        for fid in ("train1", "val1", "test1"):
            frames = [{"id": fid, "width": 50, "height": 50, "filename": f"{fid}.jpg"}]
            anns = {fid: [{"class_id": 11, "class_name": "x",
                           "x_center": 0.5, "y_center": 0.5,
                           "width": 0.1, "height": 0.1}]}
            out.append(self._coco(cat_map, frames, anns)["annotations"][0]["category_id"])
        assert len(set(out)) == 1 and out[0] == 3, f"remap divergiu entre splits: {out}"


class TestDiagnosticoDeSplit:
    """D-165 / issue #426 — o split por grupo saía torto e seguia CALADO.

    Medido: 17 grupos câmera+dia para 413 frames; o mesmo
    {train:0.7, val:0.2, test:0.1} produziu 210/6/179 (53/1,5/45) no v3-treino1
    e 354/51/8 (86/12/2) no v4. Nas duas vezes sem uma linha de aviso.

    ⛔ O split por grupo não muda — é ele que impede vazamento de câmera+dia.
    O que faltava era o aviso.
    """

    PEDIDO = {"train": 0.7, "val": 0.2, "test": 0.1}

    @staticmethod
    def _frames(n, inicio=0):
        return [{"id": f"f{i}"} for i in range(inicio, inicio + n)]

    @staticmethod
    def _anns(mapa):
        """{frame_id: [classes]} → anns_by_frame"""
        return {
            fid: [{"class_name": c, "class_id": 1} for c in classes]
            for fid, classes in mapa.items()
        }

    def _diag(self, v2_mod, train, val, test, anns=None):
        splits = {
            "train": self._frames(train),
            "val": self._frames(val, 1000),
            "test": self._frames(test, 2000),
        }
        return v2_mod._diagnosticar_split(splits, self.PEDIDO, anns or {})

    def test_split_saudavel_nao_avisa(self, v2_mod):
        assert self._diag(v2_mod, 700, 200, 100) == []

    def test_caso_real_v3_treino1_avisa(self, v2_mod):
        """210/6/179 — val com 6 imagens e test em 45% contra os 10% pedidos."""
        avisos = self._diag(v2_mod, 210, 6, 179)
        assert any("'val' com 6 imagem" in a for a in avisos)
        assert any("'test' ficou em 45%" in a for a in avisos)

    def test_caso_real_v4_avisa(self, v2_mod):
        """354/51/8 — test com 8 imagens, train em 86% contra os 70% pedidos."""
        avisos = self._diag(v2_mod, 354, 51, 8)
        assert any("'test' com 8 imagem" in a for a in avisos)
        assert any("'train' ficou em 86%" in a for a in avisos)

    def test_classe_que_treina_e_some_do_test_e_cegueira(self, v2_mod):
        anns = self._anns({
            **{f"f{i}": ["mascara", "oculos"] for i in range(700)},
            **{f"f{i}": ["mascara"] for i in range(2000, 2100)},
        })
        avisos = self._diag(v2_mod, 700, 200, 100, anns)
        assert any("ZERO no test" in a and "oculos" in a for a in avisos)

    def test_classe_com_suporte_fraco_no_test_avisa(self, v2_mod):
        """'Precisão sobre n=2 não é medida, é ruído com casas decimais.'"""
        anns = self._anns({
            **{f"f{i}": ["mascara"] for i in range(700)},
            **{f"f{i}": ["mascara"] for i in range(2000, 2002)},
        })
        avisos = self._diag(v2_mod, 700, 200, 100, anns)
        assert any("suporte fraco no test" in a and "mascara=2" in a for a in avisos)

    def test_sem_frame_nenhum_nao_quebra(self, v2_mod):
        assert self._diag(v2_mod, 0, 0, 0) == []


class TestSplitDeterministico:
    """#515 — o retry refazia o sorteio e misturava DOIS splits no mesmo
    prefixo R2.

    `max_retries=2` + `random.shuffle` sem semente: uma tentativa que morre
    no meio da etapa 7 deixa `train/_annotations.coco.json` de um sorteio e
    `val/` de outro. Medido no v9-freeze: 514 frames declarados nos dois —
    93% da "validação" já vista no treino, e a versão saiu `ready`.
    """

    def _frames(self):
        # 40 grupos (um vídeo por frame) — sem semente, dois sorteios
        # coincidirem é da ordem de 1/40!.
        return [_make_frame(uuid4(), i) for i in range(40)]

    def _coco_por_split(self, storage):
        """{split: [file_name, ...]} do que foi realmente subido ao R2."""
        por_split = {}
        for call in storage.upload_bytes.call_args_list:
            key = call.args[0]
            if not key.endswith("_annotations.coco.json"):
                continue
            doc = json.loads(call.args[1].decode("utf-8"))
            por_split[key.split("/")[-2]] = sorted(
                img["file_name"] for img in doc["images"]
            )
        return por_split

    def test_mesma_semente_reproduz_o_mesmo_sorteio(self, v2_mod):
        split = {"train": 0.7, "val": 0.2, "test": 0.1}
        frames = self._frames()
        a = v2_mod._split_by_group(frames, split, seed="ds-1:v9-freeze")
        b = v2_mod._split_by_group(frames, split, seed="ds-1:v9-freeze")
        for nome in ("train", "val", "test"):
            assert [f["id"] for f in a[nome]] == [f["id"] for f in b[nome]]

    def test_splits_continuam_disjuntos(self, v2_mod):
        split = {"train": 0.7, "val": 0.2, "test": 0.1}
        s = v2_mod._split_by_group(self._frames(), split, seed="ds-1:v9")
        ids = {k: {f["id"] for f in v} for k, v in s.items()}
        assert not ids["train"] & ids["val"]
        assert not ids["train"] & ids["test"]
        assert not ids["val"] & ids["test"]

    def test_retry_do_build_reescreve_o_mesmo_sorteio(self, v2_mod):
        """O que o incidente exige de verdade: DUAS execuções do build para
        o mesmo (dataset_id, version) têm de subir COCO idêntico por split —
        senão a re-tentativa sobrescreve o prefixo com um sorteio novo.
        Falha se a semente não chegar ao `_split_by_group` do build.
        """
        frames = self._frames()
        anns = [_make_ann(frames[0]["id"])]

        _, _, _, storage_1 = _run(
            v2_mod, [dict(f) for f in frames], list(anns), version="v9-freeze"
        )
        _, _, _, storage_2 = _run(
            v2_mod, [dict(f) for f in frames], list(anns), version="v9-freeze"
        )

        coco_1 = self._coco_por_split(storage_1)
        coco_2 = self._coco_por_split(storage_2)
        assert set(coco_1) == {"train", "val", "test"}
        assert coco_1 == coco_2

    def test_ordem_das_linhas_do_banco_nao_remistura_os_splits(self, v2_mod):
        """A semente pinou o SORTEIO, não a ENTRADA dele — e é a entrada que
        muda entre duas execuções.

        `_split_by_group` embaralha `list(groups.keys())`, cuja ordem nasce da
        ordem em que as linhas voltaram do banco. Essa ordem NÃO é total: o
        snapshot ordena por `(validated_at IS NOT NULL) DESC, video_id,
        frame_number` e todo frame de NVR entra com `video_id` NULL e
        `frame_number=0` (edge/routes.py:757) — o pool inteiro empata, e
        empate volta do Postgres em ordem arbitrária. Um humano que valida um
        frame entre as tentativas também troca a primeira chave.

        Sobre uma lista em outra ordem, a MESMA semente dá OUTRO sorteio.
        Medido antes do fix com 40 grupos: 8 dos frames de 'val' da segunda
        execução estavam no 'train' da primeira — a assinatura dos 514 do
        v9-freeze.

        Prova a invariante inteira: mesmo pool → mesmo split, nenhum frame em
        dois splits, e o banco registrando o que o artefato declara.
        """
        frames = self._frames()
        anns = [_make_ann(frames[0]["id"])]

        _, _, _, storage_1 = _run(
            v2_mod, [dict(f) for f in frames], list(anns), version="v9-freeze"
        )
        # Re-tentativa: as MESMAS linhas em outra ordem, reaproveitando a row.
        _, _, repo_2, storage_2 = _run(
            v2_mod, [dict(f) for f in reversed(frames)], list(anns),
            pending_version={"id": DV_ID, "status": "error"}, version="v9-freeze",
        )

        coco_1 = self._coco_por_split(storage_1)
        coco_2 = self._coco_por_split(storage_2)
        assert coco_1 == coco_2, "reordenar as linhas do banco refez o sorteio"

        # A assinatura do incidente: o COCO de um split declarando frames que
        # o de outro split — da outra execução, no MESMO prefixo R2 — declara.
        for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
            assert not set(coco_1[a]) & set(coco_2[b])
            assert not set(coco_2[a]) & set(coco_1[b])

        # E o banco descreve o artefato recém-escrito: o v9-freeze ficou com
        # val=159 na row da 1ª tentativa e 553 no COCO da última.
        repo_2.update_version_counts.assert_called_once()
        kw = repo_2.update_version_counts.call_args.kwargs
        assert kw["train_count"] == len(coco_2["train"])
        assert kw["val_count"] == len(coco_2["val"])
        assert kw["test_count"] == len(coco_2["test"])

    def test_versoes_diferentes_sorteiam_diferente(self, v2_mod):
        """Semente por (dataset_id, version): versão nova não herda o
        sorteio da anterior (senão o split viraria fixo pra sempre)."""
        frames = self._frames()
        anns = [_make_ann(frames[0]["id"])]
        _, _, _, s1 = _run(
            v2_mod, [dict(f) for f in frames], list(anns), version="v9-freeze"
        )
        _, _, _, s2 = _run(
            v2_mod, [dict(f) for f in frames], list(anns), version="v10"
        )
        assert self._coco_por_split(s1) != self._coco_por_split(s2)
