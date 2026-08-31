"""
Regressão: rota /api/* inexistente devolvia 200 "API online" em vez de 404.

Root bug (crash de cenário): serve_frontend (catch-all SPA em app/__init__.py)
respondia 200 pra QUALQUER path sem casar rota, inclusive sob /api/. Um hook
com prefixo de versão errado (ex.: /cameras/x/scenario em vez de
/v1/cameras/x/scenario) caía nesse catch-all, recebia 200 sem a chave `data`
esperada, e o caller (api.get<T>) não tinha como distinguir "rota errada" de
"sucesso vazio" — o crash acontecia na leitura de `res.data.scenario`.

Fix: path.startswith("api/") no catch-all responde 404 no envelope de erro
padrão do repo (app.core.responses.error), nunca mais 200.
"""


def test_api_path_nao_casado_devolve_404_json(client):
    resp = client.get("/api/rota-que-nao-existe")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "error" in body


def test_api_path_com_barra_final_devolve_404_json(client):
    resp = client.get("/api/v1/algo/que/nao/existe")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False


def test_root_sem_frontend_dist_continua_200(client):
    # Path fora de /api/* (SPA fallback) não regride — continua 200.
    resp = client.get("/")

    assert resp.status_code == 200
