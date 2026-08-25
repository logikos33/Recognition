"""Prova da 128 contra o schema REAL, em transação revertida ao fim.

Sequência do boot em modo legado: as migrations rodam em ordem numérica no
mesmo passe. Simulo 022 -> 128 -> 022 -> 128 e confiro o estado a cada etapa.
"""
import os, psycopg2, psycopg2.extras
RAIZ = "/Users/vitoremanuel/Logikos-mutirao/wt-consertos/infra/migrations"
SQL_022 = open(f"{RAIZ}/022_demo_mock_alerts.sql").read()
SQL_128 = open(f"{RAIZ}/128_neutraliza_alertas_de_demonstracao_022.sql").read()
PREFIXO = "frames/d97cb03e%"

u = os.environ.get("DATABASE_PUBLIC_URL") or os.environ["DATABASE_URL"]
c = psycopg2.connect(u, cursor_factory=psycopg2.extras.RealDictCursor)
c.autocommit = False
q = c.cursor()

def estado(etapa):
    q.execute("""SELECT COUNT(*) AS n,
                        COUNT(*) FILTER (WHERE tenant_id IS NOT NULL) AS com_tenant,
                        COUNT(*) FILTER (WHERE violations <> '[]'::jsonb) AS com_violacao,
                        COUNT(*) FILTER (WHERE acknowledged) AS reconhecidos
                 FROM public.alerts WHERE evidence_key LIKE %s""", (PREFIXO,))
    r = q.fetchone()
    print(f"  {etapa:<34} linhas={r['n']:<4} com_tenant={r['com_tenant']:<4} "
          f"com_violacao={r['com_violacao']:<4} reconhecidos={r['reconhecidos']}")
    return r

try:
    print("=== estado inicial do DEV ===")
    ini = estado("antes de tudo")

    print("\n=== BOOT 1 (modo legado: 022 roda, depois 128) ===")
    q.execute(SQL_022); a = estado("depois da 022")
    q.execute(SQL_128); b = estado("depois da 128")

    print("\n=== BOOT 2 (as duas re-executam) ===")
    q.execute(SQL_022); cc = estado("depois da 022 (2a vez)")
    q.execute(SQL_128); d = estado("depois da 128 (2a vez)")

    print("\n=== VEREDITO ===")
    ok = []
    ok.append(("022 inseriu no boot 1", a["n"] > ini["n"]))
    ok.append(("128 zerou o tenant de todas", b["com_tenant"] == 0))
    ok.append(("128 zerou as violações de todas", b["com_violacao"] == 0))
    ok.append(("128 marcou todas como reconhecidas", b["reconhecidos"] == b["n"]))
    ok.append(("022 PULOU no boot 2 (não inseriu de novo)", cc["n"] == b["n"]))
    ok.append(("128 é idempotente (nada mudou)", (d["n"], d["com_tenant"], d["com_violacao"]) == (b["n"], b["com_tenant"], b["com_violacao"])))
    for nome, passou in ok:
        print(f"  {'✅' if passou else '🔴'} {nome}")
    print(f"\n{'TODAS PASSARAM' if all(p for _, p in ok) else '🔴 ALGUMA FALHOU'}")
finally:
    c.rollback()
    print("\n(transação revertida — o DEV não foi alterado)")
