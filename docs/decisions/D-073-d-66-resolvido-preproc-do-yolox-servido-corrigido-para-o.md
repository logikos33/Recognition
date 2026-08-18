# D-073 · D-66 resolvido: preproc do YOLOX servido corrigido para o contrato stock (PR #320)

**Seção:** Rodada 06/08 — pipeline de treino (varredura R2, coleta, bloqueadores da anotação) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**06/08 · Claude**

Investigação fechou o [[D-66]]: o upstream Megvii não faz BGR→RGB nem `/255`
(`yolox/data/data_augment.py::preproc`); **todos** os ONNX servidos ou treinados
pelo produto saem do export oficial (`register_pretrained_models.py` baixa o
binário stock; `training/vast/train_yolox.py` exporta via
`yolox.tools.export_onnx`) — **nenhum modelo depende do preproc errado**, então
o fix é direto, sem knob por-modelo e sem migration. RF-DETR auditado no mesmo
passo: já estava correto (ImageNet mean/std, RGB [0,1], conforme upstream).
Testes agora fixam o contrato certo (0-255, BGR, pad 114 sem normalizar).
