"""Os três consertos da noite de 18/08 — cada um mata uma falha real.

Padrão comum: dois escritores, um recurso, zero dono. Ocorreu três vezes
(conta admin, error_message, artefato R2). Ver D-166 e o registro da rodada.
"""
import io
import zipfile
import pytest
from unittest.mock import MagicMock


class TestArtefatoPreflight:
    """Três pods queimaram a época 0 lendo um dataset.zip de 22 bytes."""

    def _mk(self, blob, monkeypatch):
        from app.infrastructure.queue.tasks import training as t
        st = MagicMock()
        st.download_bytes.return_value = blob
        monkeypatch.setattr(t, "get_storage", lambda **k: st)
        return t._preflight_artefato("tenant", "chave/qualquer")

    def test_zip_vazio_e_recusado_com_o_tamanho(self, monkeypatch):
        vazio = io.BytesIO()
        with zipfile.ZipFile(vazio, "w"):
            pass
        motivo = self._mk(vazio.getvalue(), monkeypatch)
        assert motivo and "sem nenhuma entrada" in motivo

    def test_zero_bytes_e_recusado(self, monkeypatch):
        assert "vazio (0 bytes)" in (self._mk(b"", monkeypatch) or "")

    def test_zip_sem_o_json_que_o_runner_procura_lista_as_pastas(self, monkeypatch):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("val/_annotations.coco.json", "{}")   # nome errado de pasta
        motivo = self._mk(buf.getvalue(), monkeypatch)
        assert motivo and "train/_annotations.coco.json" in motivo
        assert "Pastas presentes" in motivo and "val" in motivo

    def test_zip_bom_passa_limpo(self, monkeypatch):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("train/_annotations.coco.json", "{}")
            z.writestr("valid/_annotations.coco.json", "{}")
            z.writestr("test/_annotations.coco.json", "{}")
        assert self._mk(buf.getvalue(), monkeypatch) is None


class TestVersaoReadyImutavel:
    """v5-relabel (23,8 MB, ready) virou 22 bytes por um re-export."""

    def _guard(self, status, monkeypatch):
        from app.infrastructure.queue.tasks import versioning_v2 as v2
        repo = MagicMock()
        repo.get_version_by_label.return_value = {"id": "abc", "status": status}
        monkeypatch.setattr(v2, "_get_dataset_repo", lambda: repo)
        return v2._recusa_se_versao_pronta(MagicMock(), "t", "d", "v5-relabel")

    def test_build_sobre_versao_ready_e_RECUSADO(self, monkeypatch):
        with pytest.raises(ValueError) as e:
            self._guard("ready", monkeypatch)
        assert "imutável" in str(e.value)

    def test_versao_building_ou_error_segue_normal(self, monkeypatch):
        assert self._guard("building", monkeypatch) is None
        assert self._guard("error", monkeypatch) is None

    def test_falha_de_leitura_nao_bloqueia_build_legitimo(self, monkeypatch):
        from app.infrastructure.queue.tasks import versioning_v2 as v2
        monkeypatch.setattr(v2, "_get_dataset_repo", MagicMock(side_effect=RuntimeError))
        assert v2._recusa_se_versao_pronta(MagicMock(), "t", "d", "v") is None
