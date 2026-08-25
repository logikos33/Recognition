"""Sem User-Agent, o GraphQL da RunPod responde 403 — e não é a chave.

Medido em 2026-08-25 contra a API real: a MESMA chave devolve 403
"error code: 1010" sem User-Agent e 200 com qualquer um, inclusive
"python-requests/2.32". O Cloudflare responde 403 até SEM autenticação
nenhuma, então o erro não fala nada sobre a credencial — e manda quem depura
procurar chave revogada, que foi o que aconteceu.
"""
from app.infrastructure.gpu.runpod_client import RunPodClient


def test_toda_requisicao_leva_user_agent():
    cliente = RunPodClient.__new__(RunPodClient)
    cliente.api_key = "rpa_teste"  # noqa: S105 — valor de teste, não segredo

    headers = cliente._headers()

    assert headers.get("User-Agent"), (
        "sem User-Agent o Cloudflare da RunPod devolve 403 e o erro não menciona UA"
    )
    assert headers["Authorization"] == "Bearer rpa_teste"
