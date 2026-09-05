"""#753 — o `Migrations collision guard` reprova PR de todo mundo, sem teste.

Ele existe porque os PRs #279 e #281 criaram, em worktrees paralelas, dois
`108_*.sql`; só não colidiu porque alguém renumerou a tempo — por sorte, não
por CI. E colisão de numeração já derrubou o startup da API uma vez (ADR-0021).

Os testes montam repositórios git DE VERDADE (base + clone com `origin/develop`)
e provam que o gate reprova a colisão. Repo real e não dublê porque a metade
difícil deste gate é justamente o git: `merge-base` contra a base, e não HEAD~1
— um dublê de `git diff` testaria o dublê.

Prova de que mordem (mutações que matam cada um):
  - `if len(filenames) > 1` -> `if False`            → colisão dentro do PR
  - `if base_filename is None: continue` -> sempre   → colisão contra a base
  - `merge_base` -> `"HEAD~1"`                       → o teste de 2 commits
  - `except RemoteCheckUnavailable` re-levantando    → best-effort virou fatal
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parents[5]
_GATE = _RAIZ / "scripts" / "ci" / "check_migrations_collision.py"

sys.path.insert(0, str(_GATE.parent))
import check_migrations_collision as gate  # noqa: E402

_GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *_GIT_ID, *args], cwd=cwd, check=True, capture_output=True)


def _escrever(repo: pathlib.Path, nome: str) -> None:
    (repo / "infra" / "migrations").mkdir(parents=True, exist_ok=True)
    (repo / "infra" / "migrations" / nome).write_text("SELECT 1;\n", encoding="utf-8")


@pytest.fixture
def pr(tmp_path: pathlib.Path) -> pathlib.Path:
    """Clone com `origin/develop` e uma branch de trabalho — a forma do CI.

    A base já tem 100_base.sql: é contra ela que a colisão é medida.
    """
    base = tmp_path / "base"
    base.mkdir()
    _git(base, "init", "-q", "-b", "develop")
    _escrever(base, "100_base.sql")
    _git(base, "add", "-A")
    _git(base, "commit", "-qm", "base")

    trabalho = tmp_path / "trabalho"
    _git(tmp_path, "clone", "-q", str(base), str(trabalho))
    _git(trabalho, "checkout", "-q", "-b", "feature")
    return trabalho


def _rodar(monkeypatch, capsys, repo: pathlib.Path, *extra: str) -> tuple[int, str]:
    monkeypatch.setattr(gate, "REPO_ROOT", repo)
    codigo = gate.main(["--base-ref", "develop", *extra])
    return codigo, capsys.readouterr().out


class TestReprovaOCasoRuim:
    def test_dois_arquivos_com_o_MESMO_prefixo_no_mesmo_PR_reprovam(self, pr, monkeypatch, capsys):
        """O quase-acidente dos PRs #279/#281, agora dentro de um PR só."""
        _escrever(pr, "101_a.sql")
        _escrever(pr, "101_b.sql")
        _git(pr, "add", "-A")
        _git(pr, "commit", "-qm", "duas 101")
        codigo, saida = _rodar(monkeypatch, capsys, pr, "--skip-remote-check")
        assert codigo == 1, saida
        assert "NESTE MESMO PR" in saida and "'101'" in saida

    def test_prefixo_que_JA_EXISTE_na_base_reprova(self, pr, monkeypatch, capsys):
        _escrever(pr, "100_minha_versao.sql")
        _git(pr, "add", "-A")
        _git(pr, "commit", "-qm", "colide com a base")
        codigo, saida = _rodar(monkeypatch, capsys, pr, "--skip-remote-check")
        assert codigo == 1, saida
        assert "já existe em origin/develop" in saida and "100_base.sql" in saida

    def test_colisao_no_PRIMEIRO_de_dois_commits_ainda_reprova(self, pr, monkeypatch, capsys):
        """⚠️ O caso que HEAD~1 perde. Migration nova no commit 1, mexida
        qualquer no commit 2: `git diff HEAD~1` não enxerga mais o arquivo.
        Mutação que mata: trocar o merge-base por HEAD~1."""
        _escrever(pr, "100_minha_versao.sql")
        _git(pr, "add", "-A")
        _git(pr, "commit", "-qm", "migration")
        (pr / "LEIAME.md").write_text("nota\n", encoding="utf-8")
        _git(pr, "add", "-A")
        _git(pr, "commit", "-qm", "doc")
        codigo, saida = _rodar(monkeypatch, capsys, pr, "--skip-remote-check")
        assert codigo == 1, saida
        assert "100_minha_versao.sql" in saida

    def test_colisao_confirmada_contra_OUTRO_PR_aberto_reprova(self, pr, monkeypatch, capsys):
        """Best-effort não quer dizer inofensivo: resposta obtida com sucesso e
        prefixo batendo tem de falhar o build."""
        _escrever(pr, "101_minha.sql")
        _git(pr, "add", "-A")
        _git(pr, "commit", "-qm", "nova")
        monkeypatch.setattr(
            gate, "check_open_prs",
            lambda *a, **k: (["101_minha.sql: prefixo '101' já foi adicionado pelo PR aberto #999"], 1),
        )
        codigo, saida = _rodar(monkeypatch, capsys, pr)
        assert codigo == 1, saida
        assert "#999" in saida


class TestAceitaOCasoBom:
    def test_prefixo_livre_passa(self, pr, monkeypatch, capsys):
        _escrever(pr, "101_nova.sql")
        _git(pr, "add", "-A")
        _git(pr, "commit", "-qm", "nova")
        codigo, saida = _rodar(monkeypatch, capsys, pr, "--skip-remote-check")
        assert codigo == 0, saida
        assert "OK" in saida

    def test_PR_sem_migration_nenhuma_passa(self, pr, monkeypatch, capsys):
        (pr / "LEIAME.md").write_text("nada de migrations\n", encoding="utf-8")
        _git(pr, "add", "-A")
        _git(pr, "commit", "-qm", "doc")
        codigo, saida = _rodar(monkeypatch, capsys, pr, "--skip-remote-check")
        assert codigo == 0 and "nada para checar" in saida

    def test_arquivo_MODIFICADO_nao_conta_como_adicionado(self, pr, monkeypatch, capsys):
        """Só ADD colide; editar uma migration existente é outro problema."""
        _escrever(pr, "100_base.sql")
        (pr / "infra" / "migrations" / "100_base.sql").write_text("SELECT 2;\n")
        _git(pr, "add", "-A")
        _git(pr, "commit", "-qm", "edita")
        codigo, saida = _rodar(monkeypatch, capsys, pr, "--skip-remote-check")
        assert codigo == 0, saida

    def test_API_fora_do_ar_vira_AVISO_e_nao_derruba_o_build(self, pr, monkeypatch, capsys):
        """Escolha deliberada do script: falso-negativo ocasional > CI vermelho
        por instabilidade de rede. Mas tem de aparecer no log."""
        _escrever(pr, "101_nova.sql")
        _git(pr, "add", "-A")
        _git(pr, "commit", "-qm", "nova")

        def _explode(*a, **k):
            raise gate.RemoteCheckUnavailable("sem rede")

        monkeypatch.setattr(gate, "check_open_prs", _explode)
        codigo, saida = _rodar(monkeypatch, capsys, pr)
        assert codigo == 0, saida
        assert "AVISOS" in saida and "sem rede" in saida


class TestPartesPuras:
    def test_duplicata_dentro_do_PR(self):
        assert gate.check_within_pr_duplicates({"108": ["a.sql", "b.sql"]})
        assert gate.check_within_pr_duplicates({"108": ["a.sql"]}) == []

    def test_colisao_contra_a_base(self):
        adicionadas = {"108": ["infra/migrations/108_nova.sql"]}
        assert gate.check_against_base(adicionadas, "develop", {"108": "108_velha.sql"})
        assert gate.check_against_base(adicionadas, "develop", {"107": "107_x.sql"}) == []

    @pytest.mark.parametrize(
        "nome,esperado",
        [
            ("infra/migrations/108_a.sql", "108"),
            ("108_a.sql", "108"),
            ("infra/migrations/README.md", None),
            ("infra/migrations/sem_numero.sql", None),
        ],
    )
    def test_prefixo_do_nome(self, nome, esperado):
        assert gate._prefix_of(nome) == esperado
