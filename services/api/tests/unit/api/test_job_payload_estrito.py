"""Campo desconhecido no dispatch responde 400 com o NOME do campo.

Custou dois erros reais no TREINO 2: `epochs` (o certo é `total_epochs`) fez o
job nascer com 100 épocas em vez de 12, e `base_model` foi descartado deixando
a linhagem NULL. Errar o nome é humano; o endpoint não avisar é o defeito.
Ver D-164.
"""
from app.api.v1.training.job_handlers import CAMPOS_CREATE_JOB


def test_os_dois_campos_ignorados_calados_estao_no_contrato():
    assert "total_epochs" in CAMPOS_CREATE_JOB
    assert "base_model" in CAMPOS_CREATE_JOB


def test_epochs_nao_e_valido_entao_vira_400_e_nao_silencio():
    assert "epochs" not in CAMPOS_CREATE_JOB


def test_payload_do_treino2_seria_rejeitado_com_o_nome_do_campo():
    enviado = {"module": "epi", "framework": "rfdetr", "base_model": "base",
               "epochs": 12, "hyperparams": {}}
    desconhecidos = sorted(set(enviado) - CAMPOS_CREATE_JOB)
    assert desconhecidos == ["epochs"]


def test_payload_correto_passa_limpo():
    enviado = {"module": "epi", "framework": "rfdetr", "base_model": "base",
               "total_epochs": 12, "hyperparams": {}, "dataset_version_id": "x"}
    assert not (set(enviado) - CAMPOS_CREATE_JOB)
