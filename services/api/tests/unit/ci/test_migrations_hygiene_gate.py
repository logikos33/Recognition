"""#753 — o guard-rail de higiene de migrations tinha cobertura de raspão.

O que ele guarda (cada item nasceu de incidente real):
  - prefixo NNN duplicado (ADR-0021: colisão de numeração derrubou o startup);
  - migration NOVA com DROP/DELETE/TRUNCATE ou reescrita de `password_hash`
    (#683/#694: a 049 apagava histórico de contagem; a 027/040 devolviam a
    senha do superadmin ao hash do git a cada deploy);
  - segundo diretório `migrations/` na raiz (PRs #214/#215).

Nada disso era exercitado contra um repositório DEFEITUOSO — só contra a
develop saudável, onde todo gate passa, inclusive um gate quebrado.

Prova de que mordem (mutações que matam cada um):
  - `if len(files) < 2 or prefix in baseline` -> `if True`     → duplicata
  - `if motivo is None: continue` -> `continue` incondicional  → destrutiva
  - `if legado.exists()` -> `if False`                         → dir legado
  - remover a checagem de fantasma da baseline                 → fantasma
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parents[5]
_GATE = _RAIZ / "scripts" / "ci" / "check_migrations_hygiene.py"

sys.path.insert(0, str(_GATE.parent))
from check_migrations_hygiene import (  # noqa: E402
    check_baseline_destrutiva_nao_tem_fantasma,
    check_duplicate_prefixes,
    check_no_duplicate_migrations_dir,
    check_no_new_destructive_migration,
    checar,
)

BENIGNA = "ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS x TEXT;\n"


@pytest.fixture
def raiz(tmp_path: pathlib.Path) -> pathlib.Path:
    """Repositório forjado com uma migration inocente — ponto de partida verde."""
    d = tmp_path / "infra" / "migrations"
    d.mkdir(parents=True)
    (d / "001_inicial.sql").write_text(BENIGNA, encoding="utf-8")
    return tmp_path


def _mig(raiz: pathlib.Path, nome: str, sql: str = BENIGNA) -> None:
    (raiz / "infra" / "migrations" / nome).write_text(sql, encoding="utf-8")


class TestPrefixoDuplicado:
    def test_prefixo_duplicado_NOVO_reprova(self, raiz):
        _mig(raiz, "002_a.sql")
        _mig(raiz, "002_b.sql")
        erros = check_duplicate_prefixes(raiz)
        assert erros, "duas migrations com prefixo 002 passaram"
        assert "'002'" in erros[0] and "002_a.sql" in erros[0] and "002_b.sql" in erros[0]

    def test_prefixo_na_baseline_e_tolerado(self, raiz):
        """A dívida histórica do 052 é forward-only — não pode nascer vermelha."""
        _mig(raiz, "052_a.sql")
        _mig(raiz, "052_b.sql")
        (raiz / "infra" / "migrations" / ".duplicate-prefix-baseline").write_text(
            "# comentário ignorado\n\n052\n", encoding="utf-8"
        )
        assert check_duplicate_prefixes(raiz) == []

    def test_baseline_de_um_prefixo_nao_isenta_OUTRO(self, raiz):
        """Mutação que mata: `if len(files) < 2 or baseline` -> `if baseline`."""
        _mig(raiz, "052_a.sql")
        _mig(raiz, "052_b.sql")
        _mig(raiz, "099_a.sql")
        _mig(raiz, "099_b.sql")
        (raiz / "infra" / "migrations" / ".duplicate-prefix-baseline").write_text("052\n")
        erros = check_duplicate_prefixes(raiz)
        assert len(erros) == 1 and "'099'" in erros[0]

    def test_diretorio_de_migrations_ausente_reprova(self, tmp_path):
        """Sem diretório não é 'tudo certo' — é a pergunta não ter sido feita."""
        assert check_duplicate_prefixes(tmp_path)


class TestMigrationDestrutiva:
    @pytest.mark.parametrize(
        "sql",
        [
            "DROP TABLE public.counted_products;",
            "DELETE FROM public.detections WHERE 1=1;",
            "TRUNCATE public.frames;",
            "ALTER TABLE public.users DROP COLUMN legado;",
            "UPDATE public.users SET password_hash = '$2b$fixo' WHERE email='admin';",
        ],
    )
    def test_migration_nova_destrutiva_reprova(self, raiz, sql):
        """Estas nem RODAM em produção (guarda de redeploy as pula) — o gate
        existe para dizer isso antes do merge, não depois do deploy silencioso."""
        _mig(raiz, "002_perigosa.sql", sql)
        erros = check_no_new_destructive_migration(raiz)
        assert erros, f"passou: {sql!r}"
        assert "002_perigosa.sql" in erros[0]

    def test_comando_destrutivo_COMENTADO_nao_reprova(self, raiz):
        """Falso positivo transforma gate em ruído — e ruído vira `|| true`."""
        _mig(raiz, "002_ok.sql", "-- DROP TABLE antiga; (não fazemos mais isso)\n" + BENIGNA)
        assert check_no_new_destructive_migration(raiz) == []

    def test_definicao_de_coluna_password_hash_nao_reprova(self, raiz):
        """`password_hash VARCHAR(255)` é criar coluna, não reescrever senha."""
        _mig(raiz, "002_ok.sql", "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);")
        assert check_no_new_destructive_migration(raiz) == []

    def test_baseline_isenta_o_arquivo_nomeado_e_so_ele(self, raiz):
        _mig(raiz, "049_legado.sql", "DELETE FROM public.counted_products;")
        _mig(raiz, "150_nova.sql", "DELETE FROM public.counted_products;")
        (raiz / "infra" / "migrations" / ".destructive-baseline").write_text("049_legado.sql\n")
        erros = check_no_new_destructive_migration(raiz)
        assert len(erros) == 1 and "150_nova.sql" in erros[0]

    def test_baseline_com_fantasma_reprova(self, raiz):
        """Entrada sem arquivo = a lista não encolheu sozinha quando o arquivo sumiu."""
        (raiz / "infra" / "migrations" / ".destructive-baseline").write_text("999_que_nao_existe.sql\n")
        erros = check_baseline_destrutiva_nao_tem_fantasma(raiz)
        assert erros and "999_que_nao_existe.sql" in erros[0]


class TestDiretorioLegado:
    def test_segundo_diretorio_de_migrations_reprova(self, raiz):
        (raiz / "migrations").mkdir()
        erros = check_no_duplicate_migrations_dir(raiz)
        assert erros and "legado" in erros[0]

    def test_sem_diretorio_legado_passa(self, raiz):
        assert check_no_duplicate_migrations_dir(raiz) == []


class TestConjunto:
    def test_repositorio_forjado_saudavel_passa(self, raiz):
        assert checar(raiz) == []

    def test_um_defeito_de_cada_familia_aparece_junto(self, raiz):
        _mig(raiz, "002_a.sql")
        _mig(raiz, "002_b.sql")
        _mig(raiz, "003_apaga.sql", "TRUNCATE public.frames;")
        (raiz / "migrations").mkdir()
        erros = checar(raiz)
        assert len(erros) == 3, erros


class TestFronteiraDoProcesso:
    def test_repo_real_passa_com_saida_zero(self):
        p = subprocess.run(
            [sys.executable, str(_GATE)], capture_output=True, text=True, timeout=120
        )
        assert p.returncode == 0, p.stdout + p.stderr
        assert "OK" in p.stdout
