#!/usr/bin/env python3
"""
criar_contas_rvb.py — cria as contas das PESSOAS REAIS da RVB Isolantes.

Existe porque o papel certo já foi decidido (issue #774) e ninguém deve ter
de escolher de novo na pressa da segunda-feira. Você informa QUEM entra; o
papel vem embutido aqui:

    RVB_TST_EMAILS       → papel `operator`  (técnico de segurança)
        ver evento → tratar (corrigir a violação) → verificar a detecção
    RVB_ANOTADOR_EMAILS  → papel `trainer`   (anotador do Estúdio)
        anotar → classificar (F/V/X) → verificar a detecção → treinar

A matriz que sustenta essas duas linhas é testada em
`services/api/tests/security/test_papel_fecha_o_ciclo.py`, percorrendo cada
passo pela API.

O QUE ESTE SCRIPT NÃO FAZ, DE PROPÓSITO
  · não apaga nem desativa nada;
  · não troca o papel de conta que já existe (só avisa) — mexer no acesso de
    quem já está trabalhando é decisão de gente, não de script;
  · não gera senha: a senha vem de você, por env. Assim ela não aparece na
    saída do terminal nem em log de CI.

Uso (uma linha, ver a issue de provisionamento):

    RVB_CONTAS_ENABLED=true \
    DATABASE_URL=postgresql://... \
    RVB_TST_EMAILS="fulano@rvb.com.br,ciclana@rvb.com.br" \
    RVB_ANOTADOR_EMAILS="beltrano@rvb.com.br" \
    RVB_SENHA_INICIAL='<senha combinada>' \
    RVB_EXIGIR_TROCA_SENHA=true \
    python3 scripts/criar_contas_rvb.py

Env opcionais:
    RVB_TENANT_SLUG          slug do tenant (default: rvb)
    RVB_EXIGIR_TROCA_SENHA   'true' marca force_password_reset — está na linha
                             de uso acima porque é o que fecha a issue #764:
                             sem ela a senha combinada no papel vale para
                             sempre. A TELA de troca EXISTE desde a issue #819
                             (`apps/frontend/src/app/acesso/Entrar.tsx`): o
                             403 do primeiro login abre, na própria tela, o
                             formulário de nova senha. Default segue false
                             para não mudar o comportamento de quem já
                             automatizou a chamada.
"""
import os
import sys

# ── Gate ───────────────────────────────────────────────────────────────────
if os.environ.get("RVB_CONTAS_ENABLED") != "true":
    print("ERRO: RVB_CONTAS_ENABLED != 'true'. Abortando (evita execução acidental).")
    sys.exit(1)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERRO: DATABASE_URL não definida.")
    sys.exit(1)

SENHA = os.environ.get("RVB_SENHA_INICIAL")
if not SENHA:
    print("ERRO: RVB_SENHA_INICIAL não definida.")
    sys.exit(1)
if len(SENHA) < 6:
    print("ERRO: RVB_SENHA_INICIAL: mínimo 6 caracteres (mesma regra do /login).")
    sys.exit(1)

TENANT_SLUG = os.environ.get("RVB_TENANT_SLUG", "rvb").strip().lower()
EXIGIR_TROCA = os.environ.get("RVB_EXIGIR_TROCA_SENHA", "").strip().lower() == "true"

# Papel por persona — a decisão, em um lugar só.
PAPEL_POR_PERSONA = {
    "RVB_TST_EMAILS": ("operator", "TST — evento → tratar → verificar"),
    "RVB_ANOTADOR_EMAILS": ("trainer", "Anotador — anotar → classificar → verificar → treinar"),
}

try:
    import bcrypt
    import psycopg2
except ImportError as exc:
    print(f"ERRO: dependência ausente: {exc}")
    print("  Instale com: pip install psycopg2-binary bcrypt")
    sys.exit(1)


def _emails(var: str) -> list[str]:
    return [e.strip().lower() for e in os.environ.get(var, "").split(",") if e.strip()]


def _nome_de(email: str) -> str:
    """Nome provisório a partir do e-mail — a pessoa/admin renomeia na tela."""
    return email.split("@")[0].replace(".", " ").replace("_", " ").title()


def main() -> None:
    pedidos: list[tuple[str, str, str]] = []  # (email, papel, persona)
    for var, (papel, persona) in PAPEL_POR_PERSONA.items():
        for email in _emails(var):
            pedidos.append((email, papel, persona))

    if not pedidos:
        print("ERRO: nenhum e-mail informado.")
        print("  Defina RVB_TST_EMAILS e/ou RVB_ANOTADOR_EMAILS (separados por vírgula).")
        sys.exit(1)

    duplicados = {e for e, _, _ in pedidos if [x for x, _, _ in pedidos].count(e) > 1}
    if duplicados:
        print(f"ERRO: e-mail em mais de uma persona: {sorted(duplicados)}")
        print("  Uma pessoa, um papel — escolha qual ciclo é o dela.")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, name, modules_enabled FROM tenants WHERE slug = %s",
            (TENANT_SLUG,),
        )
        row = cur.fetchone()
        if not row:
            print(f"ERRO: tenant slug='{TENANT_SLUG}' não existe neste banco.")
            sys.exit(1)
        tenant_id, tenant_nome, modulos = row
        print(f"Tenant: {tenant_nome} ({tenant_id})")

        # Conferência do item 3 da issue #775 — só avisa, não altera plano.
        modulos_lista = modulos if isinstance(modulos, list) else []
        if "epi" not in modulos_lista:
            print(f"  AVISO: modules_enabled do tenant = {modulos_lista!r} — sem 'epi'.")
            print("  As contas serão criadas, mas o módulo EPI não abrirá para elas.")

        senha_hash = bcrypt.hashpw(SENHA.encode(), bcrypt.gensalt()).decode()

        criados, existentes, divergentes = [], [], []
        for email, papel, persona in pedidos:
            cur.execute(
                "SELECT id, role, tenant_id, is_active FROM users WHERE email = %s",
                (email,),
            )
            atual = cur.fetchone()
            if atual:
                existentes.append((email, atual[1]))
                if atual[1] != papel or str(atual[2]) != str(tenant_id):
                    divergentes.append((email, atual[1], papel))
                continue

            cur.execute(
                """
                INSERT INTO users
                    (email, password_hash, name, role, tenant_id, is_active,
                     force_password_reset)
                VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                ON CONFLICT (email) DO NOTHING
                RETURNING id
                """,
                (email, senha_hash, _nome_de(email), papel, tenant_id, EXIGIR_TROCA),
            )
            if cur.fetchone():
                criados.append((email, papel, persona))

        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"ERRO: {exc}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    print()
    for email, papel, persona in criados:
        print(f"  CRIADA   {email}  papel={papel}   {persona}")
    for email, papel in existentes:
        print(f"  JÁ EXISTIA  {email}  papel={papel} (nada foi alterado)")
    for email, tem, deveria in divergentes:
        print(f"  ATENÇÃO  {email} está como '{tem}', a decisão é '{deveria}'.")
        print("           Ajuste pela tela de usuários — este script não mexe em conta viva.")

    print(f"\n{len(criados)} conta(s) criada(s). Senha: a de RVB_SENHA_INICIAL.")
    if EXIGIR_TROCA:
        print(
            "Troca de senha EXIGIDA: no primeiro login a própria tela abre o "
            "formulário 'Definir nova senha' (o 403 password_change_required "
            "é tratado em apps/frontend/src/app/acesso/Entrar.tsx, issue "
            "#819). A pessoa entra com a senha do papel, escolhe a sua e cai "
            "direto no produto — sem falar com ninguém."
        )
    else:
        print(
            "ATENÇÃO: troca de senha NÃO exigida. A senha combinada continua "
            "valendo para sempre nessas contas — é exatamente a issue #764. "
            "A tela de troca JÁ EXISTE (issue #819): rode com "
            "RVB_EXIGIR_TROCA_SENHA=true para que cada pessoa defina a sua "
            "no primeiro login."
        )


if __name__ == "__main__":
    main()
