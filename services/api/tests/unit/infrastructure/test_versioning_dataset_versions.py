"""
Tests: versioning.py — bugs de dataset_versions (falha-antes/passa-depois):

  1) src key das cópias: usa a chave R2 REAL do frame
     (frames/{user_id}/{video_id}/frame_NNNN.jpg, gravada em filename/r2_key
     pelo extraction.py) — não remonta frames/{user_id}/{frame_id}/{filename};
  2) INSERT em dataset_versions ao final (colunas legadas + tenant_id/
     module_code/status da migration 096) — a task nunca INSERTava;
  3) LEFT JOIN training_videos (crítica A-2: após a 094, video_id pode ser
     NULL e o INNER JOIN excluiria frames de upload/auto silenciosamente).

celery não pode interferir: o fixture versioning_mod importa a task sob um
celery_app transparente ESCOPADO (monkeypatch restaura sys.modules no
teardown) — nada de poluição permanente de módulos entre arquivos de teste.
"""
import importlib
import sys
import types
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_VERSIONING_KEY = "app.infrastructure.queue.tasks.versioning"


class _TransparentCelery:
    def task(self, *args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator


@pytest.fixture
def versioning_mod(monkeypatch):
    """Importa versioning fresh sob celery_app transparente, sem vazar estado.

    monkeypatch.setitem/delitem restauram sys.modules no teardown; o módulo
    importado sob o stub é removido do cache (pop) para que testes seguintes
    reimportem a versão real — o delitem-undo devolve a original se existia.
    """
    fake = types.ModuleType(_CELERY_APP_KEY)
    fake.celery = _TransparentCelery()
    monkeypatch.setitem(sys.modules, _CELERY_APP_KEY, fake)
    monkeypatch.delitem(sys.modules, _VERSIONING_KEY, raising=False)
    mod = importlib.import_module(_VERSIONING_KEY)
    yield mod
    sys.modules.pop(_VERSIONING_KEY, None)


_TENANT_ID = uuid4()
_DV_ID = uuid4()


def _make_frame(user_id, video_id, frame_num, module_code="epi"):
    key = f"frames/{user_id}/{video_id or 'novideo'}/frame_{frame_num:04d}.jpg"
    return {
        "id": uuid4(),
        "video_id": video_id,
        "filename": key,
        "r2_key": key,
        "frame_number": frame_num,
        "module_code": module_code,
        "is_validated": True,
    }


def _run_build(versioning_mod, frames, user_id=None):
    user_id = user_id or str(uuid4())

    mock_repo = MagicMock()
    mock_repo._execute.return_value = frames
    mock_repo._execute_one.return_value = {"tenant_id": _TENANT_ID}
    mock_repo._execute_mutation.return_value = {"id": _DV_ID}
    mock_repo.get_classes_by_user.return_value = [{"id": 1, "name": "helmet"}]

    mock_storage = MagicMock()
    mock_self = MagicMock()
    mock_self.retry.side_effect = Exception("retry-called")

    with patch.object(versioning_mod, "_get_annotation_repo", return_value=mock_repo), \
         patch.object(versioning_mod, "_get_storage", return_value=mock_storage):
        result = versioning_mod.build_dataset_version(
            mock_self, user_id=user_id, version="v1.0"
        )

    return result, mock_repo, mock_storage, user_id


class TestFramesQuery:
    """A-2: LEFT JOIN + inclusão de frames com video_id NULL (escopo por tenant)."""

    def test_left_join_and_null_video_scope(self, versioning_mod):
        user = str(uuid4())
        frames = [_make_frame(user, uuid4(), i) for i in range(5)]
        _, mock_repo, _, _ = _run_build(versioning_mod, frames, user_id=user)

        query = mock_repo._execute.call_args.args[0]
        assert "LEFT JOIN training_videos" in query
        assert "video_id IS NULL" in query


class TestCopyKeys:
    """Chave de origem = filename/r2_key do frame (chave R2 completa)."""

    def test_image_src_is_stored_frame_key(self, versioning_mod):
        user = str(uuid4())
        vid = uuid4()
        frames = [_make_frame(user, vid, i) for i in range(5)]
        _, _, mock_storage, _ = _run_build(versioning_mod, frames, user_id=user)

        srcs = [c.args[0] for c in mock_storage.copy_object.call_args_list]
        img_srcs = {s for s in srcs if s.startswith("frames/")}
        assert img_srcs == {f["r2_key"] for f in frames}

    def test_no_frame_id_in_src_path(self, versioning_mod):
        """Bug antigo: src remontada como frames/{user_id}/{frame_id}/{filename}."""
        user = str(uuid4())
        vid = uuid4()
        frames = [_make_frame(user, vid, i) for i in range(5)]
        _, _, mock_storage, _ = _run_build(versioning_mod, frames, user_id=user)

        srcs = [c.args[0] for c in mock_storage.copy_object.call_args_list]
        frame_ids = {str(f["id"]) for f in frames}
        for src in srcs:
            for fid in frame_ids:
                assert f"/{fid}/" not in src

    def test_label_src_mirrors_frame_key(self, versioning_mod):
        """Labels vivem em labels/{...} espelhando a chave do frame
        (ver annotation_service._export_yolo_labels)."""
        user = str(uuid4())
        vid = uuid4()
        frames = [_make_frame(user, vid, i) for i in range(5)]
        _, _, mock_storage, _ = _run_build(versioning_mod, frames, user_id=user)

        srcs = [c.args[0] for c in mock_storage.copy_object.call_args_list]
        lbl_srcs = {s for s in srcs if s.startswith("labels/")}
        expected = {f"labels/{user}/{vid}/frame_{i:04d}.txt" for i in range(5)}
        assert lbl_srcs == expected


class TestDatasetVersionInsert:
    """A task deve registrar a versão em dataset_versions (bug: nunca INSERTava)."""

    def test_insert_row_created_with_096_columns(self, versioning_mod):
        user = str(uuid4())
        frames = [_make_frame(user, uuid4(), i) for i in range(5)]
        result, mock_repo, _, _ = _run_build(versioning_mod, frames, user_id=user)

        mock_repo._execute_mutation.assert_called_once()
        sql = mock_repo._execute_mutation.call_args.args[0]
        assert "INSERT INTO dataset_versions" in sql
        for col in ("tenant_id", "module_code", "status"):
            assert col in sql
        assert result["dataset_version_id"] == str(_DV_ID)

    def test_insert_params_include_counts_tenant_and_module(self, versioning_mod):
        user = str(uuid4())
        frames = [_make_frame(user, uuid4(), i) for i in range(5)]
        _, mock_repo, _, _ = _run_build(versioning_mod, frames, user_id=user)

        params = mock_repo._execute_mutation.call_args.args[1]
        as_str = [str(p) for p in params]
        assert user in as_str
        assert "v1.0" in as_str
        assert str(_TENANT_ID) in as_str
        assert "epi" in as_str


class TestNullVideoFrames:
    """Sanidade: frames sem vídeo (upload/auto) entram no split sem crash."""

    def test_null_video_frames_are_split_without_crash(self, versioning_mod):
        user = str(uuid4())
        frames = [_make_frame(user, None, i) for i in range(6)]
        result, _, _, _ = _run_build(versioning_mod, frames, user_id=user)

        assert result["total_frames"] == 6
        total = result["train_count"] + result["val_count"] + result["test_count"]
        assert total == 6
