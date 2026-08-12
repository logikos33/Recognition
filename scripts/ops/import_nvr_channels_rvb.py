#!/usr/bin/env python3
"""
import_nvr_channels_rvb.py — Cadastro em lote dos canais 9–29 do iNVD 3032 (D-85).

NUNCA roda automaticamente. NUNCA importado por railway_start.py nem por
run_migrations — é um script de dados (mesmo padrão de unify_classes_rvb.py:
dado de cliente é script env-gated manual, nunca migration numerada).

O que faz — decisão do Vitor (rodada 11/08): "Pode incluir todas as câmeras
novas no sistema que eu vou tirar as que não fazem parte do reconhecimento."

    (a) Cadastra os canais 9–29 do gravador (21 câmeras do inventário D-85,
        docs/edge/INVENTARIO_INVD_3032_2026-08-11.md) no tenant RVB.
    (b) TODAS nascem is_active = FALSE (o estado "draft" que já existe no
        sistema — mesmo do POST /v1/admin/cameras/import). Câmera com
        is_active=FALSE fica FORA do channel_map que o ConfigPoller escreve
        pro box (config_poller.py: `if cam.get("is_active", True)`), logo:
        ⛔ não transmite (live view lê o mesmo channel_map)
        ⛔ não coleta (coletor lê o mesmo channel_map)
        ⛔ não infere (não há pipeline de inferência automatizado; task-060)
    (c) Credencial: NUNCA tocada em texto puro. O INSERT..SELECT copia
        username/password_encrypted (Fernet, CAMERA_SECRET_KEY) da câmera de
        REFERÊNCIA (canal 1, mesmo gravador, mesma credencial) direto dentro
        do banco — o ciphertext não passa nem pela memória deste processo.
        site_id/host/port/manufacturer/tenant_id/user_id vêm da mesma
        referência: as 21 nascem com o MESMO site_id das 8 atuais (sem isso
        ficam invisíveis pro edge — camera_service.create_camera, consumidores
        de site_id).
    (d) position_confirmed = FALSE (migration 113): pareamento canal↔posição
        física nunca foi feito — o nome "Canal N" é provisório de propósito.

Idempotente: NOT EXISTS por (tenant_id, host, channel) — rodar 2x não duplica
nem falha; canais já cadastrados (1–8 e reexecuções) são pulados e contados.
Tudo em UMA transação (BEGIN..COMMIT) — ou tudo aplica, ou nada.

Uso:
    DATABASE_URL=postgresql://... CONFIRM_OPS=1 \
        python3 scripts/ops/import_nvr_channels_rvb.py

Variáveis de ambiente:
    DATABASE_URL   PostgreSQL connection string (obrigatório)
    CONFIRM_OPS    precisa ser exatamente "1" — hard gate
    RVB_TENANT_SLUG  slug do tenant (default: rvb)

Saída: só contagens e canais (nenhuma credencial, nem ciphertext, é lida ou
impressa — assert de segurança no final).

⛔ NÃO EXECUTAR nesta branch — o orquestrador roda este script manualmente
após o deploy da migration 113 (o script aborta se a coluna não existir).
"""
import os
import sys

# ── Hard gate ────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("[import_nvr_channels_rvb] ERRO: DATABASE_URL não definida.")
    sys.exit(1)

if os.environ.get("CONFIRM_OPS") != "1":
    print("[import_nvr_channels_rvb] BLOQUEADO — CONFIRM_OPS != '1'.")
    print(
        "[import_nvr_channels_rvb]   Rode com: CONFIRM_OPS=1 DATABASE_URL=... "
        "python3 scripts/ops/import_nvr_channels_rvb.py"
    )
    sys.exit(1)

try:
    import psycopg2
except ImportError as exc:
    print(f"[import_nvr_channels_rvb] ERRO: dependência faltando: {exc}")
    print("  Instale: pip install psycopg2-binary")
    sys.exit(1)

TENANT_SLUG = os.environ.get("RVB_TENANT_SLUG", "rvb")

# Inventário D-85 (sondagem ONVIF de 2026-08-11, media2 GetProfiles):
# canal -> (codec do principal, resolução do principal). O substream é
# uniforme nos 29 canais: H264 704x480@30, 1024 kbps. Principal: 30fps,
# 4096 kbps em todos.
CHANNELS: dict[int, tuple[str, str]] = {
    9: ("H265", "1920x1080"),
    10: ("H265", "1920x1080"),
    11: ("H265", "1920x1080"),
    12: ("H265", "1920x1080"),
    13: ("H264", "1920x1080"),
    14: ("H265", "1920x1080"),
    15: ("H264", "1920x1080"),
    16: ("H264", "1920x1080"),
    17: ("H264", "1920x1080"),
    18: ("H265", "1920x1080"),
    19: ("H265", "1920x1080"),
    20: ("H265", "1920x1080"),
    21: ("H265", "1920x1080"),
    22: ("H265", "1920x1080"),
    23: ("H265", "1920x1080"),
    24: ("H265", "1920x1080"),
    25: ("H265", "1920x1080"),
    26: ("H265", "2560x1440"),
    27: ("H265", "2560x1440"),
    28: ("H265", "2560x1440"),
    29: ("H265", "2560x1440"),
}

_INSERT_SQL = """
INSERT INTO public.cameras
    (tenant_id, user_id, name, location, description, manufacturer,
     host, port, username, password_encrypted, channel, subtype,
     live_view_subtype, module_code, fps_target, quality_preset,
     site_id, is_active, position_confirmed, codec_detected, probe_status,
     notes)
SELECT
    ref.tenant_id, ref.user_id, %(name)s, NULL, %(description)s,
    ref.manufacturer, ref.host, ref.port, ref.username,
    ref.password_encrypted, %(channel)s, ref.subtype, ref.live_view_subtype,
    ref.module_code, ref.fps_target, ref.quality_preset,
    ref.site_id, FALSE, FALSE, %(codec)s, 'pending', %(notes)s
FROM public.cameras ref
WHERE ref.id = %(ref_id)s
  AND NOT EXISTS (
      SELECT 1 FROM public.cameras c
      WHERE c.tenant_id = ref.tenant_id
        AND c.host = ref.host
        AND c.channel = %(channel)s
  )
"""


def main() -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        cur = conn.cursor()

        # ── pré-condições (falha alto, nunca silencioso — ADR-0017) ─────
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='cameras' "
            "AND column_name='position_confirmed'"
        )
        if cur.fetchone() is None:
            print(
                "[import_nvr_channels_rvb] ABORTADO: coluna position_confirmed "
                "não existe — aplique a migration 113 antes (deploy da API)."
            )
            return 2

        cur.execute("SELECT id FROM public.tenants WHERE slug = %s", (TENANT_SLUG,))
        row = cur.fetchone()
        if row is None:
            print(f"[import_nvr_channels_rvb] ABORTADO: tenant '{TENANT_SLUG}' não existe.")
            return 2
        tenant_id = row[0]

        # Referência = canal 1 do gravador (RVB Camera 1): mesma credencial,
        # mesmo host, mesmo site. Exige credencial e site_id presentes —
        # sem site_id as 21 nasceriam invisíveis pro edge.
        cur.execute(
            "SELECT id, host, site_id IS NOT NULL, password_encrypted IS NOT NULL "
            "FROM public.cameras "
            "WHERE tenant_id = %s AND channel = 1 "
            "ORDER BY created_at ASC",
            (tenant_id,),
        )
        refs = cur.fetchall()
        if len(refs) != 1:
            print(
                f"[import_nvr_channels_rvb] ABORTADO: esperava exatamente 1 câmera "
                f"no canal 1 do tenant, encontrei {len(refs)} — resolva antes."
            )
            return 2
        ref_id, ref_host, has_site, has_pwd = refs[0]
        if not has_site or not has_pwd:
            print(
                "[import_nvr_channels_rvb] ABORTADO: câmera de referência (canal 1) "
                f"sem {'site_id' if not has_site else ''}"
                f"{' e ' if not (has_site or has_pwd) else ''}"
                f"{'credencial' if not has_pwd else ''} — as 21 herdariam o buraco."
            )
            return 2

        # ── inserção idempotente, canal a canal ──────────────────────────
        inserted, skipped = [], []
        for channel, (codec, resolution) in sorted(CHANNELS.items()):
            cur.execute(
                _INSERT_SQL,
                {
                    "ref_id": ref_id,
                    "name": f"Canal {channel}",
                    "channel": channel,
                    "codec": codec,
                    "description": (
                        "Cadastro em lote do inventário D-85 (2026-08-11). "
                        "Posição física NÃO confirmada — nome provisório."
                    ),
                    "notes": (
                        f"Inventário D-85: principal {codec} {resolution}@30fps "
                        "4096kbps; sub H264 704x480@30fps 1024kbps. Nasceu "
                        "is_active=FALSE (não transmite/coleta/infere) — "
                        "ativação é triagem do Vitor, pós-aditivo RVB."
                    ),
                },
            )
            (inserted if cur.rowcount == 1 else skipped).append(channel)

        conn.commit()

        # ── verificação pós-commit (só contagens) ────────────────────────
        cur.execute(
            "SELECT count(*) FILTER (WHERE NOT is_active), "
            "       count(*) FILTER (WHERE is_active), "
            "       count(*) FILTER (WHERE site_id IS NULL), "
            "       count(*) FILTER (WHERE password_encrypted IS NULL), "
            "       count(*) FILTER (WHERE position_confirmed) "
            "FROM public.cameras WHERE tenant_id = %s AND host = %s",
            (tenant_id, ref_host),
        )
        drafts, active, sem_site, sem_cred, confirmadas = cur.fetchone()

        print(f"[import_nvr_channels_rvb] inseridas agora : {len(inserted)} {inserted}")
        print(f"[import_nvr_channels_rvb] puladas (já há) : {len(skipped)} {skipped}")
        print(
            f"[import_nvr_channels_rvb] estado no gravador: {active} ativas, "
            f"{drafts} drafts (is_active=FALSE), {sem_site} sem site_id, "
            f"{sem_cred} sem credencial, {confirmadas} com posição confirmada"
        )
        if sem_site or sem_cred:
            print("[import_nvr_channels_rvb] ⚠️  há câmera sem site_id/credencial — investigue.")
            return 3
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"[import_nvr_channels_rvb] ERRO — rollback total: {type(exc).__name__}: {exc}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
