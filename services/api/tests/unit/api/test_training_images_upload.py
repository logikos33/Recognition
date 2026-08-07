"""
Tests: WS-A2 — ingestão de imagens de treino por upload.

Cobre:
- upload_training_images_handler: POST /api/training/images/upload
  (multipart batch, validação de extensão/tamanho/lote, R2 key pattern,
  FrameRepository.create com source='upload' e video_id=None, gate
  @require_training_role('write'))
- list_training_images_handler: filtros novos ?source= e ?status=
  (caminho tenant-scoped) mantendo compat do caminho legado
- FrameRepository.list_images_filtered: SQL tenant-scoped + LEFT JOIN

A rota de upload ainda não está wired em routes.py (o orquestrador cola o
wiring): os testes registram um blueprint espelhando EXATAMENTE o snippet.
"""
import io
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token, jwt_required

from app.infrastructure.database.repositories.frame_repository import FrameRepository

TENANT_ID = "00000000-0000-0000-0000-000000000001"

_HANDLERS = "app.api.v1.training.image_handlers"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(app, role="admin", tenant_id=TENANT_ID, user_id=None):
    uid = user_id or uuid4()
    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={"role": role, "tenant_id": tenant_id},
        )
    return token, uid


def _png_bytes(width=32, height=24):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _fake_create(**kwargs):
    """Side effect do FrameRepository.create — ecoa kwargs como row."""
    return {
        "id": uuid4(),
        "r2_key": kwargs.get("r2_key"),
        "filename": kwargs.get("filename"),
        "source": str(kwargs.get("source")),
        "width": kwargs.get("width"),
        "height": kwargs.get("height"),
        "module_code": kwargs.get("module_code") or "epi",
    }


def _mock_repo():
    repo = MagicMock()
    repo.create.side_effect = _fake_create
    return repo


# ---------------------------------------------------------------------------
# Fixtures — blueprint de teste espelhando o wiring snippet do orquestrador
# ---------------------------------------------------------------------------

@pytest.fixture
def upload_app(app):
    from app.api.v1.training.image_handlers import upload_training_images_handler
    from app.core.auth import require_training_role

    bp = Blueprint("training_upload_test", __name__)

    @bp.route("/api/training/images/upload", methods=["POST"])
    @jwt_required()
    @require_training_role("write")
    def upload_training_images():
        return upload_training_images_handler()

    app.register_blueprint(bp)
    return app


@pytest.fixture
def upload_client(upload_app):
    return upload_app.test_client()


# ---------------------------------------------------------------------------
# Tests: POST /api/training/images/upload
# ---------------------------------------------------------------------------

class TestUploadTrainingImages:

    def test_upload_valid_images_returns_201(self, upload_client, upload_app):
        token, user_id = _make_token(upload_app)
        storage = MagicMock()
        repo = _mock_repo()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo), \
             patch(f"{_HANDLERS}.get_storage", return_value=storage):
            pool_cls.get_instance.return_value = MagicMock()

            res = upload_client.post(
                "/api/training/images/upload",
                data={
                    "files": [
                        (io.BytesIO(_png_bytes(32, 24)), "a.png"),
                        (io.BytesIO(_png_bytes(64, 48)), "b.png"),
                    ],
                },
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 201
        body = res.get_json()
        assert body["success"] is True
        assert body["data"]["uploaded"] == 2
        assert body["data"]["failed"] == 0
        assert len(body["data"]["images"]) == 2
        assert storage.upload_bytes.call_count == 2
        assert repo.create.call_count == 2

    def test_upload_creates_frame_with_upload_source_and_dimensions(
        self, upload_client, upload_app
    ):
        token, user_id = _make_token(upload_app)
        repo = _mock_repo()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo), \
             patch(f"{_HANDLERS}.get_storage", return_value=MagicMock()):
            pool_cls.get_instance.return_value = MagicMock()

            upload_client.post(
                "/api/training/images/upload",
                data={"files": [(io.BytesIO(_png_bytes(320, 240)), "cam.jpg")]},
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        kwargs = repo.create.call_args.kwargs
        assert kwargs["video_id"] is None
        assert str(kwargs["source"]) == "upload"
        assert kwargs["width"] == 320
        assert kwargs["height"] == 240
        assert kwargs["tenant_id"] == TENANT_ID
        assert str(kwargs["user_id"]) == str(user_id)
        assert kwargs["r2_key"].startswith(f"training-images/{TENANT_ID}/upload/")
        assert kwargs["r2_key"].endswith(".jpg")
        assert kwargs["filename"] == kwargs["r2_key"]

    def test_upload_rejects_invalid_extension(self, upload_client, upload_app):
        token, _ = _make_token(upload_app)
        repo = _mock_repo()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo), \
             patch(f"{_HANDLERS}.get_storage", return_value=MagicMock()):
            pool_cls.get_instance.return_value = MagicMock()

            res = upload_client.post(
                "/api/training/images/upload",
                data={"files": [(io.BytesIO(b"malware"), "run.exe")]},
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Lote inteiro inválido → 400, nada persistido
        assert res.status_code == 400
        assert repo.create.call_count == 0

    def test_upload_corrupt_image_counted_as_failed(self, upload_client, upload_app):
        """Bytes não-imagem com extensão válida contam como failed.

        Falha PARCIAL (1 de 2) responde 207, não 201 — 201 sinalizaria
        sucesso total e o front não pode confundir "1 de 2 subiu" com "2 de
        2" (achado: storage falha alto, upload engolia falha por-arquivo).
        """
        token, _ = _make_token(upload_app)
        repo = _mock_repo()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo), \
             patch(f"{_HANDLERS}.get_storage", return_value=MagicMock()):
            pool_cls.get_instance.return_value = MagicMock()

            res = upload_client.post(
                "/api/training/images/upload",
                data={
                    "files": [
                        (io.BytesIO(b"not-an-image"), "fake.jpg"),
                        (io.BytesIO(_png_bytes()), "real.png"),
                    ],
                },
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 207
        body = res.get_json()
        assert body["success"] is True
        assert body["data"]["uploaded"] == 1
        assert body["data"]["failed"] == 1
        assert len(body["data"]["failed_files"]) == 1
        assert body["data"]["failed_files"][0]["filename"] == "fake.jpg"
        assert body["data"]["failed_files"][0]["reason"]

    def test_upload_all_files_fail_on_storage_error_returns_400_not_201(
        self, upload_client, upload_app
    ):
        """Se TODOS os arquivos falharem (ex.: R2 fora do ar), a resposta
        precisa ser de erro — nunca 201 com uploaded=0 disfarçando falha
        total como sucesso."""
        token, _ = _make_token(upload_app)
        repo = _mock_repo()
        storage = MagicMock()
        storage.upload_bytes.side_effect = Exception("R2 AccessDenied")

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo), \
             patch(f"{_HANDLERS}.get_storage", return_value=storage):
            pool_cls.get_instance.return_value = MagicMock()

            res = upload_client.post(
                "/api/training/images/upload",
                data={
                    "files": [
                        (io.BytesIO(_png_bytes()), "a.png"),
                        (io.BytesIO(_png_bytes()), "b.png"),
                    ],
                },
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code != 201
        assert res.status_code == 400
        body = res.get_json()
        assert body["success"] is False
        # Nenhuma linha órfã: upload falhou, repo.create nunca deveria rodar.
        repo.create.assert_not_called()

    def test_upload_db_insert_failure_rolls_back_orphan_r2_object(
        self, upload_client, upload_app
    ):
        """Upload no R2 tem sucesso mas o INSERT falha (ex.: erro de
        conexão com o banco): o objeto órfão no R2 é removido — nunca fica
        linha no banco sem objeto (isso já era garantido pela ordem
        upload-then-insert) e também não fica objeto no R2 sem
        possibilidade de referência futura."""
        token, _ = _make_token(upload_app)
        repo = MagicMock()
        repo.create.side_effect = Exception("connection reset")
        storage = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo), \
             patch(f"{_HANDLERS}.get_storage", return_value=storage):
            pool_cls.get_instance.return_value = MagicMock()

            res = upload_client.post(
                "/api/training/images/upload",
                data={"files": [(io.BytesIO(_png_bytes()), "a.png")]},
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Único arquivo do lote falhou no INSERT -> lote inteiro falhou -> 400
        assert res.status_code == 400
        storage.upload_bytes.assert_called_once()
        storage.delete.assert_called_once()
        uploaded_key = storage.upload_bytes.call_args.args[0]
        deleted_key = storage.delete.call_args.args[0]
        assert uploaded_key == deleted_key

    def test_upload_rejects_oversized_file(
        self, upload_client, upload_app, monkeypatch
    ):
        token, _ = _make_token(upload_app)
        repo = _mock_repo()
        monkeypatch.setattr(f"{_HANDLERS}._MAX_IMAGE_BYTES", 10)

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo), \
             patch(f"{_HANDLERS}.get_storage", return_value=MagicMock()):
            pool_cls.get_instance.return_value = MagicMock()

            res = upload_client.post(
                "/api/training/images/upload",
                data={"files": [(io.BytesIO(_png_bytes()), "big.png")]},
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        assert repo.create.call_count == 0

    def test_upload_rejects_batch_over_limit(
        self, upload_client, upload_app, monkeypatch
    ):
        token, _ = _make_token(upload_app)
        monkeypatch.setattr(f"{_HANDLERS}._MAX_IMAGES_PER_BATCH", 1)

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=_mock_repo()), \
             patch(f"{_HANDLERS}.get_storage", return_value=MagicMock()):
            pool_cls.get_instance.return_value = MagicMock()

            res = upload_client.post(
                "/api/training/images/upload",
                data={
                    "files": [
                        (io.BytesIO(_png_bytes()), "a.png"),
                        (io.BytesIO(_png_bytes()), "b.png"),
                    ],
                },
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400

    def test_upload_without_files_field_returns_400(self, upload_client, upload_app):
        token, _ = _make_token(upload_app)

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=_mock_repo()), \
             patch(f"{_HANDLERS}.get_storage", return_value=MagicMock()):
            pool_cls.get_instance.return_value = MagicMock()

            res = upload_client.post(
                "/api/training/images/upload",
                data={},
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400

    def test_upload_accepts_files_bracket_field_name(self, upload_client, upload_app):
        """Compat com frontends que enviam files[] (convenção PHP/axios)."""
        token, _ = _make_token(upload_app)
        repo = _mock_repo()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo), \
             patch(f"{_HANDLERS}.get_storage", return_value=MagicMock()):
            pool_cls.get_instance.return_value = MagicMock()

            res = upload_client.post(
                "/api/training/images/upload",
                data={"files[]": [(io.BytesIO(_png_bytes()), "a.png")]},
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 201
        assert repo.create.call_count == 1

    def test_upload_without_write_role_returns_403(self, upload_client, upload_app):
        """Role sem privilégio e sem override training:write → 403."""
        token, _ = _make_token(upload_app, role="operator")

        with patch("app.core.auth._has_training_override", return_value=False):
            res = upload_client.post(
                "/api/training/images/upload",
                data={"files": [(io.BytesIO(_png_bytes()), "a.png")]},
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403

    def test_upload_no_jwt_returns_401(self, upload_client):
        res = upload_client.post(
            "/api/training/images/upload",
            data={"files": [(io.BytesIO(_png_bytes()), "a.png")]},
            content_type="multipart/form-data",
        )
        assert res.status_code in (401, 422)


# ---------------------------------------------------------------------------
# Tests: GET /api/training/images — filtros ?source= e ?status= (WS-A2)
# ---------------------------------------------------------------------------

def _filtered_result(frames=None):
    return {
        "frames": frames if frames is not None else [],
        "total": len(frames or []),
        "page": 1,
        "page_size": 24,
        "total_pages": 1,
    }


class TestListTrainingImagesFilters:

    def test_source_filter_uses_tenant_scoped_query(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result([
            {
                "id": uuid4(),
                "video_id": None,
                "frame_number": 0,
                "filename": "training-images/t/upload/x.jpg",
                "r2_key": "training-images/t/upload/x.jpg",
                "source": "upload",
                "width": 320,
                "height": 240,
                "is_annotated": False,
                "created_at": "2026-07-01T00:00:00",
                "status": "unlabeled",
                "video_name": None,
            },
        ])

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()

            res = client.get(
                "/api/training/images?source=upload",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.list_images_filtered.call_args.kwargs
        assert kwargs["tenant_id"] == TENANT_ID
        assert kwargs["source"] == "upload"
        assert kwargs["status"] is None
        repo.get_by_user_paginated.assert_not_called()

        frame = res.get_json()["data"]["frames"][0]
        assert frame["video_id"] is None  # serialização segura de NULL
        assert frame["status"] == "unlabeled"
        assert frame["source"] == "upload"

    def test_status_filter_passed_to_repo(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()

            res = client.get(
                "/api/training/images?status=reviewed",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.list_images_filtered.call_args.kwargs
        assert kwargs["status"] == "reviewed"
        assert kwargs["source"] is None

    def test_invalid_source_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()

            res = client.get(
                "/api/training/images?source=dropbox",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.list_images_filtered.assert_not_called()

    def test_invalid_status_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()

            res = client.get(
                "/api/training/images?status=pending",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.list_images_filtered.assert_not_called()

    def test_legacy_path_only_with_explicit_opt_in(self, client, app):
        """O caminho user-scoped virou opt-in (`?legacy=1`).

        Como DEFAULT ele escondia todo frame sem vídeo pai (source nvr/upload/
        auto tem video_id NULL desde a migration 094) por causa do INNER JOIN
        em training_videos — ou seja, frame coletado do NVR nunca aparecia na
        galeria. Também escondia frame de outro usuário do mesmo tenant, o que
        não faz sentido num pool de anotação de equipe.
        """
        token, user_id = _make_token(app)
        video_id = uuid4()
        repo = MagicMock()
        repo.get_by_user_paginated.return_value = _filtered_result([
            {
                "id": uuid4(),
                "video_id": video_id,
                "frame_number": 3,
                "filename": "frames/u/v/frame_0003.jpg",
                "is_annotated": True,
                "created_at": "2026-07-01T00:00:00",
                "video_name": "obra.mp4",
            },
        ])

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()

            res = client.get(
                "/api/training/images?is_annotated=true&legacy=1",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        repo.list_images_filtered.assert_not_called()
        assert str(repo.get_by_user_paginated.call_args.kwargs["user_id"]) == str(user_id)

        frame = res.get_json()["data"]["frames"][0]
        assert frame["video_id"] == str(video_id)
        assert frame["video_name"] == "obra.mp4"

    def test_default_uses_tenant_scoped_path(self, client, app):
        """Sem parâmetro nenhum, o default agora é tenant-scoped — é o que faz
        o frame do NVR (video_id NULL) aparecer na galeria."""
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result([
            {
                "id": uuid4(),
                "video_id": None,
                "frame_number": 0,
                "filename": "training-images/t/nvr/r/x.jpg",
                "is_annotated": False,
                "created_at": "2026-07-31T00:00:00",
                "source": "nvr",
            },
        ])

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()

            res = client.get(
                "/api/training/images",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        repo.get_by_user_paginated.assert_not_called()
        repo.list_images_filtered.assert_called_once()
        frame = res.get_json()["data"]["frames"][0]
        assert frame["video_id"] is None  # frame sem vídeo pai sobrevive
        assert frame["source"] == "nvr"


# ---------------------------------------------------------------------------
# Tests: FrameRepository.list_images_filtered (SQL montado)
# ---------------------------------------------------------------------------

class TestListImagesFilteredRepository:

    def _repo_with_cursor(self, mock_db_pool):
        pool, _conn, cursor = mock_db_pool
        cursor.fetchone.return_value = {"total": 0}
        cursor.fetchall.return_value = []
        return FrameRepository(pool), cursor

    def test_query_is_tenant_scoped_with_source_param(self, mock_db_pool):
        repo, cursor = self._repo_with_cursor(mock_db_pool)

        repo.list_images_filtered(TENANT_ID, source="upload")

        count_sql, count_params = cursor.execute.call_args_list[0][0]
        assert "tf.tenant_id = %s" in count_sql
        assert "tf.source = %s" in count_sql
        assert count_params == (TENANT_ID, "upload")

    def test_select_uses_left_join_and_computed_status(self, mock_db_pool):
        repo, cursor = self._repo_with_cursor(mock_db_pool)

        repo.list_images_filtered(TENANT_ID)

        select_sql = cursor.execute.call_args_list[1][0][0]
        assert "LEFT JOIN training_videos" in select_sql
        assert "'reviewed'" in select_sql
        assert "'labeled'" in select_sql
        assert "'unlabeled'" in select_sql

    def test_status_reviewed_filters_validated_at(self, mock_db_pool):
        repo, cursor = self._repo_with_cursor(mock_db_pool)

        repo.list_images_filtered(TENANT_ID, status="reviewed")

        count_sql = cursor.execute.call_args_list[0][0][0]
        assert "tf.validated_at IS NOT NULL" in count_sql

    def test_status_labeled_filters_annotated_not_validated(self, mock_db_pool):
        repo, cursor = self._repo_with_cursor(mock_db_pool)

        repo.list_images_filtered(TENANT_ID, status="labeled")

        count_sql = cursor.execute.call_args_list[0][0][0]
        assert "tf.is_annotated = TRUE AND tf.validated_at IS NULL" in count_sql

    def test_invalid_status_raises_value_error(self, mock_db_pool):
        repo, _cursor = self._repo_with_cursor(mock_db_pool)

        with pytest.raises(ValueError, match="status inválido"):
            repo.list_images_filtered(TENANT_ID, status="bogus")

    def test_pagination_params_appended_last(self, mock_db_pool):
        repo, cursor = self._repo_with_cursor(mock_db_pool)

        repo.list_images_filtered(TENANT_ID, page=3, page_size=10)

        select_params = cursor.execute.call_args_list[1][0][1]
        assert select_params == (TENANT_ID, 10, 20)  # LIMIT 10 OFFSET 20
