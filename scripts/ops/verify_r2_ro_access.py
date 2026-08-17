#!/usr/bin/env python3
"""Verificador de acesso R2 SOMENTE-LEITURA (DEV).

Confirma que a credencial read-only do R2 (a que o Vitor cria no bloco 3 do
provisionamento) consegue LISTAR o bucket DEV — sem baixar imagem, sem imprimir
chave, sem imprimir nome de objeto. Feito para o runner de mineração: se este
script sai 0, a credencial funciona no primeiro try.

⛔ REGRA DO SEGREDO: este script NUNCA imprime valor de credencial nem conteúdo
de objeto. Só reporta presença/ausência de variável e sucesso/falha do LIST.

Lê do ENV (nada em argv — argv é visível em `ps`):
  R2_RO_ACCESS_KEY   ← chave read-only (criada pelo Vitor)
  R2_RO_SECRET       ← secret read-only (criada pelo Vitor)
  R2_ENDPOINT        ← reusa o existente (endpoint da conta, não é a credencial)
  R2_BUCKET          ← reusa o existente (bucket DEV)

⛔ NÃO reusa R2_KEY / R2_SECRET (essas são read-WRITE — bloco 3 exige RO própria).

Uso:
  python3 scripts/ops/verify_r2_ro_access.py
Saída: linha única "R2_RO: OK ..." / "R2_RO: FALHA ..." e exit 0/1.
"""
from __future__ import annotations

import os
import sys

_REQUIRED = ("R2_RO_ACCESS_KEY", "R2_RO_SECRET", "R2_ENDPOINT", "R2_BUCKET")


def _fail(msg: str) -> None:
    # msg NUNCA contém valor de credencial — só nomes de variável / diagnóstico.
    print(f"R2_RO: FALHA — {msg}")
    sys.exit(1)


def main() -> None:
    missing = [name for name in _REQUIRED if not os.environ.get(name)]
    if missing:
        # Reporta só os NOMES ausentes, nunca os presentes nem seus valores.
        _fail(f"variáveis ausentes no ambiente do runner: {', '.join(missing)}")

    # Guarda-corpo: não deixar reusar a credencial read-WRITE por engano.
    if os.environ.get("R2_RO_ACCESS_KEY") == os.environ.get("R2_KEY"):
        _fail(
            "R2_RO_ACCESS_KEY == R2_KEY: a credencial read-only não pode ser a "
            "read-write existente (crie uma Object Read only dedicada)"
        )

    try:
        import boto3  # noqa: PLC0415 — dependência já usada em r2_storage.py
        from botocore.config import Config  # noqa: PLC0415
    except ImportError:
        _fail("boto3 não instalado no ambiente do runner (pip install boto3)")

    bucket = os.environ["R2_BUCKET"]
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_RO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["R2_RO_SECRET"],
        config=Config(signature_version="s3v4", retries={"max_attempts": 2}),
    )

    try:
        # LIST de 1 objeto: prova leitura sem BAIXAR nada (sem get_object).
        resp = client.list_objects_v2(Bucket=bucket, MaxKeys=1)
    except Exception as exc:  # noqa: BLE001 — reporta a CLASSE do erro, nunca a chave
        _fail(f"list_objects_v2 falhou ({type(exc).__name__}) — cheque permissão/bucket")

    # Reporta só a CONTAGEM/presença — nunca a Key do objeto.
    key_count = resp.get("KeyCount", 0)
    if key_count and key_count > 0:
        print("R2_RO: OK — leitura confirmada (bucket DEV lista >=1 objeto; nada baixado)")
    else:
        # Acesso funcionou (sem AccessDenied), mas bucket vazio — ainda é sucesso de auth.
        print("R2_RO: OK — auth/list confirmados; bucket DEV vazio (0 objetos), nada baixado")
    sys.exit(0)


if __name__ == "__main__":
    main()
