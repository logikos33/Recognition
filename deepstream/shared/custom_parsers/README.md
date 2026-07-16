# Custom bbox parsers — DeepStream nvinfer (task-088)

Parsers de bounding-box para o `nvinfer` do DeepStream decodificar saídas de
detector que o SDK não entende nativamente. O SDK 7.1 só traz sample de YOLO via
Triton (servidor sidecar, mais pesado) — nada para o `nvinfer` nativo com
RF-DETR/YOLOX. Sem parser, um engine desses **não produz detecção alguma** no
pipeline.

## `nvdsparsebbox_yolox.cpp`

Decodifica a saída "raw" do YOLOX (tensor `[N, 5+C]` em grade → decode
grid+stride, `score = obj_conf * max_class_conf`). É um port **linha-a-linha** de
`services/api/app/domain/detectors/onnx_yolox.py` (`_decode_positions`), para que
o edge (DeepStream/TensorRT) case com o servido na nuvem (ONNXRuntime).

### Build (no edge, Jetson + DeepStream 7.1)
```bash
make                      # gera libnvdsparsebbox_yolox.so
# DEEPSTREAM_DIR / CUDA_DIR sobrescrevíveis se instalado noutro path
```
Requer g++ + headers do DeepStream (`sources/includes`) + CUDA toolkit
(`/usr/local/cuda/include` — o header do TensorRT puxa `cuda_runtime_api.h`).

### Wiring
Ver `config_infer_yolox.template.txt` — referenciar via `parse-bbox-func-name` +
`custom-lib-path`, com `cluster-mode=2` (o nvinfer faz o NMS; o parser só
decodifica).

### Estado da validação (2026-07-16, no Orin NX real)
- ✅ Compila, carrega no `nvinfer`, é invocado, decodifica os anchors e produz
  bounding boxes válidas no pipeline (confirmado: com `pre-cluster-threshold=0.0`,
  1443/1443 frames do vídeo de amostra produziram caixas com coords válidas,
  reescaladas corretamente pelo DeepStream para o frame; pipeline @ ~222 FPS,
  sem crash, `App run successful`).
- ⏳ Validação "detecta objeto de verdade" **pendente de modelo com pesos bons**:
  o único checkpoint YOLOX público testável sem torch (Megvii 2021) tem
  objectness quebrado (~0.0004) → score ~0, classe aleatória. Reusar este parser
  com o modelo próprio da task-086.
- ⏳ Follow-up de rigor: teste de paridade numérica exata parser (C++) vs
  `onnx_yolox.py` (Python) na mesma engine/frame, quando houver modelo funcional.

### Ainda não existe
Parser equivalente para **RF-DETR** (saída estilo DETR `pred_logits`/`pred_boxes`
— sem grid/stride, decode diferente). Escrever quando RF-DETR virar candidato a
default no edge (ver benchmark task-084).
