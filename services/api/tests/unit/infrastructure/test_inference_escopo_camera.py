"""O escopo salvo na aba "Modelos por câmera" tem de valer no pipeline (#519).

Antes: `_resolve_camera_model` lia o deployment SÓ para tirar `model_id` —
`config.classes` era ignorado. O admin marcava 3 classes, salvava, e o worker
continuava alertando as 6. A tela prometia um escopo que o pipeline não cumpria.
"""
from app.infrastructure.queue.tasks import inference


def _det(classe: str) -> dict:
    return {"class": classe, "confidence": 0.9, "bbox": [1, 2, 3, 4]}


def _com_cache(camera_id: str, classes) -> None:
    with inference._camera_detector_lock:
        inference._camera_detectors[camera_id] = {
            "model_id": "m1", "detector": object(), "classes": classes,
        }


def teardown_function() -> None:
    with inference._camera_detector_lock:
        inference._camera_detectors.clear()


def test_classe_fora_do_escopo_nao_passa():
    _com_cache("cam-1", frozenset({"Luvas", "Botas"}))
    saida = inference._no_escopo_da_camera("cam-1", [_det("Luvas"), _det("Óculos")])
    assert [d["class"] for d in saida] == ["Luvas"]


def test_sem_escopo_gravado_tudo_passa():
    """None = o dono nunca abriu a aba. Silenciar tudo apagaria 28 câmeras."""
    _com_cache("cam-1", None)
    entrada = [_det("Luvas"), _det("Óculos")]
    assert inference._no_escopo_da_camera("cam-1", entrada) == entrada


def test_camera_sem_cache_tambem_deixa_passar():
    entrada = [_det("Luvas")]
    assert inference._no_escopo_da_camera("cam-desconhecida", entrada) == entrada


def test_escopo_vazio_e_escolha_explicita():
    """`[]` é o dono dizendo "esta câmera não reconhece nada" — não é ausência."""
    _com_cache("cam-1", frozenset())
    assert inference._no_escopo_da_camera("cam-1", [_det("Luvas")]) == []


def test_escopo_sai_do_config_do_deployment():
    escopo = inference._escopo_do_deployment({"config": {"classes": ["Luvas", "Botas"]}})
    assert escopo == frozenset({"Luvas", "Botas"})


def test_deployment_sem_a_chave_nao_inventa_escopo():
    assert inference._escopo_do_deployment({"config": {}}) is None
    assert inference._escopo_do_deployment({}) is None
    assert inference._escopo_do_deployment(None) is None


def test_escopo_vazio_no_config_sobrevive_como_vazio():
    assert inference._escopo_do_deployment({"config": {"classes": []}}) == frozenset()
