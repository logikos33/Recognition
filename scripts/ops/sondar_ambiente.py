#!/usr/bin/env python3
"""sondar_ambiente.py — testa o `pip install` do treino SEM treinar.

POR QUE ISTO EXISTE (a conta que o justifica)
────────────────────────────────────────────────────────────────────────────────
Testar uma mudança de dependência pelo caminho normal custa ~50 min e US$ 0,03:
`_run_runpod_train_job` monta o `dataset.zip` (4.983 downloads + 349 MB de
upload) ANTES de criar o pod, e só então o `pip install` roda. Em 02/09 duas
correções seguidas queimaram esse ciclo inteiro para descobrir, no minuto 50,
que faltava mais um pin:

    18h38  numpy misto 1.x/2.x  → ImportError '_center'
    19h09  typing_extensions antigo → ImportError 'Sentinel'
           (albumentations → pydantic → pydantic_core → typing_extensions)

Esta sonda roda o MESMO `pip_install` do runner e apenas `import rfdetr`, num
pod que vive ~3 min. Mesma imagem, mesma resolução de dependências, mesmo
`_logar_versoes_resolvidas`. Custo ~US$ 0,04 e resposta em minutos — e o
dataset não entra na conta, porque a pergunta não é sobre o dataset.

⚠️ Ela responde "o ambiente sobe?", NÃO "o treino converge". É um teste de
fumaça de dependências, e é só isso que promete.

    R2_*=... RUNPOD_API_KEY=... python3 scripts/ops/sondar_ambiente.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "services" / "api"))
sys.path.insert(0, str(_RAIZ / "training" / "vast"))

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"
IMAGEM = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"


def _do_runner() -> tuple[list[str], str]:
    """A MESMA lista e o MESMO lock que `train_rfdetr` usa — lidos do runner,
    nunca recopiados. Uma sonda que testa outro ambiente não testa nada."""
    import re

    fonte = (_RAIZ / "training" / "vast" / "remote_train.py").read_text()
    bloco = re.search(r"pip_install\(\s*\n(.*?)\n\s*\)", fonte, re.S)
    if not bloco:
        raise SystemExit("não achei a chamada pip_install em remote_train.py")
    pacotes = re.findall(r'"([^"]+)"', bloco.group(1))
    lock = re.search(r'_CONSTRAINTS = """\\\n(.*?)"""', fonte, re.S)
    return pacotes, (lock.group(1) if lock else "")


EXECUTOR = '''
import json, os, subprocess, sys, urllib.request

PACOTES = {pacotes!r}
LOCK = {lock!r}
SAIDA = os.environ["UPLOAD_URL_RESULTADO"]

resultado = {{"pacotes_pedidos": PACOTES, "lock_linhas": len(LOCK.splitlines())}}
try:
    cmd = [sys.executable, "-m", "pip", "install", *PACOTES]
    if LOCK:
        # Testa o ambiente COM o lock — é assim que o pod de treino instala.
        with open("/root/c.txt", "w") as fh:
            fh.write(LOCK)
        cmd = [sys.executable, "-m", "pip", "install", "-c", "/root/c.txt", *PACOTES]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    resultado["pip_returncode"] = p.returncode
    resultado["pip_tail"] = (p.stdout + p.stderr)[-3000:]
    if p.returncode == 0:
        import rfdetr  # o import que quebrou nas duas ultimas tentativas
        from rfdetr import RFDETRBase  # noqa: F401
        resultado["import_rfdetr"] = "OK"
except Exception as exc:
    resultado["erro"] = f"{{type(exc).__name__}}: {{exc}}"[:2000]
    import traceback
    resultado["traceback"] = traceback.format_exc()[-3000:]

from importlib.metadata import PackageNotFoundError, version
vs = {{}}
for nome in ("numpy","scipy","supervision","rfdetr","transformers","torch",
             "onnx","pydantic","pydantic_core","typing_extensions",
             "albumentations","onnxruntime","pillow"):
    try:
        vs[nome] = version(nome)
    except PackageNotFoundError:
        pass
resultado["versoes"] = vs

corpo = json.dumps(resultado, indent=2).encode()
req = urllib.request.Request(SAIDA, data=corpo, method="PUT",
                             headers={{"Content-Type": "application/json"}})
urllib.request.urlopen(req, timeout=120)
print("resultado enviado")
'''


def main() -> int:
    from app.infrastructure.gpu.runpod_client import RunPodClient
    from app.infrastructure.gpu.runpod_runner import (
        build_onstart, cloud_type_default, container_disk_gb_default,
        gpu_type_default,
    )
    from app.infrastructure.storage.local_storage import get_storage

    pacotes, lock = _do_runner()
    print(json.dumps({"pacotes": pacotes, "lock_linhas": len(lock.splitlines())}),
          flush=True)

    chave = f"sondas/ambiente/{uuid.uuid4().hex[:12]}.json"
    st = get_storage(TENANT_RVB)
    url_put = st.generate_presigned_upload_url(
        chave, content_type="application/json", ttl=7200
    )

    cli = RunPodClient(os.environ["RUNPOD_API_KEY"])
    # 900 s: pip install de torch/rfdetr leva ~4 min; o dobro disso é folga e
    # ainda assim custa centavos. O `timeout` do onstart mata o pod de qualquer
    # jeito — a sonda não pode virar o pod esquecido que ela existe para evitar.
    onstart = build_onstart(
        EXECUTOR.format(pacotes=pacotes, lock=lock), 900,
        executor_filename="sonda_env.py",
    )
    pod = cli.create_pod(
        name=f"recognition-sondaenv-{uuid.uuid4().hex[:8]}",
        image=IMAGEM, gpu_type_id=gpu_type_default(),
        env={"UPLOAD_URL_RESULTADO": url_put,
             "RUNPOD_API_KEY": cli.api_key},
        docker_start_cmd=["/bin/bash", "-c", onstart],
        container_disk_gb=container_disk_gb_default(),
        cloud_type=cloud_type_default(),
    )
    pod_id = str(pod["id"])
    print(json.dumps({"pod": pod_id}), flush=True)

    try:
        limite = time.time() + 1200
        while time.time() < limite:
            time.sleep(20)
            try:
                print(st.download_bytes(chave).decode())
                return 0
            except Exception:  # noqa: BLE001 — ainda não subiu
                continue
        print(json.dumps({"erro": "sonda não devolveu resultado em 20 min"}))
        return 1
    finally:
        # O pod morre SEMPRE — sucesso, erro ou timeout. Mesmo contrato do
        # `run_runpod_job`; uma sonda de ambiente que vaza GPU seria irônica.
        cli.terminate_pod(pod_id)
        print(json.dumps({"pod_terminado": pod_id}), flush=True)


if __name__ == "__main__":
    sys.exit(main())
