# D-066 · Achado adjacente: preproc do detector servido diverge do YOLOX stock (potencial bug de inferência)

**Seção:** Rodada 5 — Triagem dos 679 frames RVB (05/08 · Claude) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**05/08 · Claude**

`app/domain/detectors/onnx_yolox.py::_preprocess` normaliza **RGB / 255**. O
YOLOX stock do Megvii (o mesmo `yolox_s.onnx` que `register_pretrained_models.py`
baixa e registra como `yolox-s-coco-pretrained`) espera **BGR 0-255** — é também
o preproc do edge (landmine "preproc BGR 0-255"). Empiricamente, RGB/255 **zera**
as detecções desse modelo (0 pessoas); BGR 0-255 acha a pessoa a 0.851.

Ou o modelo servido em produção é **re-exportado com a normalização embutida**
(então `_preprocess` casa e está OK), ou a inferência do **modelo COCO
pré-treinado servido está quebrada**. **Verificar** — fora do escopo desta
rodada, registrado como P1 a confirmar.
