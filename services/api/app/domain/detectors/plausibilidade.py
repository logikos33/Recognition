"""Guarda de plausibilidade geométrica: a caixa tem de ter o tamanho e a forma
da classe que ela afirma ser.

ORIGEM — observação do dono do produto na folha de contato de campo
(`docs/quality/FOLHA-CONTATO-CAMPO-V2.html`): "algumas cenas captam corretamente
o uso incorreto de máscara e outras acabam identificando UMA PESSOA INTEIRA como
uso incorreto de máscara". O remédio que ele propôs — "a máscara fica no rosto" —
é o que este módulo implementa: um envelope por classe que rejeita a caixa cujo
tamanho ou forma não cabem no que o anotador humano desenha para aquela classe.

CAUSA PROVÁVEL (medida no commit d7452f6d, não corrigida aqui): o dataset
v10b-freeze tem 3.489 imagens de RECORTE DE PESSOA e 2 de quadro inteiro. No
recorte (~583x696) uma máscara ocupa fração muito maior do enquadramento; servido
em quadro cheio 1920x1080, o modelo procura algo com aquela proporção e acha a
pessoa inteira. Isto é um curativo no caminho servido, não o conserto do treino.

━━ POR QUE DUAS DIMENSÕES ━━
Só tamanho não basta. O caso que o dono apontou — `Uso incorreto de mascara`
120x173px — cabe no envelope de TAMANHO (173/1080 = 0,160 contra o teto 0,209) e
só é pego pela FORMA: h/w = 1,44 contra o p99 humano de 1,13. Uma caixa de rosto
é horizontal (h/w ~0,74); uma de tronco é quadrada ou vertical.

━━ ESCALA: por que o envelope não é em pixels ━━
O envelope foi medido em quadros 1920x1080. Guardá-lo em pixels absolutos o
tornaria válido só nessa resolução. Duas convenções diferentes, de propósito:

  · TAMANHO em FRAÇÃO DO QUADRO (w/W, h/H). A mesma máscara física a 1920x1080 e
    a 1280x720 ocupa a mesma fração — o envelope atravessa resolução.
  · FORMA em h/w de PIXELS, nunca de fração. Normalizar deforma a razão pelo
    aspecto do quadro: 82x62px (h/w = 0,76) vira 0,0427x0,0574 = 1,34 em fração.
    O mesmo objeto mudaria de "horizontal" para "vertical" só por trocar a
    unidade. Em pixels quadrados, h/w é a forma real e independe da resolução.

⛔ E POR ISSO ESTA GUARDA NÃO VIVE NO DETECTOR. Em `predict()` não há como saber
se o frame recebido é um quadro cheio ou um RECORTE de pessoa. Num recorte de
583x696 uma máscara legítima ocupa ~15% da largura, contra os ~4% do quadro
cheio: o envelope de fração-do-quadro a rejeitaria em massa. A guarda é chamada
só de `tasks/inference.py`, cujas duas entradas (`inference_loop` via
`cv2.VideoCapture` e `retroactive_inference` via frame do R2) são quadros
cheios por construção. Quem for servir recorte um dia precisa de outro envelope,
não deste.

━━ O ENVELOPE (derivado, não chutado) ━━
Mesmo universo do export de treino (`annotation_repository._COVERAGE_UNIVERSE`):
só anotação HUMANA (`source='manual'`) ou pré-anotação APROVADA
(`reviewed_by NOT NULL`) — sem isso o envelope seria derivado das pré-anotações
da MÁQUINA e assaria o próprio defeito dentro da guarda. Decodifica o offset de
namespace de classe (`class_namespace.TENANT_CLASS_ID_OFFSET = 100000`): `4` e
`100004` são a MESMA classe, e contá-las separado foi o que produziu a tabela
errada que motivou esta investigação.

    SELECT c.name, COUNT(*) n,
      percentile_cont(0.99) WITHIN GROUP (ORDER BY a.width)  AS wn_p99,
      percentile_cont(0.99) WITHIN GROUP (ORDER BY a.height) AS hn_p99,
      percentile_cont(0.99) WITHIN GROUP (
          ORDER BY (a.height*tf.height)/(a.width*tf.width))  AS hw_p99
      FROM frame_annotations a
      JOIN yolo_classes c
        ON c.id = CASE WHEN a.class_id >= 100000
                       THEN a.class_id - 100000 ELSE a.class_id END
      JOIN training_frames tf ON tf.id = a.frame_id
     WHERE tf.tenant_id = %(tenant)s AND tf.module_code = 'epi'
       AND tf.is_annotated = TRUE AND tf.curation_status <> 'excluida'
       AND c.archived_at IS NULL
       AND (COALESCE(a.source,'manual') = 'manual' OR a.reviewed_by IS NOT NULL)
       AND tf.width >= 1280          -- só quadro cheio; recorte tem outra escala
     GROUP BY c.name;

`frame_annotations.width/height` já são fração do quadro (CHECK 0..1 na 003), daí
`wn_p99`/`hn_p99` saírem prontos; a forma multiplica de volta por `tf.width/
tf.height` para voltar a pixels.

━━ A FOLGA, e por que ela é assimétrica ━━
TAMANHO leva folga de 1,5x sobre o p99. O tamanho aparente varia com a distância
da pessoa à câmera, e 240 caixas (a classe mais rica) não cobrem a cauda de quem
passa colado na lente; sem folga a guarda cortaria pessoa próxima legítima.
FORMA não leva folga. h/w é invariante à escala — uma máscara tem a mesma
proporção a 3m e a 15m —, então o p99 já é o extremo real da classe e não há
cauda de distância para acomodar. Folga de 1,5 na forma elevaria o teto de
`Uso incorreto de mascara` para 1,70 e deixaria passar exatamente o caso de 1,44
que o dono apontou: seria uma guarda que não guarda.

━━ CLASSES FRÁGEIS ━━
`n` fica na tabela de propósito. Abaixo de ~30 caixas o p99 é praticamente o
máximo da amostra, e o envelope é uma aposta em poucos exemplos — `Botas` (13) e
`Uso incorreto de mascara` (12) estão nesse regime. Mantidos mesmo assim porque
a folga de 1,5x no tamanho absorve o erro de amostragem e a forma observada é
estreita; quando a anotação crescer, re-rodar a query acima e atualizar aqui.

Classe SEM linha nesta tabela não tem envelope e PASSA SEMPRE (fail-open). Das 11
classes que o modelo servido emite, 6 não têm nenhuma anotação humana em quadro
cheio (`Luvas`, `Óculos`, `Sem Luvas`, `Sem Óculos`, `Sem mascara`, `Capacete`) —
inventar limite para elas seria chutar, que é o que esta guarda existe para não
fazer.
"""
import logging

logger = logging.getLogger(__name__)

#: Folga sobre o p99 de TAMANHO. Só tamanho: ver "A FOLGA" no docstring.
FOLGA_TAMANHO = 1.5

#: classe → (n_amostras, wn_p99, hn_p99, hw_p99)
#: Derivado do tenant RVB (63c219d8) em 2026-09-02 pela query do docstring.
ENVELOPE: dict[str, tuple[int, float, float, float]] = {
    "Protetor auditivo":        (240, 0.1104, 0.1855, 1.83),
    "mascara":                  (36,  0.0964, 0.0917, 1.27),
    "Sem protetor de ouvido":   (25,  0.0598, 0.1211, 1.33),
    "Botas":                    (13,  0.0808, 0.0957, 1.90),
    "Uso incorreto de mascara": (12,  0.0734, 0.1391, 1.13),
}


def motivo_implausivel(
    classe: str, bbox, frame_w: int, frame_h: int
) -> str | None:
    """Motivo pelo qual a caixa não cabe na classe, ou None se ela cabe.

    `bbox` é [x, y, w, h] em PIXELS do quadro original — o contrato de
    `Detector.predict` (`domain/detectors/base.py`, `_BBOX_UNIDADE =
    pixels_xywh_frame_original`). Passar bbox normalizado aqui faria toda caixa
    parecer minúscula e a guarda aprovaria tudo em silêncio.

    Sem envelope para a classe → None (passa). Quadro de dimensão inválida →
    None: sem W/H não há fração possível, e recusar detecção por falta de
    metadado do frame seria apagar alerta por um bug nosso.
    """
    env = ENVELOPE.get(classe)
    if env is None:
        return None
    if not frame_w or not frame_h or frame_w <= 0 or frame_h <= 0:
        return None

    try:
        _, _, w, h = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return "degenerada"

    _, wn_max, hn_max, hw_max = env
    if w / frame_w > wn_max * FOLGA_TAMANHO:
        return "larga"
    if h / frame_h > hn_max * FOLGA_TAMANHO:
        return "alta"
    # Forma em pixels, NUNCA em fração — normalizar deforma a razão pelo
    # aspecto do quadro e troca "horizontal" por "vertical" (ver docstring).
    if h / w > hw_max:
        return "forma"
    return None


def filtrar_implausiveis(
    detections: list[dict], frame_w: int, frame_h: int, camera_id: str = "?"
) -> list[dict]:
    """Remove as detecções geometricamente implausíveis, contando o que caiu.

    Toda rejeição vira log estruturado com classe, tamanho e motivo: uma guarda
    que descarta em silêncio é a próxima investigação de "por que o dashboard
    está vazio" — o mesmo erro que `_no_escopo_da_camera` já cometeu uma vez.
    """
    mantidas: list[dict] = []
    rejeitadas: list[tuple[str, str, float, float]] = []
    for d in detections:
        classe = str(d.get("class", ""))
        bbox = d.get("bbox") or [0, 0, 0, 0]
        motivo = motivo_implausivel(classe, bbox, frame_w, frame_h)
        if motivo is None:
            mantidas.append(d)
        else:
            rejeitadas.append((classe, motivo, float(bbox[2]), float(bbox[3])))

    for classe, motivo, w, h in rejeitadas:
        logger.info(
            "plausibilidade_rejeitou: camera=%s classe=%s motivo=%s caixa=%.0fx%.0f "
            "hw=%.2f quadro=%dx%d",
            camera_id, classe, motivo, w, h, (h / w) if w else 0.0,
            frame_w, frame_h,
        )
    if detections and not mantidas:
        # 100%% fora costuma ser envelope desalinhado com a taxonomia servida
        # (ou frame de RECORTE chegando aqui), não um turno inteiro implausível.
        logger.warning(
            "plausibilidade_descartou_tudo: camera=%s n=%d classes=%s quadro=%dx%d "
            "— envelope é de QUADRO CHEIO; recorte de pessoa cai todo aqui",
            camera_id, len(detections),
            sorted({str(d.get("class")) for d in detections})[:6], frame_w, frame_h,
        )
    return mantidas
