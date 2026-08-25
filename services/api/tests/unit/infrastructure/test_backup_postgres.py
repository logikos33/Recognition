"""Backup do banco: segredo fora do argv, drill de verdade, silêncio denunciado.

Auditado em 2026-08-25: a spec de 20/08 pedia pg_dump→R2 2×/dia com drill, e
NADA existia. No R2 havia um único objeto — um dump manual de 5 dias antes.
Zero pg_dump no código, e `postgresql` nem estava no nixPkgs.

Os três testes que importam aqui:

  · a senha NUNCA em argv (aparece em `ps aux`);
  · drill que reprova dump truncado — senão o que se monitora é o upload;
  · idade que falha fechada — "não consegui verificar" ≠ "está tudo bem".
"""
from __future__ import annotations

import gzip
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.queue.tasks import backup as mod


class TestSegredoNuncaEmArgv:
    URL = "postgresql://usuario:S3nh4%40Secreta@db.exemplo.com:5433/recognition"

    def test_senha_vai_por_env_nao_por_argumento(self):
        args, env = mod._ambiente_pg(self.URL)
        linha = " ".join(args)
        assert "S3nh4" not in linha, (
            "senha em argv aparece em `ps aux` e em qualquer coletor de processo"
        )
        assert env["PGPASSWORD"] == "S3nh4@Secreta", "e tem de estar decodificada"

    def test_host_porta_usuario_e_banco_vao_por_argumento(self):
        args, _env = mod._ambiente_pg(self.URL)
        assert args == [
            "--host", "db.exemplo.com",
            "--port", "5433",
            "--username", "usuario",
            "--dbname", "recognition",
        ]

    def test_tls_exigido_por_padrao(self):
        """Railway recusa conexão sem TLS; sem isto o dump falha por rede."""
        _args, env = mod._ambiente_pg(self.URL)
        assert env["PGSSLMODE"] == "require"

    def test_url_sem_host_e_recusada(self):
        with pytest.raises(ValueError):
            mod._ambiente_pg("postgresql:///semhost")

    def test_porta_padrao_quando_ausente(self):
        args, _ = mod._ambiente_pg("postgresql://u:p@host/db")
        assert "5432" in args


class TestDrillReprovaDumpQuebrado:
    """Dump truncado, dump vazio e dump bom são todos objetos plausíveis no
    bucket. Só o drill distingue."""

    def _dump(self, *, marcadores=True, rodape=True, tamanho=1_000_000) -> bytes:
        partes = [b"-- PostgreSQL database dump\n"]
        if marcadores:
            partes += [b"CREATE TABLE public.alerts (\n);\n",
                       b"CREATE TABLE public.cameras (\n);\n"]
        partes.append(b"x" * tamanho)
        if rodape:
            partes.append(b"\n-- PostgreSQL database dump complete\n")
        return gzip.compress(b"".join(partes))

    def test_dump_integro_passa(self):
        r = mod._drill(self._dump())
        assert r["ok"] is True
        assert r["tem_rodape"] is True
        assert len(r["marcadores"]) == 2

    def test_dump_truncado_reprova(self):
        """Timeout ou disco cheio cortam o arquivo ANTES do rodapé — é
        exatamente o que o pg_dump só escreve depois de terminar."""
        r = mod._drill(self._dump(rodape=False))
        assert r["ok"] is False
        assert r["tem_rodape"] is False

    def test_dump_sem_as_tabelas_centrais_reprova(self):
        r = mod._drill(self._dump(marcadores=False))
        assert r["ok"] is False
        assert r["marcadores"] == []

    def test_dump_pequeno_demais_reprova(self):
        """Um dump de banco vazio comprime para quase nada e pareceria ok."""
        r = mod._drill(self._dump(tamanho=10))
        assert r["ok"] is False

    def test_objeto_que_nao_e_gzip_explode_em_vez_de_passar(self):
        with pytest.raises(Exception):  # noqa: B017 — qualquer erro serve; o que não pode é passar
            mod._drill(b"isto nao e um gzip")


class TestIdadeFalhaFechada:
    def _com_chaves(self, chaves):
        armazenamento = MagicMock()
        armazenamento.list_keys.return_value = chaves
        return patch.object(mod, "_storage", return_value=armazenamento)

    def test_sem_backup_nenhum_e_insalubre(self):
        with self._com_chaves([]):
            r = mod.idade_do_backup_mais_novo()
        assert r["saudavel"] is False
        assert "nenhum" in r["motivo"]

    def test_backup_recente_e_saudavel(self):
        agora = datetime.now(timezone.utc)
        chave = f"{mod.PREFIXO_BACKUP}/{agora.strftime('%Y-%m-%dT%H%M%SZ')}.sql.gz"
        with self._com_chaves([chave]):
            r = mod.idade_do_backup_mais_novo()
        assert r["saudavel"] is True
        assert r["idade_horas"] < 1

    def test_backup_velho_demais_e_insalubre(self):
        velho = datetime.now(timezone.utc) - timedelta(hours=mod.IDADE_MAXIMA_H + 2)
        chave = f"{mod.PREFIXO_BACKUP}/{velho.strftime('%Y-%m-%dT%H%M%SZ')}.sql.gz"
        with self._com_chaves([chave]):
            r = mod.idade_do_backup_mais_novo()
        assert r["saudavel"] is False

    def test_pega_o_MAIS_NOVO_e_nao_o_primeiro_da_lista(self):
        agora = datetime.now(timezone.utc)
        velho = agora - timedelta(days=9)
        chaves = [
            f"{mod.PREFIXO_BACKUP}/{agora.strftime('%Y-%m-%dT%H%M%SZ')}.sql.gz",
            f"{mod.PREFIXO_BACKUP}/{velho.strftime('%Y-%m-%dT%H%M%SZ')}.sql.gz",
        ]
        with self._com_chaves(list(reversed(chaves))):
            r = mod.idade_do_backup_mais_novo()
        assert r["saudavel"] is True

    def test_erro_de_storage_NAO_vira_saudavel(self):
        """A regra da rodada inteira: falha não devolve o valor que significa
        'tudo bem'."""
        armazenamento = MagicMock()
        armazenamento.list_keys.side_effect = RuntimeError("R2 fora do ar")
        with patch.object(mod, "_storage", return_value=armazenamento):
            r = mod.idade_do_backup_mais_novo()
        assert r["saudavel"] is False

    def test_nome_ilegivel_nao_vira_saudavel(self):
        with self._com_chaves([f"{mod.PREFIXO_BACKUP}/qualquer-coisa.sql.gz"]):
            r = mod.idade_do_backup_mais_novo()
        assert r["saudavel"] is False


class TestTarefaNaoMenteSucesso:
    def test_sem_pg_dump_na_imagem_devolve_erro_explicito(self):
        with patch.object(mod.shutil, "which", return_value=None), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://u:p@h/d"}):
            r = mod.backup_database.apply().get()
        assert r["status"] == "erro"
        assert "pg_dump" in r["motivo"]

    def test_sem_database_url_devolve_erro(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_PUBLIC_URL", raising=False)
        r = mod.backup_database.apply().get()
        assert r["status"] == "erro"


class TestOAgendamentoExiste:
    def test_backup_esta_no_schedule_seguro_2x_por_dia(self):
        from app.infrastructure.queue.celery_app import SAFE_BEAT_SCHEDULE

        entrada = SAFE_BEAT_SCHEDULE.get("backup-postgres")
        assert entrada, "sem entrada no beat o backup nunca roda sozinho"
        assert entrada["task"] == "tasks.backup.backup_database"
        assert entrada["schedule"] == 43200, "12h = 2x/dia"

    def test_o_modulo_esta_nos_includes_do_celery(self):
        from pathlib import Path

        import app.infrastructure.queue.celery_app as ca

        codigo = Path(ca.__file__).read_text(encoding="utf-8")
        assert "app.infrastructure.queue.tasks.backup" in codigo, (
            "task fora do include: o beat agenda e o worker responde "
            "'unregistered task'"
        )

    def test_nixpacks_traz_o_postgresql(self):
        """Sem o binário na imagem a tarefa roda e devolve erro para sempre."""
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[5]
        nix = (raiz / "nixpacks.toml").read_text(encoding="utf-8")
        assert "postgresql_18" in nix, (
            "o servidor é PostgreSQL 18.6 e o pg_dump não pode ser mais antigo"
        )
