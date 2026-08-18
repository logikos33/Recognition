"""Os três consertos da noite de 18/08 — cada um mata uma falha real.

Padrão comum: dois escritores, um recurso, zero dono. Ocorreu três vezes
(conta admin, error_message, artefato R2). Ver D-166 e o registro da rodada.
"""
import pytest
from unittest.mock import MagicMock


class TestArtefatoPreflight:
    """Valida a FONTE (objetos soltos), não o zip — que é cache derivado e o
    dispatch reconstrói/sobrescreve a cada disparo. Quatro pods morreram na
    época 0 porque o v5-relabel só tinha o zip e os prefixos estavam vazios."""

    def _mk(self, keys_por_prefixo, monkeypatch):
        from app.infrastructure.queue.tasks import training as t
        st = MagicMock()
        st.list_keys.side_effect = lambda pre: keys_por_prefixo.get(pre, [])
        monkeypatch.setattr(t, "get_storage", lambda **k: st)
        return t._preflight_artefato("tenant", "base")

    def _completo(self):
        return {
            f"base/{sp}/": [f"base/{sp}/_annotations.coco.json", f"base/{sp}/a.jpg"]
            for sp in ("train", "val", "test")
        }

    def test_fonte_completa_passa(self, monkeypatch):
        assert self._mk(self._completo(), monkeypatch) is None

    def test_prefixo_vazio_e_recusado_nomeando_o_split(self, monkeypatch):
        # Exatamente o caso do v5-relabel: só o zip, prefixos vazios.
        motivo = self._mk({}, monkeypatch)
        assert motivo and "train/ vazio" in motivo and "test/ vazio" in motivo

    def test_split_sem_o_json_e_recusado_com_a_contagem(self, monkeypatch):
        keys = self._completo()
        keys["base/train/"] = ["base/train/a.jpg", "base/train/b.jpg"]
        motivo = self._mk(keys, monkeypatch)
        assert motivo and "train/ sem _annotations.coco.json (2 objetos)" in motivo

    def test_zip_presente_NAO_salva_fonte_vazia(self, monkeypatch):
        # O zip existir não conta: o dispatch vai sobrescrevê-lo.
        motivo = self._mk({"base/dataset.zip": ["base/dataset.zip"]}, monkeypatch)
        assert motivo is not None


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
