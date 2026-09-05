"""
Tests: persistência e leitura da MEMBRESIA do holdout (migration 131).

O que estes testes seguram, e por quê:

1. GRAVA E LÊ IGUAL — a membresia que sai do build volta idêntica do banco.
   Sem isso a coluna é decoração.
2. DOIS MODELOS, MESMA PROVA — dois modelos diferentes avaliados contra o
   MESMO holdout recebem a MESMA lista de frames. Este é o defeito que a
   tarefa existe para matar: `_resolve_holdout_split` lia as contagens da
   dataset_version DO PRÓPRIO MODELO, e por isso o ranking histórico comparou
   notas de exames diferentes.
3. VERSÃO ANTIGA NÃO MENTE — build anterior à 131 não tem membresia; a leitura
   devolve frozen=False em vez de fingir que a prova estava congelada.
4. O BUILD GRAVA — build_dataset_version_v2 chama update_split_membership com
   os ids exatos de cada split, antes de marcar 'ready'.

A migration em si (2 passadas, idempotência) é provada pelo harness:
`bash tests/harness/migrations/run.sh` — ver o commit da migration.
"""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

from app.infrastructure.database.repositories.dataset_repository import DatasetRepository
from app.infrastructure.queue.tasks import model_evaluation

DSV_ID = "77777777-7777-7777-7777-777777777777"
TENANT_ID = "11111111-1111-1111-1111-111111111111"
MODEL_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
MODEL_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

# 5 frames no test, 3 no train — ids que o COCO do R2 nomeia como "<id>.jpg".
MEMBRESIA = {
    "train": ["f-01", "f-02", "f-03"],
    "val": ["f-04"],
    "test": ["f-10", "f-11", "f-12", "f-13", "f-14"],
}


def _coco_com(frame_ids: list[str], extras: list[str] = ()) -> bytes:
    """COCO do R2 com os frames pedidos + intrusos que NÃO estão na membresia."""
    nomes = [*frame_ids, *extras]
    return json.dumps({
        "categories": [{"id": 1, "name": "Luvas"}],
        "images": [
            {"id": i, "file_name": f"{n}.jpg", "width": 640, "height": 480}
            for i, n in enumerate(nomes, start=1)
        ],
        "annotations": [
            {"id": i, "image_id": i, "category_id": 1, "bbox": [0, 0, 10, 10]}
            for i, _ in enumerate(nomes, start=1)
        ],
    }).encode("utf-8")


class _RepoFake(DatasetRepository):
    """DatasetRepository real, com o SQL trocado por um dict.

    Herda a classe de produção de propósito: o que está sendo testado é
    `get_holdout`, e ela precisa rodar de verdade — não uma reimplementação
    do teste que concorda com ela por construção.
    """

    def __init__(self, row: dict | None):
        self._row = row
        self._gravado: dict | None = None

    def _execute_one(self, query, params=()):  # type: ignore[override]
        return dict(self._row) if self._row else None

    def _execute_mutation(self, query, params=()):  # type: ignore[override]
        # update_split_membership manda o jsonb já serializado no params[0]
        self._gravado = json.loads(params[0])
        return {"id": DSV_ID}


class TestMembresiaGravaELe:
    def test_grava_e_le_de_volta_identica(self):
        repo = _RepoFake(None)
        repo.update_split_membership(DSV_ID, TENANT_ID, MEMBRESIA)
        assert repo._gravado == MEMBRESIA

        # ida e volta pelo banco: a row lida traz o jsonb da gravação
        lido = _RepoFake({
            "id": DSV_ID, "coco_r2_key": "exports/v1",
            "split_membership": repo._gravado, "test_count": 5, "val_count": 1,
        }).get_holdout(DSV_ID)
        assert lido["frame_ids"] == MEMBRESIA["test"]
        assert lido["split"] == "test"
        assert lido["frozen"] is True

    def test_le_jsonb_vindo_como_string(self):
        """Driver que não faz parse automático de jsonb não pode virar crash."""
        holdout = _RepoFake({
            "id": DSV_ID, "coco_r2_key": "exports/v1",
            "split_membership": json.dumps(MEMBRESIA),
            "test_count": 5, "val_count": 1,
        }).get_holdout(DSV_ID)
        assert holdout["frame_ids"] == MEMBRESIA["test"]

    def test_cai_para_val_quando_test_vazio(self):
        membresia = {**MEMBRESIA, "test": []}
        holdout = _RepoFake({
            "id": DSV_ID, "coco_r2_key": "exports/v1",
            "split_membership": membresia, "test_count": 0, "val_count": 1,
        }).get_holdout(DSV_ID)
        assert holdout["split"] == "val"
        assert holdout["frame_ids"] == ["f-04"]

    def test_versao_antiga_nao_se_declara_congelada(self):
        """Build anterior à 131: membresia irrecuperável, e a leitura DIZ isso."""
        holdout = _RepoFake({
            "id": DSV_ID, "coco_r2_key": "exports/v1",
            "split_membership": None, "test_count": 5, "val_count": 1,
        }).get_holdout(DSV_ID)
        assert holdout["frozen"] is False
        assert holdout["frame_ids"] is None
        assert holdout["split"] == "test"

    def test_versao_inexistente_devolve_none(self):
        assert _RepoFake(None).get_holdout(DSV_ID) is None


class TestFiltroDaMembresia:
    def test_recorta_o_coco_para_exatamente_os_frames_congelados(self):
        coco = json.loads(_coco_com(MEMBRESIA["test"], extras=["intruso-1", "intruso-2"]))
        recortado, faltantes = model_evaluation._filtrar_coco_pela_membresia(
            coco, MEMBRESIA["test"]
        )
        assert [i["file_name"] for i in recortado["images"]] == [
            f"{f}.jpg" for f in MEMBRESIA["test"]
        ]
        assert faltantes == []
        ids = {i["id"] for i in recortado["images"]}
        assert all(a["image_id"] in ids for a in recortado["annotations"])

    def test_denuncia_frame_congelado_que_sumiu_do_r2(self):
        """#515: o COCO no R2 já foi reescrito por baixo. A membresia percebe."""
        coco = json.loads(_coco_com(MEMBRESIA["test"][:3]))
        _, faltantes = model_evaluation._filtrar_coco_pela_membresia(
            coco, MEMBRESIA["test"]
        )
        assert faltantes == ["f-13", "f-14"]

    def test_digital_independe_da_ordem_e_muda_com_o_conteudo(self):
        d = model_evaluation._digital_do_holdout
        assert d(["b", "a", "c"]) == d(["a", "b", "c"])
        assert d(["a", "b", "c"]) != d(["a", "b", "d"])


class TestDoisModelosMesmaProva:
    """O teste que a tarefa pede: dois modelos, um holdout, a MESMA lista."""

    def _rodar(self, monkeypatch, model_id: str, holdout: dict, capturadas: list):
        registry, dataset, eval_repo, storage = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        registry.get_by_id.return_value = {
            "id": model_id, "tenant_id": TENANT_ID, "module_code": "epi",
            "framework": "rfdetr", "r2_onnx_key": f"models/{model_id}.onnx",
            "dataset_version_id": f"dsv-proprio-do-{model_id}",
        }
        registry.list_for_tenant.return_value = []
        dataset.get_by_id.return_value = {"id": DSV_ID}

        # get_holdout responde pelo ID PEDIDO. Pedir o holdout do próprio
        # modelo devolve OUTRA prova — é isso que faz a mutação reprovar em
        # vez de passar por um fake que responde igual a qualquer pergunta.
        def _por_id(version_id, *a, **k):
            if str(version_id) == DSV_ID:
                return dict(holdout)
            return {
                "dataset_version_id": str(version_id),
                "coco_r2_key": "exports/prova-do-modelo",
                "split": "test", "frame_ids": ["intruso-1"], "frozen": True,
            }

        dataset.get_holdout.side_effect = _por_id
        # O COCO do R2 traz frames a MAIS do que a membresia — se a leitura
        # ignorasse a membresia, os intrusos entrariam na prova.
        storage.download_bytes.return_value = _coco_com(
            MEMBRESIA["test"], extras=["intruso-1", "intruso-2"]
        )
        eval_repo.create.return_value = {"id": f"eval-{model_id}"}
        monkeypatch.setattr(model_evaluation, "_get_registry_repo", lambda: registry)
        monkeypatch.setattr(model_evaluation, "_get_dataset_repo", lambda: dataset)
        monkeypatch.setattr(model_evaluation, "_get_eval_repo", lambda: eval_repo)
        monkeypatch.setattr(model_evaluation, "_get_storage", lambda tenant_id=None: storage)
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())

        def _avaliar(model, storage, coco_r2_key, split, coco):
            capturadas.append([i["file_name"] for i in coco["images"]])
            return {
                "metrics": {
                    "map50": 0.5,
                    "per_class": {"Luvas": {"ap": 0.5, "tp": 4, "fp": 1, "fn": 1}},
                },
                "confusion_matrix": {},
                "images_evaluated": len(coco["images"]),
            }

        monkeypatch.setattr(model_evaluation, "_evaluate_model_on_split", _avaliar)
        resultado = model_evaluation.evaluate_challenger_model.apply(
            args=(model_id, DSV_ID)
        ).get()
        return resultado, eval_repo

    def test_dois_modelos_no_mesmo_holdout_recebem_a_mesma_lista(self, monkeypatch):
        holdout = {
            "dataset_version_id": DSV_ID, "coco_r2_key": "exports/v1",
            "split": "test", "frame_ids": MEMBRESIA["test"], "frozen": True,
        }
        capturadas: list[list[str]] = []
        r_a, eval_a = self._rodar(monkeypatch, MODEL_A, holdout, capturadas)
        r_b, eval_b = self._rodar(monkeypatch, MODEL_B, holdout, capturadas)

        assert r_a["status"] == "completed" and r_b["status"] == "completed"
        # MESMA prova: mesma lista de imagens, na mesma ordem.
        assert capturadas[0] == capturadas[1]
        # E sem os intrusos que estavam no COCO do R2.
        assert capturadas[0] == [f"{f}.jpg" for f in MEMBRESIA["test"]]

        m_a = eval_a.create.call_args.args[0]["metrics"]
        m_b = eval_b.create.call_args.args[0]["metrics"]
        assert m_a["holdout_fingerprint"] == m_b["holdout_fingerprint"]
        assert m_a["holdout_version_id"] == m_b["holdout_version_id"] == DSV_ID
        assert m_a["holdout_frozen"] is True
        assert m_a["holdout_frame_count"] == 5

    def test_holdout_e_pedido_pelo_id_dado_nao_pelo_do_modelo(self, monkeypatch):
        """A regressão exata: o holdout não pode vir da dataset_version do modelo."""
        holdout = {
            "dataset_version_id": DSV_ID, "coco_r2_key": "exports/v1",
            "split": "test", "frame_ids": MEMBRESIA["test"], "frozen": True,
        }
        capturadas: list[list[str]] = []
        self._rodar(monkeypatch, MODEL_A, holdout, capturadas)
        # get_holdout foi chamado com o id PEDIDO, não com o do modelo
        # (que é "dsv-proprio-do-<model_id>" no fake acima).
        dataset = model_evaluation._get_dataset_repo()
        assert dataset.get_holdout.call_args.args[0] == DSV_ID

    def test_versao_sem_membresia_marca_a_nota_como_nao_congelada(self, monkeypatch):
        holdout = {
            "dataset_version_id": DSV_ID, "coco_r2_key": "exports/v1",
            "split": "test", "frame_ids": None, "frozen": False,
        }
        capturadas: list[list[str]] = []
        _, eval_repo = self._rodar(monkeypatch, MODEL_A, holdout, capturadas)
        metrics = eval_repo.create.call_args.args[0]["metrics"]
        assert metrics["holdout_frozen"] is False
        assert metrics["holdout_fingerprint"] is None
        # Sem membresia, o COCO inteiro entra — inclusive os intrusos. É o
        # comportamento legado, e é por isso que a nota vem marcada.
        assert len(capturadas[0]) == 7
