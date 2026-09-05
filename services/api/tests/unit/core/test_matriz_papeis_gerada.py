"""
A matriz que o front usa nos testes É a do registry — sem drift.

`apps/frontend/src/test/e2e/matriz-papeis.json` é um ARTEFATO GERADO de
`permissions_for_role()`. Quatro suítes do front julgam o produto contra ela
(`papeis.test.ts`, `navPorPerfil.test.ts`, `Estudio.test.tsx`,
`front-novo-perfis.spec.ts`) e NENHUMA delas percebe se o arquivo envelheceu:
todas leem o JSON e comparam o front com o JSON. Se o registry mudar e o JSON
não, as quatro continuam verdes medindo uma matriz que não existe mais.

Não é hipótese: quando este teste foi escrito, o arquivo estava seis chaves
atrás do registry — `quality:read`/`quality:write` tinham entrado e nunca
foram regeradas.

Este é o único ponto que compara os DOIS lados. Se ficar vermelho, regere:

    cd services/api && python3 -c "import json,sys; sys.path.insert(0,'.'); \\
      from app.core.permissions import ROLE_ORDER, permissions_for_role; \\
      print(json.dumps({r: permissions_for_role(r) for r in ROLE_ORDER}, \\
      indent=1, ensure_ascii=False))" > \\
      ../../apps/frontend/src/test/e2e/matriz-papeis.json
"""
import json
from pathlib import Path

from app.core.permissions import ROLE_ORDER, permissions_for_role

MATRIZ = (
    Path(__file__).resolve().parents[5]
    / "apps" / "frontend" / "src" / "test" / "e2e" / "matriz-papeis.json"
)


def test_o_arquivo_existe_onde_o_front_o_procura():
    """Se o caminho mudar, este teste cai — e não passa medindo nada."""
    assert MATRIZ.is_file(), f"matriz não encontrada em {MATRIZ}"


def test_matriz_do_front_igual_ao_registry():
    gerada = json.loads(MATRIZ.read_text(encoding="utf-8"))
    esperada = {papel: permissions_for_role(papel) for papel in ROLE_ORDER}

    assert set(gerada) == set(esperada), "papéis divergem do ROLE_ORDER"
    divergencias = {
        papel: {
            "só no arquivo": sorted(set(gerada[papel]) - set(esperada[papel])),
            "só no registry": sorted(set(esperada[papel]) - set(gerada[papel])),
        }
        for papel in esperada
        if sorted(gerada[papel]) != sorted(esperada[papel])
    }
    assert divergencias == {}, (
        "matriz-papeis.json está atrasada em relação a permissions.py — "
        f"regere (ver docstring): {divergencias}"
    )
