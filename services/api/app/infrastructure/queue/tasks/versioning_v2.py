"""
Recognition — Dataset Versioning v2 (COCO export, WS-A3).

build_dataset_version_v2: snapshot de frames rotulados do tenant (reviewed
primeiro), split por grupo — video_id quando existe; senão camera_id+dia
de captura (frames soltos de NVR, sem video_id — evita leakage entre
train/val/test quando frames quase-idênticos da mesma câmera no mesmo dia
cairiam em splits diferentes); 'frame:{id}' só como último recurso quando
nem video_id nem camera_id+data são resolvíveis (log de aviso — não
deveria acontecer com o schema atual). Conversão de anotações YOLO
normalizadas (cx/cy/w/h 0..1) para COCO absoluto via width/height do
frame (fallback: baixa a imagem do R2 e lê dimensões com PIL —
ThreadPoolExecutor(10), ajuste #11), upload para R2 em
{R2Prefix.DATASET_EXPORTS}/{tenant_id}/{dataset_id}/{version}/... e
INSERT em dataset_versions via DatasetRepository.create_version_v2 com
linhagem completa (status building→ready|error).

Filtros do export: frames com curation_status='excluida' nunca entram no
pool (curation 'duvida' CONTINUA entrando — ainda não há decisão humana);
anotações cuja classe custom do tenant está arquivada (yolo_classes.
archived_at) são excluídas do COCO, mesmo que o frame continue no pool.

Corrige os bugs da task legada (versioning.py): key mismatch no copy e
ausência de INSERT. A task legada permanece para compat; esta é a oficial.
"""
import hashlib
import json
import traceback
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any

from app.constants import DatasetVersionStatus, ExportFormat, R2Prefix
from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

# Nome da categoria raiz do COCO. Não é uma classe do modelo: é a âncora que
# ancora a contagem de classes do RF-DETR (ver onde `categories` é montado).
_ANCORA_COCO = "recognition"

_DIM_FALLBACK_WORKERS = 10
_SPLIT_NAMES = ("train", "val", "test")
_COCO_FILENAME = "_annotations.coco.json"


def _get_dataset_repo():
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.dataset_repository import (
        DatasetRepository,
    )
    return DatasetRepository(DatabasePool.get_instance())


def _get_annotation_repo():
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.annotation_repository import (
        AnnotationRepository,
    )
    return AnnotationRepository(DatabasePool.get_instance())


def _get_storage(tenant_id: str | None = None):
    from app.infrastructure.storage.local_storage import get_storage
    return get_storage(tenant_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snapshot_labeled_frames(
    annotation_repo, tenant_id: str, module_code: str
) -> list[dict[str, Any]]:
    """Snapshot de frames rotulados do tenant+módulo, reviewed primeiro.

    AI_NOTE (ajuste #4): LEFT JOIN training_videos — frames com video_id
    NULL (upload/auto/nvr) ENTRAM no snapshot; INNER JOIN os excluiria.

    Câmera arquivada (is_active=FALSE) NÃO alimenta mais o treino: arquivar
    uma câmera que não faz parte do reconhecimento precisa tirar o material
    dela do modelo, senão o arquivamento é só cosmético e o modelo continua
    aprendendo de cena descartada. LEFT JOIN + `camera_id IS NULL OR
    is_active` preserva frame de upload/vídeo, que não tem câmera.

    camera_id + captured_at (fallback created_at) incluídos para o split
    por câmera/dia de frames soltos de NVR (video_id NULL) — ver
    _group_key.

    curation_status != 'excluida' (migration 110): frame descartado na
    curadoria nunca entra no pool de export — mesmo filtro padrão da casa
    (ver frame_repository.py list_frames/list_by_camera). 'duvida' CONTINUA
    entrando — ainda não há decisão humana; excluir preventivamente só
    encolheria o pool sem necessidade (registrado no PR).
    """
    return annotation_repo._execute(
        """
        SELECT tf.id, tf.video_id, tf.filename, tf.r2_key, tf.frame_number,
               tf.width, tf.height, tf.module_code, tf.camera_id,
               tf.captured_at, tf.created_at,
               (tf.validated_at IS NOT NULL) AS is_reviewed
          FROM training_frames tf
          LEFT JOIN training_videos tv ON tv.id = tf.video_id
          LEFT JOIN public.cameras cam ON cam.id = tf.camera_id
         WHERE tf.tenant_id = %s
           AND tf.module_code = %s
           AND tf.is_annotated = TRUE
           AND tf.curation_status != 'excluida'
           AND (tf.camera_id IS NULL OR cam.is_active = TRUE)
         ORDER BY (tf.validated_at IS NOT NULL) DESC,
                  tf.video_id, tf.frame_number
        """,
        (str(tenant_id), module_code),
    )


def _fetch_annotations(
    annotation_repo, tenant_id: str, module_code: str,
    somente_humano: bool = False,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Anotações YOLO (normalizadas) dos frames rotulados do tenant+módulo.

    Gate de procedência (D-39, migration 095): dataset de treino só recebe
    anotação HUMANA — direta (source='manual', default histórico da coluna;
    nenhum dado existente some) ou pré-anotação de IA APROVADA por humano
    (reviewed_by setado em accept_pre_annotations no aceite, ~annotation_
    repository.py linha 296). Uma pré-anotação sem revisão (reviewed_by
    NULL) nunca alimenta o treino.

    class_name vem da PRÓPRIA LINHA de frame_annotations (task-077), nunca de
    um JOIN — mesma regra que AnnotationRepository.get_by_frame documenta.
    Reconstruir o nome via yolo_classes trocava o rótulo de toda anotação
    feita com classe do CATÁLOGO: class_id 6 ("Óculos", module_classes) caía
    em yolo_classes.id=6 ("mascara" do tenant) e o dataset saía ensinando
    máscara com foto de óculos. Medido no DEV antes do fix: 111 boxes com
    rótulo trocado e 19 descartados em silêncio — 130 de 599 (21,7%).

    O LEFT JOIN em yolo_classes sobrou só para o que ele sabe responder:
    se a classe CUSTOM do tenant foi aposentada (archived_at). Ele é
    escopado por tenant_id — sem isso, class_id=1 de um frame do RVB
    resolvia para "hardhat" de OUTRO tenant (leitura cross-tenant, C-01).
    Classe de catálogo (class_id < 100000) não passa por ele.

    Mapeamento de classe: frame_annotations.class_id é um inteiro solto
    (sem FK — migration 103): índice 0-based do catálogo global
    (module_classes) OU id namespaced de classe custom do tenant
    (class_namespace.TENANT_CLASS_ID_OFFSET=100000 + yolo_classes.id — ver
    domain/services/class_namespace.py). O CASE abaixo desfaz o offset só
    quando ele existe (class_id >= 100000); classes de catálogo (<100000)
    mantêm o comportamento legado. `c.archived_at IS NULL` exclui do
    export anotações cuja classe tenant foi arquivada (yolo_classes.
    archived_at, migration 110 — "aposentar" uma classe sem apagar caixas
    já salvas): a classe continua existindo, só não alimenta mais treino.

    curation_status != 'excluida': mesmo filtro do pool de frames (ver
    _snapshot_labeled_frames) — sem efeito prático isolado (o frame já
    não estaria em `frames`), mas mantém as duas queries com o mesmo
    universo e evita trabalho desperdiçado.
    """
    rows = annotation_repo._execute(
        """
        SELECT a.frame_id, a.class_id, a.x_center, a.y_center,
               a.width, a.height, a.class_name,
               a.source, a.reviewed_by
          FROM frame_annotations a
          JOIN training_frames tf ON tf.id = a.frame_id
          LEFT JOIN public.cameras cam ON cam.id = tf.camera_id
          LEFT JOIN yolo_classes c
            ON a.class_id >= 100000
           AND c.id = a.class_id - 100000
           AND c.tenant_id = tf.tenant_id
         WHERE tf.tenant_id = %s
           AND tf.module_code = %s
           AND tf.is_annotated = TRUE
           AND tf.curation_status != 'excluida'
           AND (tf.camera_id IS NULL OR cam.is_active = TRUE)
           AND (a.class_id < 100000
                OR (c.id IS NOT NULL AND c.archived_at IS NULL))
         ORDER BY a.frame_id, a.id
        """,
        (str(tenant_id), module_code),
    )
    # Universo ANTES de qualquer filtro: é o que distingue "frame que perdeu as
    # caixas por filtro" de "frame que nunca teve caixa" — o primeiro sai do
    # dataset, o segundo é negativo legítimo e fica. Ver _sem_rotulos_de_frame.
    tinham_caixa = {str(row["frame_id"]) for row in rows}

    if somente_humano:
        # v12 (#536): a caixa que veio de PROPOSTA ACEITA carrega a geometria do
        # MODELO, não a do humano — aceitar com uma tecla confirma a CLASSE, não
        # a CAIXA. Treinar nela ensina o modelo a repetir o próprio erro de
        # localização: medido no A/B do v11, que tinha 38,4% de caixas dessa
        # origem e PERDEU em IoU (0,67 contra 0,84) para um modelo com metade do
        # dado. Este filtro deixa entrar só o que a mão humana desenhou.
        humanas = [row for row in rows if row.get("source", "manual") == "manual"]
        return humanas, tinham_caixa

    return [
        row for row in rows
        if row.get("source", "manual") == "manual" or row.get("reviewed_by") is not None
    ], tinham_caixa


#: Área (fração do frame) a partir da qual a caixa deixa de ser localização.
_AREA_ROTULO_DE_FRAME = 0.95


def _sem_rotulos_de_frame(
    annotations: list[dict[str, Any]], frames: list[dict[str, Any]],
    frames_com_caixa_no_banco: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Tira do treino de localização as caixas que cobrem o frame inteiro.

    E, junto, aplica a invariante geral do dataset: **nenhum frame vai ao
    treino com zero caixas a não ser que ele genuinamente não tenha nada**.
    Um frame que perdeu todas as caixas por FILTRO (rótulo de frame, ou
    proveniência no braço só-humano) mostra o objeto e estaria ensinando o
    detector a NÃO vê-lo — é pior que descartá-lo. Frame que nunca teve caixa
    alguma no banco é negativo de verdade e continua no dataset.

    `frames_com_caixa_no_banco` é o conjunto ANTES de qualquer filtro; sem ele
    a função só sabe julgar os frames que os rótulos de frame esvaziaram.
    """
    restantes = [a for a in annotations if not _e_rotulo_de_frame(a)]
    rotulos = len(annotations) - len(restantes)

    com_caixa = {str(a["frame_id"]) for a in restantes}
    tinham = (
        frames_com_caixa_no_banco
        if frames_com_caixa_no_banco is not None
        else {str(a["frame_id"]) for a in annotations}
    )
    esvaziados = tinham - com_caixa
    if not rotulos and not esvaziados:
        return annotations, frames

    logger.warning(
        "dataset_export_frames_esvaziados: %d caixas [0,0,1,1] (classificação, "
        "não localização) fora do treino; %d frames ficaram sem nenhuma caixa "
        "depois dos filtros e saíram do dataset",
        rotulos, len(esvaziados),
    )
    return restantes, [f for f in frames if str(f["id"]) not in esvaziados]


def _e_rotulo_de_frame(row: dict[str, Any]) -> bool:
    """A caixa cobre o frame todo — é rótulo de conteúdo, não alvo de detecção.

    A aba Classificar responde "este frame mostra a classe X?" e grava o
    veredito com o bbox [0,0,1,1] (CropClassifier.tsx: FULL_FRAME_BBOX), um
    placeholder assumido no próprio código enquanto não havia detector de
    pessoa para recortar. O destino dessa linha, porém, é a mesma tabela e o
    mesmo source='manual' de uma caixa desenhada à mão — então o export a
    entregava ao treino como VERDADE DE LOCALIZAÇÃO.

    Medido no RVB em 2026-08-25: 1.095 das 4.629 anotações manuais (23,7%) são
    exatamente cx=0,5 cy=0,5 w=1 h=1, distribuídas em 420 frames que não têm
    nenhuma outra caixa. Um quarto do dado humano estava ensinando que
    "Protetor auditivo" é a imagem inteira — o que casa com a queixa de caixa
    larga e fora do lugar, e com a perda de IoU do v11.

    O rótulo continua valendo como classificação (a linha não é apagada — C-01
    e a regra de nunca DELETE); ele só não entra no treino de localização.
    """
    largura = row.get("width")
    altura = row.get("height")
    if largura is None or altura is None:
        return False
    return float(largura) * float(altura) >= _AREA_ROTULO_DE_FRAME


def _frame_day(frame: dict[str, Any]) -> str | None:
    """Data (YYYY-MM-DD) de captura do frame: captured_at, fallback created_at.

    captured_at (TIMESTAMPTZ) é a data real de gravação NVR; created_at
    (TIMESTAMP, sempre presente — NOT NULL no schema) é quando o frame foi
    extraído/ingerido, usado só quando captured_at não veio preenchido.
    Aceita datetime (psycopg2/RealDictCursor) ou str (testes/defensivo).
    """
    value = frame.get("captured_at") or frame.get("created_at")
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)[:10] or None


def _group_key(frame: dict[str, Any]) -> str:
    """Grupo de split — sem leakage entre train/val/test.

    Prioridade: video_id (vídeo inteiro em um único split) > camera_id +
    dia de captura (frames soltos de NVR — mesma câmera no mesmo dia tende
    a ter frames quase-idênticos; separar entre splits vazaria informação)
    > 'frame:{id}' como último recurso, quando não há video_id nem
    camera_id+data resolvíveis — não deveria acontecer com o schema atual
    (training_frames sempre tem camera_id ou video_id), mas não pode
    quebrar o build; loga aviso porque o split volta a ser efetivamente
    por imagem para esse frame.
    """
    if frame.get("video_id"):
        return str(frame["video_id"])

    camera_id = frame.get("camera_id")
    day = _frame_day(frame)
    if camera_id and day:
        return f"cam:{camera_id}:{day}"

    logger.warning(
        "split_group_key_fallback_frame_id: frame_id=%s sem video_id nem "
        "camera_id+data resolvíveis — split por imagem individual (risco "
        "de leakage entre splits para este frame)",
        frame.get("id"),
    )
    return f"frame:{frame['id']}"


def _limita_frames(
    frames: list[dict[str, Any]], limite: int, seed: str,
) -> list[dict[str, Any]]:
    """Corta o dataset a `limite` frames, de forma determinística.

    Braço de controle do A/B do #536. As duas populações do experimento são
    DISJUNTAS — medido no RVB: 2.617 frames têm só proposta aceita, 2.359 têm
    só caixa desenhada à mão, e ZERO têm as duas. Não existe "mesmas imagens
    com menos caixas": tirar a geometria do modelo tira 53% dos frames
    INTEIROS. Então o único controle possível é igualar o VOLUME — comparar
    2.362 frames de geometria 100% humana contra 2.362 frames de procedência
    misturada separa "menos dado" de "geometria pior".

    A escolha sai do hash (seed, id), não de `random.sample`: o corte precisa
    ser reproduzível entre execuções e independente da ordem que o banco
    devolveu. Ordenar por hash embaralha sem sortear.
    """
    def peso(frame: dict[str, Any]) -> str:
        return hashlib.sha256(f"{seed}\x00{frame['id']}".encode()).hexdigest()

    return sorted(frames, key=peso)[:limite]


def _split_estavel(chave: str, seed: str, split: dict[str, float]) -> str:
    """Split de um grupo por HASH — independente de quem mais está no dataset.

    `_split_by_group` decide por posição numa lista embaralhada dos grupos
    PRESENTES: mude a população e a mesma semente produz outra atribuição.
    Medido no A/B do #536: dos 2.362 frames presentes nos dois braços, **1.701
    caíram em split diferente** mesmo com a semente compartilhada — e com isso
    `Sem protetor de ouvido` acabou com MAIS caixas de treino no braço podado
    (337) que no completo (294), tornando a comparação por classe sem sentido.

    Aqui a atribuição sai de hash(seed, chave), então qualquer SUBCONJUNTO
    herda a mesma decisão por construção. O preço é proporção aproximada em vez
    de exata — aceitável, e quem chama registra a proporção real obtida.

    sha256 e não `hash()`: o hash embutido do Python é salgado por processo
    (PYTHONHASHSEED), então daria split diferente a cada worker.
    """
    digest = hashlib.sha256(f"{seed}\x00{chave}".encode()).digest()
    ponto = int.from_bytes(digest[:8], "big") / float(1 << 64)
    corte_train = split.get("train", 0.7)
    corte_val = corte_train + split.get("val", 0.2)
    if ponto < corte_train:
        return "train"
    return "val" if ponto < corte_val else "test"


def _split_by_group(
    frames: list[dict[str, Any]], split: dict[str, float], seed: str | None = None,
    estavel: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Split por grupo (sem leakage: frames do mesmo vídeo no mesmo split).

    `seed` torna o sorteio DETERMINÍSTICO por (dataset_id, version) — #515.
    A task tem `max_retries=2` e o retry reaproveita a row e o MESMO prefixo
    R2. Com shuffle sem semente, uma tentativa que morre no meio da etapa 7
    (subir os COCO por split) deixa `train/_annotations.coco.json` de um
    sorteio e `val/` de outro: o v9-freeze saiu `ready` com 514 frames que os
    dois declaram — 93% da "validação" vista no treino. Com semente, o retry
    reproduz o mesmo sorteio e reescrever vira idempotente em vez de
    destrutivo. `seed=None` preserva o comportamento antigo.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        groups.setdefault(_group_key(frame), []).append(frame)

    if estavel:
        if seed is None:
            raise ValueError("split estável exige seed")
        splits_e: dict[str, list[dict[str, Any]]] = {s: [] for s in _SPLIT_NAMES}
        for key, group_frames in groups.items():
            splits_e[_split_estavel(key, seed, split)].extend(group_frames)
        total = sum(len(v) for v in splits_e.values()) or 1
        logger.info(
            "dataset_export_split_estavel: %d grupos, proporção real "
            "train=%.3f val=%.3f test=%.3f (pedida train=%.2f val=%.2f)",
            len(groups), len(splits_e["train"]) / total, len(splits_e["val"]) / total,
            len(splits_e["test"]) / total, split.get("train", 0.7), split.get("val", 0.2),
        )
        return _garante_val_e_test(splits_e)

    # `sorted` antes do shuffle: a semente pina o SORTEIO, não a ENTRADA dele.
    # `groups` nasce na ordem em que as linhas voltaram do banco, e essa ordem
    # NÃO é total — frame de NVR entra com video_id NULL e frame_number=0, e o
    # `ORDER BY (validated_at IS NOT NULL) DESC, video_id, frame_number` do
    # snapshot empata o pool inteiro (empate volta do Postgres em ordem
    # arbitrária; validar um frame entre as tentativas troca a primeira chave).
    # Sem ordem canônica, a re-tentativa embaralha uma lista DIFERENTE com a
    # mesma semente — outro sorteio, e o vazamento de train para val volta.
    group_keys = sorted(groups)
    rnd = random.Random(seed) if seed is not None else random  # noqa: S311
    rnd.shuffle(group_keys)  # noqa: S311 — split de dataset, não cripto

    n = len(group_keys)
    n_train = max(1, int(n * split.get("train", 0.7)))
    n_val = int(n * split.get("val", 0.2))
    train_keys = set(group_keys[:n_train])
    val_keys = set(group_keys[n_train:n_train + n_val])

    splits: dict[str, list[dict[str, Any]]] = {s: [] for s in _SPLIT_NAMES}
    for key, group_frames in groups.items():
        if key in train_keys:
            splits["train"].extend(group_frames)
        elif key in val_keys:
            splits["val"].extend(group_frames)
        else:
            splits["test"].extend(group_frames)

    return _garante_val_e_test(splits)


def _garante_val_e_test(
    splits: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Val/test não-vazios quando há frames suficientes (base minúscula)."""
    if not splits["val"] and len(splits["train"]) > 1:
        cut = max(1, len(splits["train"]) // 5)
        splits["val"] = splits["train"][-cut:]
        splits["train"] = splits["train"][:-cut]
    if not splits["test"] and len(splits["val"]) > 1:
        splits["test"] = splits["val"][-1:]
        splits["val"] = splits["val"][:-1]
    return splits


def _conferir_splits(
    splits: dict[str, list[dict[str, Any]]],
    cocos: dict[str, dict[str, Any]],
) -> None:
    """Recusa marcar 'ready' um artefato em que um frame está em dois splits.

    O v9-freeze saiu `ready` com 514 frames declarados ao mesmo tempo no
    `train/_annotations.coco.json` e no de `val` — 93% da "validação" já vista
    no treino, e nada no caminho conferiu: nem o build, nem o dispatch, nem o
    runner (#515). O sorteio agora é determinístico, mas determinismo é uma
    hipótese sobre o código; a conferência é a medida do artefato que acabou de
    ser escrito. Divergiu, a exceção leva a versão a 'error' — não a 'ready'.
    """
    declarados = {
        nome: {img["file_name"] for img in doc.get("images", [])}
        for nome, doc in cocos.items()
    }
    for nome, arquivos in declarados.items():
        esperado = len(splits.get(nome, []))
        if len(arquivos) != esperado:
            raise ValueError(
                f"COCO de '{nome}' declara {len(arquivos)} imagens distintas "
                f"contra os {esperado} frames do split — artefato inconsistente"
            )
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        comum = declarados.get(a, set()) & declarados.get(b, set())
        if comum:
            raise ValueError(
                f"{len(comum)} frame(s) declarados em '{a}' E em '{b}' — "
                "vazamento entre splits; a versão não vai a 'ready'"
            )


# ── Guard de split degenerado (D-165, issue #426) ─────────────────────────────
# O split é por grupo (câmera+dia) e isso ⛔ NÃO muda: é ele que impede vazamento
# de câmera+dia. Com poucos grupos, porém, a proporção sai instável — e seguia
# CALADA. Medido: 17 grupos para 413 frames, o mesmo {train:.7, val:.2, test:.1}
# produziu 210/6/179 (53/1,5/45) no v3-treino1 e 354/51/8 (86/12/2) no v4.
#
# Aviso, não recusa. D-165 pede "aviso alto"; abortar o export puniria justamente
# o dataset pequeno, que é a fase em que a causa se resolve sozinha (mais câmera,
# mais dia). O diagnóstico sai no log E no resultado da task — quem exporta vê.
_MIN_IMAGENS_POR_SPLIT = 10       # abaixo disso a métrica do split é ruído
_DESVIO_PROPORCAO_MAX = 0.15      # 15 pp; os dois casos reais desviaram 17 e 35
_MIN_INSTANCIAS_CLASSE_TEST = 10  # "precisão sobre n=2 não é medida" (#426)


def _diagnosticar_split(
    splits: dict[str, list[dict[str, Any]]],
    split_pedido: dict[str, float],
    anns_by_frame: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """Avisos sobre um split degenerado — lista vazia quando está saudável."""
    avisos: list[str] = []
    total = sum(len(v) for v in splits.values())
    if not total:
        return avisos

    for nome in _SPLIT_NAMES:
        n = len(splits.get(nome, []))
        if n < _MIN_IMAGENS_POR_SPLIT:
            avisos.append(
                f"split '{nome}' com {n} imagem(ns) — abaixo do mínimo utilizável "
                f"de {_MIN_IMAGENS_POR_SPLIT}; métrica sobre esse split é ruído"
            )
        pedido = float(split_pedido.get(nome, 0.0))
        real = n / total
        if pedido and abs(real - pedido) > _DESVIO_PROPORCAO_MAX:
            avisos.append(
                f"split '{nome}' ficou em {real:.0%} contra os {pedido:.0%} pedidos "
                f"— o agrupamento por câmera+dia tem grupos demais concentrados"
            )

    # Classe que treina mas não aparece no test: a avaliação fica CEGA para ela.
    def _classes(nome: str) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for frame in splits.get(nome, []):
            for ann in anns_by_frame.get(str(frame["id"]), []):
                contagem[ann["class_name"]] = contagem.get(ann["class_name"], 0) + 1
        return contagem

    no_treino, no_test = _classes("train"), _classes("test")
    cegas = sorted(set(no_treino) - set(no_test))
    if cegas:
        avisos.append(
            f"classe(s) com suporte no train e ZERO no test: {cegas} — a avaliação "
            f"não mede essas classes, e o veredito sai sem elas"
        )
    fracas = sorted(
        c for c in set(no_treino) & set(no_test)
        if no_test[c] < _MIN_INSTANCIAS_CLASSE_TEST
    )
    if fracas:
        avisos.append(
            "classe(s) com suporte fraco no test "
            f"({', '.join(f'{c}={no_test[c]}' for c in fracas)}) — abaixo de "
            f"{_MIN_INSTANCIAS_CLASSE_TEST} instâncias a precisão é ruído com casas decimais"
        )
    return avisos


def _resolve_dimensions(
    frames: list[dict[str, Any]], storage
) -> tuple[list[dict[str, Any]], list[str]]:
    """Preenche width/height ausentes lendo a imagem do R2 com PIL.

    AI_NOTE (ajuste #11): fallback concorrente — ThreadPoolExecutor(10)
    para não serializar HTTP GETs no R2. Frames irresolvíveis são
    descartados (COCO exige dimensões absolutas).
    """
    missing = [f for f in frames if not f.get("width") or not f.get("height")]
    errors: list[str] = []
    if missing:
        from PIL import Image

        def _fetch(frame: dict[str, Any]) -> str | None:
            key = frame.get("r2_key") or frame.get("filename")
            try:
                data = storage.download_bytes(key)
                with Image.open(BytesIO(data)) as img:
                    frame["width"], frame["height"] = img.size
                return None
            except Exception as exc:  # noqa: BLE001
                return f"{frame['id']} ({key}): {exc}"

        with ThreadPoolExecutor(max_workers=_DIM_FALLBACK_WORKERS) as pool:
            for err in pool.map(_fetch, missing):
                if err:
                    errors.append(err)
                    logger.warning("dim_fallback_failed: %s", err)

    kept = [f for f in frames if f.get("width") and f.get("height")]
    return kept, errors


def _frame_ext(frame: dict[str, Any]) -> str:
    key = frame.get("r2_key") or frame.get("filename") or ""
    if "." in key.rsplit("/", 1)[-1]:
        return key.rsplit(".", 1)[-1]
    return "jpg"


def _yolo_to_coco_bbox(
    ann: dict[str, Any], width: int, height: int
) -> list[float]:
    """YOLO normalizado (cx, cy, w, h em 0..1) → COCO absoluto [x, y, w, h]."""
    w = float(ann["width"]) * width
    h = float(ann["height"]) * height
    x = float(ann["x_center"]) * width - w / 2
    y = float(ann["y_center"]) * height - h / 2
    return [round(x, 2), round(y, 2), round(w, 2), round(h, 2)]


def _build_coco_split(
    frames: list[dict[str, Any]],
    anns_by_frame: dict[str, list[dict[str, Any]]],
    categories: list[dict[str, Any]],
    cat_id_by_class: dict[int, int],
    version: str,
) -> dict[str, Any]:
    """Monta o JSON COCO de um split."""
    images: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    ann_id = 1
    for image_id, frame in enumerate(frames, start=1):
        images.append(
            {
                "id": image_id,
                "file_name": f"{frame['id']}.{_frame_ext(frame)}",
                "width": int(frame["width"]),
                "height": int(frame["height"]),
            }
        )
        for ann in anns_by_frame.get(str(frame["id"]), []):
            # Classe sem suporte no treino saiu do mapa (ver bloco 5): a
            # anotação é ignorada em TODOS os splits, para train/val/test
            # falarem do mesmo espaço de classes.
            if ann["class_id"] not in cat_id_by_class:
                continue
            bbox = _yolo_to_coco_bbox(ann, int(frame["width"]), int(frame["height"]))
            annotations.append(
                {
                    "id": ann_id,
                    "image_id": image_id,
                    "category_id": cat_id_by_class[ann["class_id"]],
                    "bbox": bbox,
                    "area": round(bbox[2] * bbox[3], 2),
                    "iscrowd": 0,
                }
            )
            ann_id += 1
    return {
        "info": {"description": f"Recognition dataset {version}"},
        "licenses": [],
        "categories": categories,
        "images": images,
        "annotations": annotations,
    }


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

def _recusa_se_versao_pronta(task, tenant_id: str, dataset_id: str, version: str) -> None:
    """Recusa build sobre dataset_version já `ready` — e denuncia quem tentou.

    Ver docstring de build_dataset_version_v2 para o incidente.
    """
    try:
        repo = _get_dataset_repo()
        atual = repo.get_version_by_label(dataset_id, tenant_id, version)
    except Exception as exc:  # noqa: BLE001 — falha de leitura não pode
        # bloquear build legítimo; o guard é proteção, não gargalo.
        logger.warning("version_guard_leitura_falhou: version=%s err=%s", version, exc)
        return

    if atual and str(atual.get("status")) == DatasetVersionStatus.READY.value:
        origem = getattr(getattr(task, "request", None), "id", None)
        logger.error(
            "dataset_version_ready_IMUTAVEL: recusado build sobre versão já "
            "pronta. version=%s dataset=%s tenant=%s version_id=%s "
            "task_id=%s — QUEM CHAMOU: %s",
            version, dataset_id, tenant_id, atual.get("id"), origem,
            "".join(traceback.format_stack(limit=12)),
        )
        raise ValueError(
            f"dataset_version '{version}' já está em 'ready' e é imutável — "
            "um re-export precisa de uma versão NOVA. Build recusado sem "
            "tocar no artefato existente."
        )


@celery.task(
    bind=True, max_retries=2, queue="versioning",
    name="tasks.versioning_v2.build_dataset_version_v2",
)
def build_dataset_version_v2(
    self,
    tenant_id: str,
    dataset_id: str,
    user_id: str,
    version: str,
    split: dict[str, float] | None = None,
    augmentations: dict[str, Any] | None = None,
    export_format: str = ExportFormat.COCO.value,
    module_code: str = "epi",
    somente_humano: bool = False,
    limite_frames: int | None = None,
    split_seed: str | None = None,
) -> dict[str, Any]:
    """Build oficial de dataset_version com export COCO por split.

    ⛔ Versão em `ready` é IMUTÁVEL. Um build sobre versão pronta é recusado
    antes de qualquer trabalho — "versão" significa snapshot congelado, e um
    export que sobrescreve versão pronta contradiz o próprio conceito.
    Re-export legítimo cria versão NOVA.

    Incidente que originou o guard (18/08): o artefato de `v5-relabel` (23,8 MB,
    já `ready`, base do experimento TREINO 2) foi sobrescrito por um zip de
    22 bytes às 01:50 e três pods queimaram a época 0 lendo dataset vazio.

    A recusa loga ALTO quem tentou (task id, origem, versão) — o guard é
    também o sensor que identifica o gatilho na próxima tentativa.
    """
    split = split or {"train": 0.7, "val": 0.2, "test": 0.1}

    _recusa_se_versao_pronta(self, tenant_id, dataset_id, version)
    version_id: str | None = None
    dataset_repo = _get_dataset_repo()

    try:
        logger.info(
            "build_dataset_v2_start: tenant=%s dataset=%s version=%s",
            tenant_id, dataset_id, version,
        )
        annotation_repo = _get_annotation_repo()
        storage = _get_storage(tenant_id)

        # 1. Snapshot de frames rotulados (reviewed primeiro)
        frames = _snapshot_labeled_frames(annotation_repo, tenant_id, module_code)
        if not frames:
            raise ValueError(
                "Nenhum frame rotulado encontrado para o tenant/módulo"
            )

        # 2. Anotações YOLO normalizadas por frame
        annotations, tinham_caixa = _fetch_annotations(
            annotation_repo, tenant_id, module_code, somente_humano=somente_humano
        )
        annotations, frames = _sem_rotulos_de_frame(annotations, frames, tinham_caixa)

        if limite_frames is not None and len(frames) > limite_frames:
            frames = _limita_frames(frames, limite_frames, split_seed or version)
            sobreviveram = {str(f["id"]) for f in frames}
            annotations = [
                a for a in annotations if str(a["frame_id"]) in sobreviveram
            ]

        anns_by_frame: dict[str, list[dict[str, Any]]] = {}
        for ann in annotations:
            anns_by_frame.setdefault(str(ann["frame_id"]), []).append(ann)

        # 3. Dimensões absolutas (fallback R2+PIL concorrente)
        frames, dim_errors = _resolve_dimensions(frames, storage)
        if not frames:
            raise ValueError(
                "Nenhum frame com dimensões resolvíveis para export COCO"
            )

        # 4. Split por grupo (sem leakage)
        # `split_seed` amarra dois exports à MESMA partição. Sem ele, versões
        # diferentes sorteiam diferente (é o comportamento correto no dia a
        # dia) — mas num A/B isso vira confundidor: medido no v13, os dois
        # braços caíram em 3.995 e 2.772 frames de treino, e a comparação
        # passaria a medir o sorteio em vez do filtro que estava sendo testado.
        splits = _split_by_group(
            frames, split, seed=split_seed or f"{dataset_id}:{version}",
            estavel=split_seed is not None,
        )
        split_warnings = _diagnosticar_split(splits, split, anns_by_frame)
        for aviso in split_warnings:
            logger.warning("dataset_export_split_degenerado: %s", aviso)

        # 5. Categorias e distribuição de classes
        #
        # O mapa nasce do split de TREINO, não do conjunto inteiro. Classe que
        # só aparece em val/test entrava em `categories` com ZERO instâncias no
        # train — e o RF-DETR quebra na época 0 com contagem de classes
        # inconsistente (mesma família do incidente de `supercategory`, #378).
        # Medido no v5-relabel: `Capacete` tem 1 box no mundo, caiu no test, e
        # o treino falhou na época 0.
        #
        # Robustez, não mudança de desenho: imagens e splits ficam idênticos —
        # só a categoria sem suporte de treino sai do mapa, com aviso alto.
        #
        # O remap é consistente por construção: existe UM `cat_id_by_class`,
        # usado nos três splits. Mapa divergente entre treino e avaliação
        # corromperia exatamente a métrica que o experimento mede.
        sem_treino_registradas: set[str] = set()
        train_frame_ids = {str(f["id"]) for f in splits.get("train", [])}
        seen: dict[int, str] = {}
        for ann in annotations:
            if str(ann["frame_id"]) in train_frame_ids:
                seen.setdefault(ann["class_id"], ann["class_name"])

        if not seen:
            # Split degenerado (dataset minúsculo — o agrupamento por
            # câmera+dia pôs tudo em val/test). Cai no comportamento antigo
            # em vez de abortar: um dataset de 1 grupo não é o caso que este
            # guard existe para pegar, e falhar aqui quebraria export legítimo
            # de base pequena. Avisa alto — nunca degradar em SILÊNCIO.
            logger.warning(
                "dataset_export_train_sem_anotacao: split de treino vazio "
                "(%d frames) — mapa de classes montado sobre o conjunto "
                "inteiro, como antes do guard de suporte-zero",
                len(train_frame_ids),
            )
            for ann in annotations:
                seen.setdefault(ann["class_id"], ann["class_name"])
        else:
            sem_treino = {
                ann["class_name"]
                for ann in annotations
                if ann["class_id"] not in seen
            }
            sem_treino_registradas = sem_treino
            if sem_treino:
                logger.warning(
                    "dataset_export_classes_sem_suporte_treino: %s — excluídas "
                    "do mapa de classes (o modelo não vai prevê-las). Total de "
                    "categorias: %d",
                    sorted(sem_treino), len(seen),
                )

        cat_id_by_class = {
            class_id: idx
            for idx, class_id in enumerate(sorted(seen), start=1)
        }
        # ÂNCORA id:0 — obrigatória, e a ausência dela é silenciosa.
        #
        # O RF-DETR conta classes a partir de uma categoria raiz `id:0` com
        # `supercategory:"none"` (convenção COCO do Roboflow). Sem ela os
        # índices de classe ficam deslocados de um: o modelo treina, exporta e
        # SERVE — devolvendo o rótulo errado para cada caixa, sem erro nenhum.
        #
        # Como isto passou despercebido: o único export que treinou de verdade
        # (v6, TREINO 2) foi remontado À MÃO numa sessão de depuração, e a
        # âncora entrou ali. O código do produto nunca a emitiu — o v7 nasceu
        # começando em id:1 com `supercategory: "epi"`, e só não virou treino
        # errado porque o pré-voo comparou os dois.
        categories = [{"id": 0, "name": _ANCORA_COCO, "supercategory": "none"}]
        categories += [
            {
                "id": cat_id_by_class[cid],
                "name": seen[cid],
                "supercategory": _ANCORA_COCO,
            }
            for cid in sorted(seen)
        ]
        kept_ids = {str(f["id"]) for f in frames}
        class_distribution: dict[str, int] = {}
        for ann in annotations:
            if str(ann["frame_id"]) in kept_ids:
                name = ann["class_name"]
                class_distribution[name] = class_distribution.get(name, 0) + 1

        # Classe excluída por não ter suporte no treino fica REGISTRADA na
        # versão, não só no log do pod (que expira junto com o pod). Isto é
        # risco de produto, não detalhe: com o split instável (17 grupos —
        # D-165), uma classe legítima pode cair fora do train por sorteio e
        # sumir do modelo entre execuções. Quem for ler as métricas depois
        # precisa ver que o modelo não prevê aquela classe.
        # Chave reservada com underscores: nenhuma classe real colide, e não
        # exige migration (class_distribution já é jsonb).
        if sem_treino_registradas:
            class_distribution["__sem_suporte_treino__"] = sorted(
                sem_treino_registradas
            )

        # 6. INSERT com linhagem completa — status 'building' (ajuste #9)
        base_key = f"{R2Prefix.DATASET_EXPORTS}/{tenant_id}/{dataset_id}/{version}"
        # Reaproveita a row de um retry anterior (mesmo dataset_id+version+
        # tenant, status building/error) em vez de INSERTar de novo — sem
        # UNIQUE constraint no schema, cada retry do Celery criaria uma row
        # duplicada com o mesmo label, órfã da primeira tentativa.
        existing = dataset_repo.get_pending_version(dataset_id, tenant_id, version)
        if existing:
            version_id = str(existing["id"])
            row = dataset_repo.update_version_status(
                existing["id"], tenant_id, DatasetVersionStatus.BUILDING.value
            ) or existing
            # As contagens da row são da tentativa ANTERIOR e o artefato vai ser
            # reescrito agora: sem reescrevê-las o banco descreve um export que
            # não existe mais. O v9-freeze ficou com val=159 gravado enquanto o
            # COCO no R2 declarava 553 (#515) — e é o banco que o dispatch lê.
            dataset_repo.update_version_counts(
                existing["id"], tenant_id,
                frame_count=len(frames),
                train_count=len(splits["train"]),
                val_count=len(splits["val"]),
                test_count=len(splits["test"]),
            )
            logger.info(
                "build_dataset_v2_reusing_version: version_id=%s (retry)", version_id
            )
        else:
            row = dataset_repo.create_version_v2(
                {
                    "user_id": user_id,
                    "version": version,
                    "frame_count": len(frames),
                    "train_count": len(splits["train"]),
                    "val_count": len(splits["val"]),
                    "test_count": len(splits["test"]),
                    "class_distribution": class_distribution,
                    "metadata_key": None,
                    "tenant_id": tenant_id,
                    "module_code": module_code,
                    "dataset_id": dataset_id,
                    "split": split,
                    "augmentations": augmentations,
                    "coco_r2_key": None,
                    "export_format": export_format,
                    "status": DatasetVersionStatus.BUILDING.value,
                    "created_by": user_id,
                }
            )
            version_id = str(row["id"])

        # 7. Copiar imagens + upload dos COCO por split
        copy_errors: list[str] = []
        cocos: dict[str, dict[str, Any]] = {}
        for split_name in _SPLIT_NAMES:
            split_frames = splits[split_name]
            for frame in split_frames:
                src = frame.get("r2_key") or frame.get("filename")
                dest = f"{base_key}/{split_name}/{frame['id']}.{_frame_ext(frame)}"
                try:
                    storage.copy_object(src, dest)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("copy_skipped: src=%s err=%s", src, exc)
                    copy_errors.append(f"{src} → {dest}: {exc}")

            coco = _build_coco_split(
                split_frames, anns_by_frame, categories, cat_id_by_class, version
            )
            cocos[split_name] = coco
            storage.upload_bytes(
                f"{base_key}/{split_name}/{_COCO_FILENAME}",
                json.dumps(coco).encode("utf-8"),
                "application/json",
            )

        # 7b. Conferência antes do 'ready' — ver _conferir_splits.
        _conferir_splits(splits, cocos)

        # 8. building → ready (grava prefixo R2 dos COCO)
        dataset_repo.update_version_status(
            row["id"], tenant_id, DatasetVersionStatus.READY.value,
            coco_r2_key=base_key,
        )

        result = {
            "dataset_version_id": version_id,
            "dataset_id": dataset_id,
            "tenant_id": tenant_id,
            "version": version,
            "status": DatasetVersionStatus.READY.value,
            "coco_r2_key": base_key,
            "total_frames": len(frames),
            "train_count": len(splits["train"]),
            "val_count": len(splits["val"]),
            "test_count": len(splits["test"]),
            "class_distribution": class_distribution,
            "categories": [c["name"] for c in categories],
            "copy_errors": copy_errors,
            "dimension_errors": dim_errors,
            # Sai no resultado, não só no log: aviso que ninguém lê é silêncio
            # com passos extras (D-165).
            "split_warnings": split_warnings,
        }
        logger.info(
            "build_dataset_v2_done: version_id=%s total=%d train=%d val=%d test=%d",
            version_id, len(frames),
            len(splits["train"]), len(splits["val"]), len(splits["test"]),
        )
        return result

    except ValueError as exc:
        logger.error(
            "build_dataset_v2_invalid: tenant=%s dataset=%s err=%s",
            tenant_id, dataset_id, exc,
        )
        _mark_error(dataset_repo, version_id, tenant_id)
        raise
    except Exception as exc:
        logger.error(
            "build_dataset_v2_failed: tenant=%s dataset=%s err=%s",
            tenant_id, dataset_id, exc, exc_info=True,
        )
        _mark_error(dataset_repo, version_id, tenant_id)
        raise self.retry(exc=exc, countdown=60) from exc


def _mark_error(dataset_repo, version_id: str | None, tenant_id: str) -> None:
    """Marca a versão como 'error' (best-effort — nunca mascara a exceção)."""
    if not version_id:
        return
    try:
        dataset_repo.update_version_status(
            version_id, tenant_id, DatasetVersionStatus.ERROR.value
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "build_dataset_v2_mark_error_failed: version=%s err=%s",
            version_id, exc,
        )
