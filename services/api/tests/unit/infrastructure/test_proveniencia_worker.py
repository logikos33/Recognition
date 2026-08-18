"""Proveniência do worker no próprio job — o "/livez" de quem não fala HTTP.

O celery-worker do DEV nunca teve source git e ficou 5 dias atrás da develop:
conserto nenhum chegava ao pod, e a verificação olhava o /livez da API — o
sensor certo, no serviço errado. O hash do runner responde a pergunta que
importa: o pod rodou QUAL código?
"""
from app.infrastructure.queue.tasks.training import worker_provenance


def test_commit_vem_da_env_do_railway(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "c2cfb0e9abc")
    assert worker_provenance("x")["worker_commit"] == "c2cfb0e9abc"


def test_sem_env_devolve_unknown_denunciando_railway_up(monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    assert worker_provenance("x")["worker_commit"] == "unknown"


def test_hash_muda_quando_o_runner_muda(monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    a = worker_provenance("codigo antigo")["runner_sha256"]
    b = worker_provenance("codigo com onnx explicito")["runner_sha256"]
    assert a != b, "o hash tem que distinguir versões do runner"
    assert worker_provenance("codigo antigo")["runner_sha256"] == a, "deve ser estável"


def test_hash_e_curto_o_bastante_para_caber_em_log(monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    assert len(worker_provenance("x")["runner_sha256"]) == 16
