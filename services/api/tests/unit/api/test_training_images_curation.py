"""
Tests: curadoria de frames (migration 110).

Cobre:
- GET  /api/training/images        → filtros novos ?camera_id= / ?curation_status=
- GET  /api/training/images/facets → contagens por câmera e status
- POST /api/training/frames/curation → curadoria em lote
"""
from unittest.mock import MagicMock, patch
from datetime import datetime
from uuid import uuid4

from flask_jwt_extended import create_access_token

TENANT_ID = "00000000-0000-0000-0000-000000000001"
_HANDLERS = "app.api.v1.training.image_handlers"


def _make_token(app, role="admin", tenant_id=TENANT_ID, user_id=None):
    uid = user_id or uuid4()
    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={"role": role, "tenant_id": tenant_id},
        )
    return token, uid


def _filtered_result(frames=None):
    return {
        "frames": frames if frames is not None else [],
        "total": len(frames or []),
        "page": 1,
        "page_size": 24,
        "total_pages": 1,
    }


# ---------------------------------------------------------------------------
# GET /api/training/images — filtros camera_id / curation_status
# ---------------------------------------------------------------------------

class TestGalleryCurationFilters:
    def test_camera_id_filter_passed_to_repo(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result()
        cam = str(uuid4())

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                f"/api/training/images?camera_id={cam}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.list_images_filtered.call_args.kwargs
        assert kwargs["camera_id"] == cam

    def test_invalid_camera_id_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images?camera_id=not-a-uuid",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.list_images_filtered.assert_not_called()

    def test_curation_status_filter_passed_to_repo(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images?curation_status=duvida",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.list_images_filtered.call_args.kwargs
        assert kwargs["curation_status"] == "duvida"

    def test_invalid_curation_status_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images?curation_status=bogus",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.list_images_filtered.assert_not_called()

    def test_camera_ids_csv_passed_to_repo(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result()
        cam1, cam2 = str(uuid4()), str(uuid4())

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                f"/api/training/images?camera_ids={cam1},{cam2}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.list_images_filtered.call_args.kwargs
        assert set(kwargs["camera_ids"]) == {cam1, cam2}

    def test_camera_ids_repeated_param_passed_to_repo(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result()
        cam1, cam2 = str(uuid4()), str(uuid4())

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                f"/api/training/images?camera_ids={cam1}&camera_ids={cam2}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.list_images_filtered.call_args.kwargs
        assert set(kwargs["camera_ids"]) == {cam1, cam2}

    def test_invalid_camera_ids_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images?camera_ids=not-a-uuid",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.list_images_filtered.assert_not_called()

    def test_no_camera_ids_param_passes_none(self, client, app):
        """Sem camera_ids na query, o handler passa None — repo cai para o
        caminho compat de camera_id singular (ou nenhum filtro de câmera)."""
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.list_images_filtered.call_args.kwargs
        assert kwargs["camera_ids"] is None

    def test_proposal_classes_csv_passed_to_repo_lowercased(self, client, app):
        """#516 filtro por classe: CSV de nomes → lista lower/strip, sem repetição."""
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images?proposal_classes=Mascara,%20Sem%20mascara%20,mascara",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.list_images_filtered.call_args.kwargs
        assert kwargs["proposal_classes"] == ["mascara", "sem mascara"]

    def test_no_proposal_classes_passes_none(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images?proposal_classes=",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        assert repo.list_images_filtered.call_args.kwargs["proposal_classes"] is None

    def test_too_many_proposal_classes_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        muitos = ",".join(f"c{i}" for i in range(51))

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                f"/api/training/images?proposal_classes={muitos}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.list_images_filtered.assert_not_called()

    def test_camera_id_serialized_as_string(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        cam = uuid4()
        repo.list_images_filtered.return_value = _filtered_result([
            {
                "id": uuid4(), "video_id": None, "frame_number": 0,
                "filename": "x.jpg", "r2_key": "x.jpg", "source": "nvr",
                "width": 100, "height": 100, "camera_id": cam,
                "curation_status": "active", "is_annotated": False,
                "created_at": "2026-08-01T00:00:00", "status": "unlabeled",
                "video_name": None,
            },
        ])

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images",
                headers={"Authorization": f"Bearer {token}"},
            )

        frame = res.get_json()["data"]["frames"][0]
        assert frame["camera_id"] == str(cam)


# ---------------------------------------------------------------------------
# GET /api/training/images/facets
# ---------------------------------------------------------------------------

class TestImageFacets:
    def test_returns_facets_scoped_to_tenant(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_facets.return_value = {
            "cameras": [{"camera_id": str(uuid4()), "camera_name": "Portaria", "count": 5}],
            "status": {"nao_anotado": 10, "anotado": 4, "duvida": 2, "excluida": 1},
        }

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images/facets",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.get_facets.call_args.kwargs
        assert kwargs["tenant_id"] == TENANT_ID
        data = res.get_json()["data"]
        assert data["status"]["duvida"] == 2
        assert data["cameras"][0]["camera_name"] == "Portaria"

    def test_forwards_active_filters(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_facets.return_value = {"cameras": [], "status": {}}
        cam = str(uuid4())

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                f"/api/training/images/facets?source=nvr&camera_id={cam}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.get_facets.call_args.kwargs
        assert kwargs["source"] == "nvr"
        assert kwargs["camera_id"] == cam

    def test_invalid_source_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images/facets?source=bogus",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.get_facets.assert_not_called()

    def test_forwards_camera_ids_csv(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_facets.return_value = {"cameras": [], "status": {}}
        cam1, cam2 = str(uuid4()), str(uuid4())

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                f"/api/training/images/facets?camera_ids={cam1},{cam2}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        kwargs = repo.get_facets.call_args.kwargs
        assert set(kwargs["camera_ids"]) == {cam1, cam2}

    def test_invalid_camera_ids_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images/facets?camera_ids=not-a-uuid",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.get_facets.assert_not_called()

    def test_no_jwt_returns_401(self, client):
        res = client.get("/api/training/images/facets")
        assert res.status_code in (401, 422)


# ---------------------------------------------------------------------------
# POST /api/training/frames/curation
# ---------------------------------------------------------------------------

class TestCurateFrames:
    def test_curates_batch_returns_updated_count(self, client, app):
        token, uid = _make_token(app)
        repo = MagicMock()
        repo.update_curation_status.return_value = 2
        f1, f2 = str(uuid4()), str(uuid4())

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.post(
                "/api/training/frames/curation",
                json={"frame_ids": [f1, f2], "status": "duvida"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        assert res.get_json()["data"]["updated"] == 2
        kwargs = repo.update_curation_status.call_args.kwargs
        assert kwargs["status"] == "duvida"
        assert kwargs["tenant_id"] == TENANT_ID
        assert str(kwargs["updated_by"]) == str(uid)
        assert {str(f) for f in kwargs["frame_ids"]} == {f1, f2}

    def test_empty_frame_ids_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.post(
                "/api/training/frames/curation",
                json={"frame_ids": [], "status": "duvida"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.update_curation_status.assert_not_called()

    def test_missing_frame_ids_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.post(
                "/api/training/frames/curation",
                json={"status": "duvida"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400

    def test_invalid_status_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.post(
                "/api/training/frames/curation",
                json={"frame_ids": [str(uuid4())], "status": "bogus"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.update_curation_status.assert_not_called()

    def test_invalid_frame_id_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.post(
                "/api/training/frames/curation",
                json={"frame_ids": ["not-a-uuid"], "status": "active"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.update_curation_status.assert_not_called()

    def test_batch_over_limit_returns_400(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        too_many = [str(uuid4()) for _ in range(501)]

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.post(
                "/api/training/frames/curation",
                json={"frame_ids": too_many, "status": "active"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.update_curation_status.assert_not_called()

    def test_cross_tenant_ids_silently_not_updated(self, client, app):
        """Escopo por tenant é feito no WHERE do repo — o handler não sabe
        (nem precisa saber) quais ids eram de outro tenant; só repassa o
        `updated` que o repo devolveu (sem vazar existência, C-01)."""
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.update_curation_status.return_value = 0  # nenhum pertencia ao tenant
        repo_frame_ids = [str(uuid4())]

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.post(
                "/api/training/frames/curation",
                json={"frame_ids": repo_frame_ids, "status": "excluida"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        assert res.get_json()["data"]["updated"] == 0

    def test_write_role_required(self, client, app):
        """@require_training_role('write') — viewer não pode curar."""
        token, _ = _make_token(app, role="viewer")
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.post(
                "/api/training/frames/curation",
                json={"frame_ids": [str(uuid4())], "status": "active"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        repo.update_curation_status.assert_not_called()

    def test_no_jwt_returns_401(self, client):
        res = client.post(
            "/api/training/frames/curation",
            json={"frame_ids": [str(uuid4())], "status": "active"},
        )
        assert res.status_code in (401, 422)


# ---------------------------------------------------------------------------
# GET /api/training/images — cursor keyset (?before_id=)
# ---------------------------------------------------------------------------

class TestGalleryCursor:
    """O cursor tem de sobreviver à IDA E VOLTA pelo serializador do Flask.

    Foi exatamente aí que a primeira versão quebrou: o cursor levava também o
    `created_at` ecoado da resposta, e o Flask serializa datetime em RFC 822
    ("Tue, 18 Aug 2026 15:36:38 GMT"). O `fromisoformat` recusava, todo lote a
    partir do segundo virava 400, e o `catch` silencioso do prefetch
    transformava isso em "a fila parou nos 40", sem erro na tela. Nenhum teste
    pegava porque nenhum atravessava o serializador — os de repositório
    passavam `datetime` direto.

    Estes atravessam: leem o id DA RESPOSTA JSON e mandam de volta.
    """

    def _frame(self):
        return {
            "id": str(uuid4()),
            "video_id": None,
            "camera_id": None,
            "filename": "x.jpg",
            "created_at": datetime(2026, 8, 18, 15, 36, 38, 482853),
            "curation_status": "active",
            "is_annotated": False,
        }

    def test_id_da_resposta_volta_como_cursor_sem_400(self, client, app):
        token, _ = _make_token(app)
        frames = [self._frame() for _ in range(3)]
        repo = MagicMock()
        repo.cursor_frame_exists.return_value = True
        repo.list_images_filtered.return_value = _filtered_result(frames)

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            primeiro = client.get(
                "/api/training/images?page_size=3",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert primeiro.status_code == 200
            # o cursor sai DA RESPOSTA, como o navegador faz
            ultimo_id = primeiro.get_json()["data"]["frames"][-1]["id"]

            segundo = client.get(
                f"/api/training/images?page_size=3&before_id={ultimo_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert segundo.status_code == 200, segundo.get_json()
        assert repo.list_images_filtered.call_args.kwargs["cursor"] == ultimo_id

    def test_sem_before_id_nao_manda_cursor(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_images_filtered.return_value = _filtered_result()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        assert repo.list_images_filtered.call_args.kwargs["cursor"] is None

    def test_before_id_invalido_da_400_e_nao_chama_o_repo(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                "/api/training/images?before_id=nao-e-uuid",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        repo.list_images_filtered.assert_not_called()

    def test_cursor_morto_da_410_e_nao_lista_vazia(self, client, app):
        """Frame do cursor apagado (vídeo pai removido) tem de dar 410.

        Lista vazia é indistinguível de fim de fila, e a tela anunciaria
        "fila concluída" com o acervo cheio. Frame de vídeo É apagável:
        DELETE /api/v1/videos/<id> roda DELETE FROM training_frames, e
        recorte de vídeo enviado entra nesta fila (only_crops é heurística
        de dimensão, não de origem).
        """
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.cursor_frame_exists.return_value = False

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                f"/api/training/images?before_id={uuid4()}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 410
        repo.list_images_filtered.assert_not_called()

    def test_cursor_vivo_segue_para_o_repo(self, client, app):
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.cursor_frame_exists.return_value = True
        repo.list_images_filtered.return_value = _filtered_result()
        fid = str(uuid4())

        with patch(f"{_HANDLERS}.DatabasePool") as pool_cls, \
             patch(f"{_HANDLERS}.FrameRepository", return_value=repo):
            pool_cls.get_instance.return_value = MagicMock()
            res = client.get(
                f"/api/training/images?before_id={fid}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        assert repo.list_images_filtered.call_args.kwargs["cursor"] == fid
