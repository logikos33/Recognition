"""
Recognition — namespacing entre module_classes (catálogo global) e
yolo_classes (classes custom do tenant) na leitura unificada do anotador.

Contexto do bug: o anotador (AnnotationInterface.jsx) lista classes de
GET /modules/<code>/classes → module_classes (catálogo global, class_id
INTEGER pequeno, 0-based por módulo — hoje no máx. 0-7 em EPI). A criação de
classe (POST /classes) grava em yolo_classes (id SERIAL, GLOBAL cross-tenant
e cross-módulo). Como as duas tabelas nunca eram unidas na leitura, uma
classe recém-criada pelo tenant nunca aparecia no anotador — e mesmo que
aparecesse, `AnnotationService._validate_class` só validava contra
module_classes, rejeitando o save.

Por que namespacing por offset (e não, por exemplo, um esquema separado de
`source` por anotação): frame_annotations.class_id é um INTEGER solto (sem FK
— migration 103, task-078) usado tanto para persistir a anotação quanto como
índice de treino no .txt exportado (AnnotationService._export_yolo_labels).
Somar um offset grande ao id de yolo_classes ao expor a classe pro anotador
garante que o inteiro nunca colide com um class_id real de module_classes —
mesmo se o catálogo global crescer — SEM alterar os índices existentes do
catálogo (retrocompatível com toda anotação já salva, que usa o índice cru
0-based).

DÍVIDA CONHECIDA (não resolvida aqui, fora do escopo deste bugfix): o índice
namespaced (100000+) é ótimo para desambiguar leitura/validação, mas não é um
índice denso 0..N-1 — um pipeline de treino que espera classes contíguas
precisa remapear antes de treinar. Ver PR que introduziu este módulo.
"""

# Bem acima do maior catálogo real de module_classes (hoje: EPI tem 8 linhas,
# 0-7 — ver infra/migrations/009_module_classes.sql). Sem correspondência
# com nenhum id UUID de module_classes.id (coluna diferente).
TENANT_CLASS_ID_OFFSET = 100_000


def namespace_tenant_class_id(yolo_class_id: int) -> int:
    """Namespacing do id de yolo_classes pro espaço combinado do anotador.

    Usado tanto ao montar a lista unificada (ModuleService.get_classes) quanto
    ao validar anotações que referenciam uma classe custom do tenant
    (AnnotationService._validate_class) — os dois lados usam a MESMA função,
    então o inteiro que o frontend recebe na leitura é exatamente o que ele
    reenvia no save, sem tradução adicional.
    """
    return TENANT_CLASS_ID_OFFSET + int(yolo_class_id)
