"""Repository: vínculo N:N câmera↔módulo (public.camera_modules, migration 134).

Separado de CameraRepository porque é outra tabela — a regra da casa é uma
tabela por repository, e CameraRepository já carrega 30 métodos de
public.cameras.

O que esta tabela NÃO é: `cameras.active_module`. Aquela coluna é 1:1 e nasce
com DEFAULT 'epi', então todas as 29 câmeras da RVB estão em 'epi' sem que
ninguém tenha decidido nada. Aqui, ausência de linha significa exatamente
"ninguém declarou" — e é essa distinção que a tela de atribuição existe para
resolver.

Desvincular APAGA a linha. A migration 134 não tem coluna `enabled`, de
propósito: "sem linha" e "linha desligada" seriam duas formas de dizer a mesma
coisa, e todo SELECT que esquecesse o `WHERE enabled` mentiria em silêncio.

⚠️ Escrito em 2026-09-02 junto com outra frente, que estava escrevendo os
leitores de escopo (`escopo_sql` abaixo) contra uma versão da tabela COM
`enabled`. Os métodos de leitura/escrita da tela de atribuição
(`list_by_tenant`, `replace_for_cameras`) já seguem o DDL que foi de fato
commitado; os demais ainda citam `enabled` e vão falhar contra o schema real
até serem reconciliados.

`escopo_sql`/`escopo_params` (abaixo do repository) são o PONTO ÚNICO onde o
vínculo vira filtro. Coleta, pool de anotação, dashboard, eventos e deployment
de modelo importam daqui — nenhum deles escreve o próprio predicado. Trocar a
regra é trocar uma string neste arquivo.
"""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class CameraModuleRepository(BaseRepository):
    """Queries SQL para public.camera_modules."""

    def list_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        """Vínculos do tenant — (camera_id, module_code).

        Sem `WHERE enabled`: a migration 134 não tem essa coluna, e é
        deliberado — linha presente É o vínculo, desvincular apaga a linha.
        Duas formas de dizer "sem módulo" fariam todo SELECT que esquecesse o
        filtro mentir em silêncio.

        Uma consulta só para o tenant inteiro (não uma por câmera): 28 GETs
        paralelos nesta mesma tela já estouraram o pool de conexões da API no
        RVB — ver model_config_handlers.list_camera_model_configs.
        """
        return self._execute(
            "SELECT camera_id, module_code FROM public.camera_modules "
            "WHERE tenant_id = %s "
            "ORDER BY camera_id, module_code",
            (str(tenant_id),),
        )

    def replace_for_cameras(
        self,
        tenant_id: str,
        camera_ids: list[str],
        modules: list[str],
        assigned_by: str | None,
    ) -> int:
        """Faz `modules` ser EXATAMENTE o conjunto das câmeras dadas.

        Atômico (uma transação): o desvincular e o vincular de um mesmo salvar
        nunca chegam pela metade — sem isso uma falha no meio deixaria a câmera
        sem o vínculo antigo E sem o novo. Devolve quantas câmeras foram
        tocadas.

        `modules` vazio é operação legítima — significa "esta câmera não serve
        a módulo nenhum". Recusá-la deixaria o dono sem como DESFAZER uma
        marcação errada. Nesse caso o passo 1 limpa e o passo 2 não roda.
        """
        if not camera_ids:
            return 0

        def _run(_conn: Any, cur: Any) -> int:
            # 1) apaga o que saiu da seleção. DELETE aqui é DML da aplicação
            #    numa tabela de vínculo — não é a migration apagando dado, e
            #    não há coluna `enabled` para desligar em vez disso (migration
            #    134: linha presente É o vínculo).
            cur.execute(
                "DELETE FROM public.camera_modules "
                "WHERE tenant_id = %s AND camera_id = ANY(%s::uuid[]) "
                "AND NOT (module_code = ANY(%s))",
                (str(tenant_id), camera_ids, modules),
            )
            # 2) grava o que entrou. DO NOTHING preserva o assigned_by/
            #    assigned_at de quem declarou primeiro: re-salvar a mesma tela
            #    sem mudar nada não pode reescrever a autoria do vínculo.
            if modules:
                cur.executemany(
                    "INSERT INTO public.camera_modules "
                    "(tenant_id, camera_id, module_code, assigned_by) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (camera_id, module_code) DO NOTHING",
                    [
                        (str(tenant_id), cam, mod, assigned_by)
                        for cam in camera_ids
                        for mod in modules
                    ],
                )
            return len(camera_ids)

        return int(self._execute_in_transaction(_run))

    def camera_ids_for_module(self, tenant_id: str, module_code: str) -> list[str]:
        """Ids das câmeras que o dono declarou para `module_code`.

        Lista VAZIA = escopo não declarado (a tabela nasce vazia e não há
        backfill — ver migration 134). Quem usa isto para popular seletor tem
        de tratar o vazio como "mostra todas", nunca como "nenhuma": no dia do
        deploy nenhum tenant tem vínculo e um seletor vazio esconderia as 29
        câmeras da RVB sem nada ter mudado no banco.
        """
        rows = self._execute(
            "SELECT camera_id FROM public.camera_modules "
            "WHERE tenant_id = %s AND module_code = %s AND enabled = true",
            (str(tenant_id), str(module_code)),
        )
        return [str(r["camera_id"]) for r in rows]

    def camera_serves_module(
        self, tenant_id: str, camera_id: str, module_code: str
    ) -> bool:
        """A câmera serve o módulo? Mesma regra do `escopo_sql` — uma câmera.

        True quando o módulo AINDA NÃO tem nenhuma câmera declarada no tenant
        (escopo não declarado). Usado pela ingestão, que precisa decidir sobre
        UMA câmera antes de gastar upload no R2.
        """
        row = self._execute_one(
            "SELECT EXISTS (SELECT 1 FROM public.camera_modules "
            "  WHERE camera_id = %s AND tenant_id = %s "
            "    AND module_code = %s AND enabled = true) AS vinculada, "
            "EXISTS (SELECT 1 FROM public.camera_modules "
            "  WHERE tenant_id = %s AND module_code = %s AND enabled = true) "
            "  AS escopo_declarado",
            (
                str(camera_id), str(tenant_id), str(module_code),
                str(tenant_id), str(module_code),
            ),
        )
        if row is None:
            return True
        return bool(row["vinculada"]) or not bool(row["escopo_declarado"])


# ---------------------------------------------------------------------------
# O PONTO ÚNICO: vínculo → predicado SQL
# ---------------------------------------------------------------------------
#
# Toda superfície que precisa "só as câmeras deste módulo" cola ESTE fragmento
# no WHERE e estende os params com `escopo_params(...)`. Não há segunda cópia
# desta lógica no código — se a regra mudar, muda aqui.
#
# Três termos, nesta ordem, e cada um está aqui por um motivo medido:
#
#  1. `<col> IS NULL` — frame de upload manual e frame extraído de vídeo não
#     têm câmera. Sem este termo eles sumiriam do pool de anotação junto, e o
#     dono perderia material que nunca teve nada a ver com câmera nenhuma.
#
#  2. o vínculo em si — a câmera foi declarada para o módulo pelo dono.
#
#  3. `NOT EXISTS (qualquer vínculo do módulo)` — ESCOPO NÃO DECLARADO. A
#     tabela 134 nasce vazia de propósito (sem backfill). Sem este termo, o
#     deploy da migration zeraria a galeria, o dashboard e a coleta de TODOS
#     os tenants no mesmo segundo, sem uma linha mudar de valor no banco. Esta
#     casa já perdeu 1.098 anotações num filtro que excluía calado; um filtro
#     que exclui TUDO calado é a mesma família de defeito, uma ordem de
#     grandeza maior. O escopo só passa a valer quando o dono declara a
#     primeira câmera do módulo — antes disso ele não existe, e o predicado
#     diz isso em vez de fingir que existe e está vazio.
#
# ⚠️ `enabled = true` nos dois EXISTS: câmera desmarcada tem linha, e uma
# linha desmarcada não pode contar como escopo declarado nem como vínculo.

_ESCOPO_SQL = (
    "({col} IS NULL"
    " OR EXISTS (SELECT 1 FROM public.camera_modules cm_e"
    "             WHERE cm_e.camera_id = {col} AND cm_e.tenant_id = %s"
    "               AND cm_e.module_code = %s AND cm_e.enabled = true)"
    " OR NOT EXISTS (SELECT 1 FROM public.camera_modules cm_d"
    "                 WHERE cm_d.tenant_id = %s AND cm_d.module_code = %s"
    "                   AND cm_d.enabled = true))"
)


def escopo_sql(camera_col: str) -> str:
    """Predicado "esta linha é de câmera do módulo".

    `camera_col` é nome de coluna qualificado (ex.: 'tf.camera_id', 'a.camera_id')
    — literal do CHAMADOR, jamais input do usuário. tenant_id e module_code vão
    como %s via `escopo_params`, na mesma ordem.
    """
    return _ESCOPO_SQL.format(col=camera_col)


def escopo_params(tenant_id: str, module_code: str) -> list[str]:
    """Os 4 %s do `escopo_sql`, na ordem em que aparecem."""
    t, m = str(tenant_id), str(module_code)
    return [t, m, t, m]


# `public.cameras` é o caso especial: ela JÁ tem uma coluna de módulo
# (`module_code`, 1:1, DEFAULT 'epi') que hoje é a única resposta existente.
# Aqui o vínculo não SOMA à coluna, ele a SUBSTITUI assim que existe — senão
# uma câmera que o dono vinculou ao EPI mas cuja coluna diz 'quality' sairia
# das contagens do EPI, e o dono não teria como consertar pela tela nova.
#
# Enquanto o módulo não tem nenhum vínculo declarado no tenant, vale a coluna
# — que é exatamente o comportamento de hoje, byte a byte.
_ESCOPO_CAMERA_SQL = (
    "(EXISTS (SELECT 1 FROM public.camera_modules cm_c"
    "          WHERE cm_c.camera_id = {col} AND cm_c.tenant_id = %s"
    "            AND cm_c.module_code = %s AND cm_c.enabled = true)"
    " OR (NOT EXISTS (SELECT 1 FROM public.camera_modules cm_n"
    "                  WHERE cm_n.tenant_id = %s AND cm_n.module_code = %s"
    "                    AND cm_n.enabled = true)"
    "     AND {mod_col} = %s))"
)


def escopo_camera_sql(id_col: str, module_col: str) -> str:
    """Predicado "esta CÂMERA pertence ao módulo", para queries em public.cameras.

    Diferente de `escopo_sql`: lá o vínculo restringe um conjunto que já tem
    outro critério de módulo; aqui ele SUBSTITUI a coluna legada.
    Ambos os nomes de coluna são literais do chamador, nunca input do usuário.

    ⚠️ Os dois nomes TÊM de vir qualificados ('public.cameras.id', 'c.id'…).
    Sem qualificar, `cm_c.camera_id = id` dentro do EXISTS resolve para o `id`
    da PRÓPRIA camera_modules — a coluna existe nas duas tabelas e o Postgres
    prefere a de dentro, sem erro nenhum. O predicado passaria a comparar a
    linha consigo mesma e o filtro devolveria zero câmeras em silêncio (foi o
    que aconteceu na primeira versão, pego pelo teste do KPI). Sem valor
    default justamente para não deixar esse caminho aberto.
    """
    for nome in (id_col, module_col):
        if "." not in nome:
            raise ValueError(
                f"escopo_camera_sql exige coluna qualificada, recebeu {nome!r}"
            )
    return _ESCOPO_CAMERA_SQL.format(col=id_col, mod_col=module_col)


def escopo_camera_params(tenant_id: str, module_code: str) -> list[str]:
    """Os 5 %s do `escopo_camera_sql`, na ordem em que aparecem."""
    t, m = str(tenant_id), str(module_code)
    return [t, m, t, m, m]
