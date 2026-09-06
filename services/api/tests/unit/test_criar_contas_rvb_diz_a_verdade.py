"""O texto do script de provisionamento é o que decide se a senha do papel
expira — e ele mentiu.

`scripts/criar_contas_rvb.py` é a ÚNICA informação que a pessoa que cria as
contas da RVB tem na hora de escolher `RVB_EXIGIR_TROCA_SENHA`. Enquanto a
tela de troca não existia, ele dizia (docstring e `print` da execução) "a TELA
dessa troca ainda não existe — sem ela, a pessoa não passa da tela de login",
e por isso recomendava NÃO exigir a troca. Correto na época.

A tela passou a existir (issue #819): o 403 `password_change_required` abre,
na própria tela de login, o formulário de nova senha. O texto do script não
acompanhou — e continuava mandando deixar a senha combinada valendo para
sempre, que é a issue #764 de volta.

Este teste amarra as duas pontas: ENQUANTO a tela tratar o 403, o script não
pode dizer que ela não existe. Se um dia a tela sair, o primeiro assert cai e
alguém tem de decidir de novo — em vez de o texto envelhecer calado.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
TELA = RAIZ / "apps" / "frontend" / "src" / "app" / "acesso" / "Entrar.tsx"
SCRIPT = RAIZ / "scripts" / "criar_contas_rvb.py"


def test_a_tela_de_troca_trata_o_403() -> None:
    """A âncora: sem isto o resto deste arquivo não quer dizer nada."""
    tela = TELA.read_text(encoding="utf-8")
    assert "password_change_required" in tela
    assert "/auth/change-password" in tela


def test_o_script_nao_diz_que_a_tela_nao_existe() -> None:
    texto = SCRIPT.read_text(encoding="utf-8")
    for frase in ("tela de troca ainda não existe", "TELA dessa troca ainda não", "a TELA de troca ainda não existe"):
        assert frase not in texto, f"script ainda afirma que a tela não existe: {frase!r}"


def test_o_script_manda_exigir_a_troca() -> None:
    """O caminho de copiar-e-colar tem de fechar a #764, não reabri-la."""
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "RVB_EXIGIR_TROCA_SENHA=true \\" in texto, (
        "a linha de uso da docstring precisa incluir RVB_EXIGIR_TROCA_SENHA=true"
    )
    assert "#764" in texto, "o aviso de senha permanente precisa citar a issue"
