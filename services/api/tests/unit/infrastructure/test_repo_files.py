"""find_repo_file — regressão do IndexError("6") no worker (layout da
imagem difere do checkout; ver repo_files.py)."""
import pytest

from app.infrastructure.queue.tasks.repo_files import find_repo_file


def test_localiza_executor_de_propagacao() -> None:
    path = find_repo_file("training", "propagate_seeded.py")
    assert path.is_file()


def test_localiza_executor_de_treino() -> None:
    path = find_repo_file("training", "vast", "remote_train.py")
    assert path.is_file()


def test_arquivo_inexistente_falha_com_mensagem_legivel() -> None:
    with pytest.raises(FileNotFoundError, match="training/arquivo-que-nao-existe.py"):
        find_repo_file("training", "arquivo-que-nao-existe.py")
