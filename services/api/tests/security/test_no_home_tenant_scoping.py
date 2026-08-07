"""Guarda estática — impede a 4ª ocorrência da lacuna do contexto assumido.

Contexto (ver docs/security/tenant-context-sweep.md): a impersonação por tenant
(#279) fez `get_tenant_id()` devolver o tenant ASSUMIDO (B), mas a identidade do
token continua sendo o superadmin (tenant de casa A). Qualquer SQL que resolva o
tenant efetivo por `(SELECT tenant_id FROM users WHERE id = <user_id>)` — o
tenant DE CASA — diverge do resto da feature (que escopa por get_tenant_id())
e vira um **404 latente** sob contexto assumido. Foi a causa-raiz de #302
(live view) e #313 (frames), corrigido de novo em treino/modelos.

Esta guarda varre **todos** os repositories e queue tasks de uma vez e falha
se surgir uma ocorrência NOVA do anti-padrão fora do baseline justificado —
apontando o file:line. Assim a 4ª ocorrência nem chega a nascer.

O que NÃO é flagueado (é a forma sancionada): encadear `get_tenant_id()` /
`get_tenant_schema()` handler → service → repository como parâmetro explícito.
Isso não é detectável estaticamente como "errado"; por isso a guarda mira o
anti-padrão (derivação SQL do tenant de casa), que é inequívoco.

Se você está adicionando uma ocorrência LEGÍTIMA (ex.: fallback COALESCE só
para linhas legadas com tenant_id NULL, com o caller sempre passando
get_tenant_id()), atualize BASELINE abaixo COM justificativa — e adicione um
teste falha-antes/passa-depois provando que o caminho honra o contexto assumido.
"""
from __future__ import annotations

import re
from pathlib import Path

# Anti-padrão: o tenant efetivo derivado da linha de casa do usuário.
# (A forma JOIN `COALESCE(tm.tenant_id, u.tenant_id)` NÃO é mirada aqui — é o
# fallback legado-NULL de model_registry.get_for_tenant, cujo caller sempre
# passa get_tenant_id(); ver o relatório da varredura.)
_ANTIPATTERN = re.compile(r"SELECT\s+tenant_id\s+FROM\s+users", re.IGNORECASE)

_API_ROOT = Path(__file__).resolve().parents[2]  # services/api/app -> repos/tasks
_SCAN_DIRS = [
    _API_ROOT / "app" / "infrastructure" / "database" / "repositories",
    _API_ROOT / "app" / "infrastructure" / "queue" / "tasks",
]

# Baseline JUSTIFICADO (path relativo a services/api → nº de ocorrências).
# Cada entrada é uma dívida conhecida e explicada na varredura; qualquer
# ocorrência fora daqui, ou uma contagem diferente, falha o CI.
BASELINE: dict[str, int] = {
    # frames — correção de baseline (drift pré-existente, achado ao rodar esta
    # suíte para um PR não-relacionado): get_by_id_and_user/mark_validated já
    # tinham sido corrigidos (tenant_id vira parâmetro explícito do CONTEXTO,
    # sem subquery) por 37d270a ("resolve frame ownership by request tenant
    # context, not home tenant"), mas o baseline desta guarda (3ee44db) foi
    # escrito contando as 3 ocorrências de ANTES desse fix e nunca foi
    # atualizado após o merge — os dois commits divergiram em paralelo. Só
    # sobra 1: o INSERT tag (record_frame), cujo COALESCE de 3 níveis é
    # prevenção de órfão (caller sempre passa get_tenant_id()).
    "app/infrastructure/database/repositories/frame_repository.py": 1,
    # treino — create_job/create_model: o COALESCE é prevenção de órfão; os
    # callers (job_handlers/training_service/socket_bridge) agora passam o
    # tenant do CONTEXTO (get_tenant_id()/job.tenant_id). Ver
    # test_model_tag_assumed_tenant.py.
    "app/infrastructure/database/repositories/training_repository.py": 2,
    # classes YOLO — create_class NÃO tem mais essa ocorrência: removida no
    # PR que uniu module_classes∪yolo_classes na leitura do anotador.
    # tenant_id agora é keyword-only sem default (fail-closed), mesmo padrão
    # de frame_repository.get_by_id_and_user/mark_validated — o único caller
    # vivo (TenantClassService.create_class) sempre passa get_tenant_id().
    # modelos — activate_for_tenant_module: COALESCE legado-NULL; o caller
    # (registry_handlers) sempre passa get_tenant_id().
    "app/infrastructure/database/repositories/model_registry_repository.py": 1,
    # datasets — build_dataset_version V1: código MORTO (a rota usa
    # build_dataset_version_v2, que faz threading correto do tenant). Mantido
    # no baseline enquanto o morto não é removido; ver varredura.
    "app/infrastructure/queue/tasks/versioning.py": 1,
}


def _scan() -> dict[str, list[int]]:
    """Mapeia path relativo → linhas (1-indexed) que casam o anti-padrão."""
    hits: dict[str, list[int]] = {}
    for base in _SCAN_DIRS:
        for py in base.rglob("*.py"):
            rel = py.relative_to(_API_ROOT).as_posix()  # "app/infrastructure/..."
            lines = [
                i
                for i, line in enumerate(py.read_text().splitlines(), start=1)
                if _ANTIPATTERN.search(line)
            ]
            if lines:
                hits[rel] = lines
    return hits


def test_no_new_home_tenant_scoping_in_repositories_or_tasks() -> None:
    hits = _scan()

    violations: list[str] = []

    # (a) ocorrências em arquivos fora do baseline → anti-padrão novo.
    for rel, lines in sorted(hits.items()):
        if rel not in BASELINE:
            for ln in lines:
                violations.append(
                    f"NOVO anti-padrão de tenant de casa em {rel}:{ln} — "
                    f"resolva o tenant por get_tenant_id() (contexto assumido), "
                    f"NÃO por (SELECT tenant_id FROM users). Ver "
                    f"docs/security/tenant-context-sweep.md."
                )

    # (b) contagem diferente do baseline num arquivo conhecido → ocorrência
    # adicionada (ou removida — atualize o baseline e a varredura).
    for rel, expected in sorted(BASELINE.items()):
        actual = len(hits.get(rel, []))
        if actual != expected:
            found = ", ".join(map(str, hits.get(rel, []))) or "nenhuma"
            verb = "adicionada" if actual > expected else "removida"
            violations.append(
                f"Contagem do anti-padrão mudou em {rel}: esperado {expected}, "
                f"achado {actual} (linhas: {found}) — ocorrência {verb}. Se for "
                f"legítima, atualize BASELINE COM justificativa; se removeu, "
                f"baixe o baseline e ajuste a varredura."
            )

    assert not violations, "Lacuna do contexto assumido:\n" + "\n".join(violations)
