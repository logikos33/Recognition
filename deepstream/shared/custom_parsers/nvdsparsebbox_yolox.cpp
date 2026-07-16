/*
 * Custom bounding-box parser do DeepStream (nvinfer) para detector YOLOX ONNX
 * (Apache 2.0) — task-088.
 *
 * PROBLEMA QUE RESOLVE: o `nvinfer` do DeepStream não sabe decodificar a saída
 * "raw" do YOLOX (tensor [N, 5+C] em grade, precisa de decode grid+stride) —
 * o SDK só traz sample de parser YOLO via Triton (mais pesado). Sem este
 * parser, um engine YOLOX não produz detecção alguma no pipeline DeepStream.
 *
 * CONTRATO: espelha EXATAMENTE a decodificação de
 * services/api/app/domain/detectors/onnx_yolox.py (`_decode_positions` +
 * score = obj_conf * max_class_conf), para que o comportamento no edge
 * (DeepStream/TensorRT) case com o servido na nuvem (ONNXRuntime).
 *
 * Ordem dos anchors (convenção YOLOX, igual ao _decode_positions do Python):
 *   para cada stride em {8, 16, 32}: grade (netH/stride) x (netW/stride),
 *   row-major (hy externo, wx interno). Blocos concatenados nessa ordem.
 *
 * Saída em coordenadas da REDE (netW x netH); o nvinfer reescala para o frame.
 *
 * ⚠️ Validado: compila, carrega no nvinfer, decodifica o Nº certo de caixas e
 *    integra no pipeline. A validação "detecta objeto de verdade" depende de um
 *    checkpoint YOLOX com pesos bons (o checkpoint público testado tem
 *    objectness quebrado — ver task-084/088). Reutilizável com o modelo real
 *    da task-086.
 */
#include <algorithm>
#include <cmath>
#include <vector>

#include "nvdsinfer_custom_impl.h"

// COCO 80 classes (mesmo do onnx_yolox.py). O modelo próprio (task-086) pode ter
// outro nº de classes — parametrizar via num-detected-classes no config e ler
// C a partir do shape do tensor de saída (feito abaixo, não hard-coded em 80).
static const int kStrides[] = {8, 16, 32};
static const int kNumStrides = 3;

extern "C" bool NvDsInferParseCustomYolox(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList);

extern "C" bool NvDsInferParseCustomYolox(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList)
{
    if (outputLayersInfo.empty() || outputLayersInfo[0].buffer == nullptr) {
        return false;
    }

    const NvDsInferLayerInfo& layer = outputLayersInfo[0];
    const float* data = reinterpret_cast<const float*>(layer.buffer);

    // Descobre nº de canais (5 + numClasses) a partir do shape do tensor:
    // saída esperada [N, C] (ou [1, N, C]). C = último eixo.
    const NvDsInferDims& dims = layer.inferDims;
    int channels = 0;
    if (dims.numDims >= 1) {
        channels = static_cast<int>(dims.d[dims.numDims - 1]);
    }
    if (channels <= 5) {
        return false;  // shape inesperado — não arrisca ler lixo
    }
    const int numClasses = channels - 5;

    const int netW = static_cast<int>(networkInfo.width);
    const int netH = static_cast<int>(networkInfo.height);

    size_t anchor = 0;
    for (int s = 0; s < kNumStrides; ++s) {
        const int stride = kStrides[s];
        const int gh = netH / stride;
        const int gw = netW / stride;
        for (int hy = 0; hy < gh; ++hy) {
            for (int wx = 0; wx < gw; ++wx, ++anchor) {
                const float* p = data + anchor * static_cast<size_t>(channels);

                const float obj = p[4];
                // argmax da classe
                int bestC = 0;
                float bestP = p[5];
                for (int c = 1; c < numClasses; ++c) {
                    if (p[5 + c] > bestP) {
                        bestP = p[5 + c];
                        bestC = c;
                    }
                }
                const float score = obj * bestP;

                // threshold por classe (pré-cluster) vindo do config do nvinfer
                float thresh = 0.5f;
                if (bestC < static_cast<int>(detectionParams.perClassPreclusterThreshold.size())) {
                    thresh = detectionParams.perClassPreclusterThreshold[bestC];
                }
                if (score < thresh) {
                    continue;
                }

                // decode grid+stride (idêntico ao _decode_positions do Python)
                const float cx = (p[0] + static_cast<float>(wx)) * stride;
                const float cy = (p[1] + static_cast<float>(hy)) * stride;
                const float w = std::exp(p[2]) * stride;
                const float h = std::exp(p[3]) * stride;

                NvDsInferObjectDetectionInfo det;
                det.classId = static_cast<unsigned int>(bestC);
                det.left = cx - w * 0.5f;
                det.top = cy - h * 0.5f;
                det.width = w;
                det.height = h;
                det.detectionConfidence = std::min(std::max(score, 0.0f), 1.0f);
                objectList.push_back(det);
            }
        }
    }

    return true;
}

/* Valida a assinatura em tempo de compilação. */
CHECK_CUSTOM_PARSE_FUNC_PROTOTYPE(NvDsInferParseCustomYolox);
