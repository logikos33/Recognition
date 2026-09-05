#!/usr/bin/env python3
"""baixar_datasets_publicos.py — aquisição dos datasets públicos do pré-treino de EPI.

POR QUE ISTO EXISTE (achado medido, não hipótese): o detector é SERVIDO em frame
cheio de CFTV 1920x1080 com 5-7 pessoas, mas 95,9% do dado de treino RVB é
RECORTE de pessoa (~583x696) — e o vínculo recorte→frame-cheio nunca foi
gravado, então os 5.259 recortes anotados são irreprojetáveis. Restam ~194-204
frames cheios. O dataset público não é atalho de volume: é A CORREÇÃO DO
DOMÍNIO, porque traz cena completa com pessoas em escala de CFTV.

E ataca o gargalo medido: `Luvas` tem 304 caixas (a classe mais pobre do RVB) e
é justamente a que acusa em campo com 69,7% de precisão.

    select class_name, count(*) from public.frame_annotations group by 1 order by 2 desc
    -- 3087 Protetor auditivo · 972 mascara · 829 Botas · 635 Óculos · 304 Luvas
    -- (medido no DEV em 2026-09-02)

────────────────────────────────────────────────────────────────────────────────
LICENÇA É GATE, NÃO METADADO

Cada fonte aqui teve a licença CONFERIDA NA FONTE PRIMÁRIA (ver
docs/datasets/PPE_PRETRAIN_LICENSE_AUDIT.md e o cabeçalho de cada entrada de
`FONTES`). O script:

  1. reconfere a licença declarada pela API do Roboflow ANTES de baixar, e
     ABORTA a fonte se divergir do que está registrado aqui — a página e a API
     são fontes diferentes, e discordância entre elas é sinal de que o registro
     envelheceu;
  2. grava `PROCEDENCIA.json` + `ATRIBUICAO.txt` ao lado do dado. CC BY 4.0
     EXIGE crédito: é obrigação contratual, não cortesia. Dado sem procedência
     ao lado é dado que ninguém consegue auditar seis meses depois.

⛔ SH17 NÃO ESTÁ AQUI e não deve ser adicionado: CC BY-NC-SA 4.0 (NonCommercial).
   A taxonomia dele pode ser copiada (ideia não é expressão); o dado, não.

────────────────────────────────────────────────────────────────────────────────
USO

    # padrão: NÃO baixa nada. Lista fontes, licenças e o tamanho estimado.
    python3 scripts/ops/baixar_datasets_publicos.py --destino /dados/publicos

    # baixa de verdade (exige a flag)
    ROBOFLOW_API_KEY=... python3 scripts/ops/baixar_datasets_publicos.py \\
        --destino /dados/publicos --baixar

    # só o Open Images (não precisa de chave nenhuma)
    python3 scripts/ops/baixar_datasets_publicos.py --destino /dados/publicos \\
        --so oid --baixar

    # autoteste (não toca a rede)
    python3 scripts/ops/baixar_datasets_publicos.py autoteste

Rodar duas vezes não rebaixa o que já está no disco (idempotente): um dataset com
`PROCEDENCIA.json` completo é pulado, e as imagens do Open Images são conferidas
uma a uma por existência em disco.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

# ── Fontes aprovadas ─────────────────────────────────────────────────────────
# `licenca` é o valor que a fonte primária declarou na auditoria. Se a API
# devolver outro, a fonte é abortada (ver `_confere_licenca`).
#
# Conferido em 2026-09-02, via r.jina.ai (universe.roboflow.com devolve 403 a
# curl/WebFetch diretos — Cloudflare), lendo o bloco canônico de metadados
# `License[<nome>](<url>)` da página de cada dataset.

ROBOFLOW: list[dict] = [
    {
        "id": "r1",
        "nome": "Detector_EPP_Earmuff_Gloves_Mask",
        "workspace": "priscilas-workspace-6zp93",
        "projeto": "detector_epp_earmuff_gloves_mask",
        "url": "https://universe.roboflow.com/priscilas-workspace-6zp93/detector_epp_earmuff_gloves_mask",
        "licenca": "CC BY 4.0",
        "licenca_url": "https://creativecommons.org/licenses/by/4.0/",
        "imagens_declaradas": 17359,
        "classes_declaradas": ["mask", "earmuff", "gloves", "no earmuff", "no glove", "no mask"],
        "porque": "maior, industrial, 3 das nossas 5 classes COM as duas polaridades",
    },
    {
        "id": "r2",
        "nome": "Safety_PPE",
        "workspace": "safety-jmser",
        "projeto": "safety_ppe",
        "url": "https://universe.roboflow.com/safety-jmser/safety_ppe",
        "licenca": "CC BY 4.0",
        "licenca_url": "https://creativecommons.org/licenses/by/4.0/",
        "imagens_declaradas": 6629,
        "classes_declaradas": [
            "Helmet", "Glove", "Goggles", "Person", "Shoe", "Safety_Harness",
            "No_Glove", "No_Goggles", "No_Shoe", "No_Helmet", "No_Harness",
            "No_BreathingApparatus",
        ],
        "porque": "acrescenta Óculos com polaridade e `Person` (parte do corpo real)",
    },
    {
        "id": "r3",
        "nome": "Safety Gloves",
        "workspace": "roboflow-universe-projects",
        "projeto": "safety-gloves-xbnf8",
        "url": "https://universe.roboflow.com/roboflow-universe-projects/safety-gloves-xbnf8",
        "licenca": "CC BY 4.0",
        "licenca_url": "https://creativecommons.org/licenses/by/4.0/",
        # A auditoria registrou 3.4k; a página (v5) mostra 10.459 em 2026-09-02.
        # Contagem de imagem varia por VERSÃO do projeto — por isso o número
        # declarado não é gate; só a licença é. O real é medido pós-download.
        "imagens_declaradas": None,
        "classes_declaradas": ["Gloves", "NO-Gloves"],
        "porque": "reforço dirigido ao gargalo medido (Luvas, 304 caixas)",
    },
    {
        "id": "r6",
        "nome": "HAND NO GLOVES",
        "workspace": "harami-rdknl",
        "projeto": "hand-no-gloves",
        "url": "https://universe.roboflow.com/harami-rdknl/hand-no-gloves",
        "licenca": "Public Domain",
        "licenca_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "imagens_declaradas": 200,
        "classes_declaradas": [
            "vest", "glasses", "goggles", "person", "boots", "shoes",
            "face_mask", "face_nomask", "hand_glove", "hand_noglove",
            "head_helmet", "head_nohelmet",
        ],
        "porque": "CC0 (dispensa atribuição) e a única com 4 pares de polaridade juntos",
    },
]

# ── Open Images V7 ───────────────────────────────────────────────────────────
# Anotações: CC BY 4.0 (Google LLC). Imagens: declaradas CC BY 2.0, COM ressalva
# verbatim do próprio Google: "we make no representations or warranties regarding
# the license status of each image and you should verify the license for each
# image yourself."  — https://storage.googleapis.com/openimages/web/factsfigures_v7.html
#
# É o que destrava a VARIANTE C: nenhuma fonte pública de licença comercial anota
# mão/rosto/orelha como classe própria em cena (o SH17 anota, e é NC).
#
# Só validation+test. O train NÃO é baixado: são ~1,7M imagens e as caixas destas
# três classes só existem em validation+test mesmo.
OID_URLS = {
    "validation": "https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv",
    "test": "https://storage.googleapis.com/openimages/v5/test-annotations-bbox.csv",
}
OID_IMAGEM = "https://open-images-dataset.s3.amazonaws.com/{split}/{image_id}.jpg"
OID_PAGINA = "https://storage.googleapis.com/openimages/web/download_v7.html"

#: MID → nome. Medido em 2026-09-02 contando a coluna LabelName dos dois CSVs:
#:   cut -d, -f3 val-bbox.csv | grep -cx /m/0k65p   →  5031  (+ 15185 no test)
#:   Human hand 20.216 · Human face 22.602 · Human ear 4.451 (validation+test)
#: Bate com oidv7-class-descriptions-boxable.csv.
OID_CLASSES = {
    "/m/0k65p": "Human hand",
    "/m/0dzct": "Human face",
    "/m/039xj_": "Human ear",
}

OID = {
    "id": "oid",
    "nome": "Open Images V7 (Human hand/face/ear, validation+test)",
    "url": OID_PAGINA,
    "licenca": "CC BY 4.0",
    "licenca_url": "https://creativecommons.org/licenses/by/4.0/",
    "licenca_imagens": "CC BY 2.0 (declarada; o Google não garante — verificar por imagem)",
    "porque": "única fonte comercial com mão/rosto/orelha anotados em cena — destrava a variante C",
}

VAR_CHAVE_ROBOFLOW = "ROBOFLOW_API_KEY"


# ── Procedência (atribuição é obrigação do CC BY, não cortesia) ──────────────
def texto_atribuicao(fonte: dict) -> str:
    """Crédito exigido pelo CC BY 4.0, no formato TASL (Title/Author/Source/License)."""
    if "publicdomain" in fonte["licenca_url"]:
        return (
            f'"{fonte["nome"]}" está em domínio público (CC0 1.0). Atribuição\n'
            f"dispensada pela licença; registrada aqui por rastreabilidade.\n"
            f"Fonte: {fonte['url']}\n"
        )
    autor = fonte.get("workspace", "Google LLC")
    return (
        f'"{fonte["nome"]}" por {autor}, obtido em {fonte["url"]},\n'
        f"licenciado sob {fonte['licenca']} ({fonte['licenca_url']}).\n"
    )


def grava_procedencia(destino: Path, fonte: dict, extra: dict) -> Path:
    """Escreve PROCEDENCIA.json + ATRIBUICAO.txt AO LADO do dado."""
    destino.mkdir(parents=True, exist_ok=True)
    registro = {
        **{k: v for k, v in fonte.items() if k != "classes_declaradas"},
        "classes_declaradas": fonte.get("classes_declaradas"),
        "baixado_em": datetime.now(UTC).isoformat(),
        "atribuicao": texto_atribuicao(fonte).strip(),
        **extra,
    }
    caminho = destino / "PROCEDENCIA.json"
    caminho.write_text(json.dumps(registro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (destino / "ATRIBUICAO.txt").write_text(texto_atribuicao(fonte), encoding="utf-8")
    return caminho


def ja_baixado(destino: Path) -> bool:
    """Idempotência: PROCEDENCIA.json com `completo: true` = não rebaixa."""
    p = destino / "PROCEDENCIA.json"
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("completo") is True
    except (json.JSONDecodeError, OSError):
        return False


# ── Rede (stdlib; nenhuma dependência nova) ──────────────────────────────────
def _get(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (urls fixas acima)
        return r.read()


def _tamanho(url: str, timeout: int = 30) -> int | None:
    """Content-Length via HEAD. None se o servidor não disser."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            v = r.headers.get("Content-Length")
            return int(v) if v else None
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None


def _baixa_para(url: str, alvo: Path, timeout: int = 600) -> int:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    parcial = alvo.with_suffix(alvo.suffix + ".parcial")
    with urllib.request.urlopen(url, timeout=timeout) as r, parcial.open("wb") as fh:  # noqa: S310
        while chunk := r.read(1 << 20):
            fh.write(chunk)
    parcial.replace(alvo)  # só vira o arquivo final se completou
    return alvo.stat().st_size


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def humano(n: float | None) -> str:
    if n is None:
        return "?"
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}TB"


# ── Roboflow ─────────────────────────────────────────────────────────────────
def _confere_licenca(declarado_api: str | None, esperado: str, fonte_id: str) -> None:
    """Gate. Licença que a API declara TEM de bater com a auditada. Senão, aborta.

    A regra da casa é "licença não confirmada com fonte = NÃO PODE". Página e API
    são fontes distintas: divergência entre elas significa que o registro
    envelheceu, e envelhecido não é confirmado.
    """
    if declarado_api is None:
        raise RuntimeError(
            f"[{fonte_id}] a API não devolveu campo de licença. Não dá para confirmar; "
            f"não baixando. Reconfira na página e atualize a auditoria."
        )
    if declarado_api.strip().upper() != esperado.strip().upper():
        raise RuntimeError(
            f"[{fonte_id}] LICENÇA DIVERGENTE — auditada {esperado!r}, API diz "
            f"{declarado_api!r}. NÃO BAIXANDO. Reabra "
            f"docs/datasets/PPE_PRETRAIN_LICENSE_AUDIT.md antes de qualquer uso."
        )


def _chave_roboflow() -> str:
    chave = os.environ.get(VAR_CHAVE_ROBOFLOW, "").strip()
    if not chave:
        raise RuntimeError(
            f"falta a variável de ambiente {VAR_CHAVE_ROBOFLOW}.\n"
            f"  O download do Roboflow Universe exige API key (api.roboflow.com devolve\n"
            f"  401 sem ela, e universe.roboflow.com devolve 403 a curl — Cloudflare).\n"
            f"  Pegue em https://app.roboflow.com/settings/api e exporte:\n"
            f"      export {VAR_CHAVE_ROBOFLOW}=...\n"
            f"  Nenhuma credencial é inventada aqui e o Cloudflare não é contornado."
        )
    return chave


def roboflow_projeto(fonte: dict, chave: str) -> dict:
    """Metadados do projeto: licença declarada pela API + lista de versões."""
    url = f"https://api.roboflow.com/{fonte['workspace']}/{fonte['projeto']}?api_key={chave}"
    return json.loads(_get(url))


def roboflow_link_export(fonte: dict, versao: int, chave: str, formato: str = "coco") -> str:
    """Link do zip exportado. Não usa o SDK `roboflow` — dois GETs de stdlib bastam."""
    url = (
        f"https://api.roboflow.com/{fonte['workspace']}/{fonte['projeto']}"
        f"/{versao}/{formato}?api_key={chave}"
    )
    corpo = json.loads(_get(url, timeout=300))
    link = (corpo.get("export") or {}).get("link")
    if not link:
        raise RuntimeError(f"[{fonte['id']}] export sem link: {json.dumps(corpo)[:300]}")
    return link


def baixa_roboflow(fonte: dict, raiz: Path, baixar: bool) -> dict:
    destino = raiz / fonte["id"]
    if ja_baixado(destino):
        return {"id": fonte["id"], "estado": "já no disco (pulado)", "bytes": None}

    chave = _chave_roboflow()
    meta = roboflow_projeto(fonte, chave)
    proj = meta.get("project", meta)
    _confere_licenca(proj.get("license"), fonte["licenca"], fonte["id"])

    versoes = meta.get("versions") or []
    if not versoes:
        raise RuntimeError(f"[{fonte['id']}] projeto sem versões exportáveis")
    # id da versão vem como "workspace/projeto/N"
    versao = max(int(str(v["id"]).rsplit("/", 1)[-1]) for v in versoes)

    link = roboflow_link_export(fonte, versao, chave)
    tam = _tamanho(link)
    if not baixar:
        return {
            "id": fonte["id"], "estado": "dry-run", "bytes": tam,
            "versao": versao, "licenca_api": proj.get("license"),
            "imagens_api": proj.get("images"),
        }

    zipe = destino / "dataset.zip"
    n = _baixa_para(link, zipe)
    grava_procedencia(
        destino, fonte,
        {
            "versao": versao,
            "formato": "coco",
            "licenca_confirmada_pela_api": proj.get("license"),
            "imagens_segundo_a_api": proj.get("images"),
            "arquivo": zipe.name,
            "sha256": sha256(zipe),
            "bytes": n,
            "completo": True,
        },
    )
    return {"id": fonte["id"], "estado": "baixado", "bytes": n, "versao": versao}


# ── Open Images ──────────────────────────────────────────────────────────────
def filtra_oid(csv_bruto: Path, saida: Path) -> tuple[int, set[tuple[str, str]]]:
    """Deixa só as 3 classes que interessam. Devolve (n_caixas, {(split,image_id)})."""
    split = "validation" if "validation" in csv_bruto.name else "test"
    imagens: set[tuple[str, str]] = set()
    n = 0
    with csv_bruto.open(newline="") as fh, saida.open("w", newline="") as out:
        leitor = csv.DictReader(fh)
        campos = ["ImageID", "Split", "LabelName", "ClassName", "XMin", "XMax", "YMin", "YMax"]
        escritor = csv.DictWriter(out, fieldnames=campos)
        escritor.writeheader()
        for linha in leitor:
            nome = OID_CLASSES.get(linha["LabelName"])
            if not nome:
                continue
            n += 1
            imagens.add((split, linha["ImageID"]))
            escritor.writerow(
                {
                    "ImageID": linha["ImageID"], "Split": split,
                    "LabelName": linha["LabelName"], "ClassName": nome,
                    "XMin": linha["XMin"], "XMax": linha["XMax"],
                    "YMin": linha["YMin"], "YMax": linha["YMax"],
                }
            )
    return n, imagens


def baixa_oid(raiz: Path, baixar: bool, amostra_estimativa: int = 40) -> dict:
    destino = raiz / "oid"
    if ja_baixado(destino):
        return {"id": "oid", "estado": "já no disco (pulado)", "bytes": None}

    destino.mkdir(parents=True, exist_ok=True)
    caixas, imagens = 0, set()
    por_classe: dict[str, int] = dict.fromkeys(OID_CLASSES.values(), 0)
    csv_bytes = 0

    for split, url in OID_URLS.items():
        bruto = destino / f"{split}-annotations-bbox.csv"
        if not bruto.exists():
            tam = _tamanho(url)
            if not baixar:
                print(f"    {split}: CSV de caixas {humano(tam)} (ainda não baixado)")
                csv_bytes += tam or 0
                continue
            _baixa_para(url, bruto)
        csv_bytes += bruto.stat().st_size
        n, imgs = filtra_oid(bruto, destino / f"{split}-3classes.csv")
        caixas += n
        imagens |= imgs
        with (destino / f"{split}-3classes.csv").open(newline="") as fh:
            for linha in csv.DictReader(fh):
                por_classe[linha["ClassName"]] += 1

    faltando = [
        (s, i) for s, i in sorted(imagens)
        if not (destino / "images" / s / f"{i}.jpg").exists()
    ]

    if not baixar:
        return {"id": "oid", "estado": "dry-run", "bytes": csv_bytes or None,
                "caixas": caixas or None, "imagens": len(imagens) or None}

    # estimativa de tamanho ANTES de baixar as imagens — por AMOSTRA, e dita
    # como amostra. Estimativa nunca é apresentada como medida.
    if faltando:
        amostrados = [
            t for s, i in faltando[:amostra_estimativa]
            if (t := _tamanho(OID_IMAGEM.format(split=s, image_id=i)))
        ]
        media = sum(amostrados) / len(amostrados) if amostrados else 0
        print(
            f"    {len(faltando)} imagens a baixar. Estimativa: "
            f"{humano(media * len(faltando))} (média de {len(amostrados)} amostras "
            f"× {len(faltando)}; NÃO é medida do total)"
        )

    def _uma(par: tuple[str, str]) -> int:
        s, i = par
        alvo = destino / "images" / s / f"{i}.jpg"
        if alvo.exists():
            return alvo.stat().st_size
        try:
            return _baixa_para(OID_IMAGEM.format(split=s, image_id=i), alvo, timeout=120)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"      falhou {s}/{i}: {e}")
            return 0

    with ThreadPoolExecutor(max_workers=16) as pool:
        bytes_img = sum(pool.map(_uma, faltando))

    baixadas = sum(1 for s, i in imagens if (destino / "images" / s / f"{i}.jpg").exists())
    grava_procedencia(
        destino,
        {**OID, "classes_declaradas": list(OID_CLASSES.values())},
        {
            "splits": list(OID_URLS),
            "urls_anotacoes": OID_URLS,
            "url_imagens": OID_IMAGEM,
            "caixas_por_classe_medido": por_classe,
            "caixas_total_medido": caixas,
            "imagens_referenciadas": len(imagens),
            "imagens_no_disco": baixadas,
            "bytes_imagens": bytes_img,
            "completo": baixadas == len(imagens),
        },
    )
    return {"id": "oid", "estado": "baixado", "bytes": csv_bytes + bytes_img,
            "caixas": caixas, "imagens": baixadas, "por_classe": por_classe}


# ── Modos ────────────────────────────────────────────────────────────────────
def executa(raiz: Path, baixar: bool, so: list[str] | None) -> int:
    fontes = [*ROBOFLOW, OID]
    if so:
        fontes = [f for f in fontes if f["id"] in so]
        if not fontes:
            print(f"ERRO: nenhuma fonte com id em {so}. Ids: {[f['id'] for f in [*ROBOFLOW, OID]]}")
            return 1

    if not baixar:
        print("MODO DRY-RUN — nada é baixado. Use --baixar para valer.\n")
    print(f"destino: {raiz}\n")

    falhas, total = 0, 0
    for f in fontes:
        print(f"[{f['id']}] {f['nome']}")
        print(f"    licença: {f['licenca']}  ({f['licenca_url']})")
        print(f"    fonte:   {f['url']}")
        print(f"    porquê:  {f['porque']}")
        try:
            r = baixa_oid(raiz, baixar) if f["id"] == "oid" else baixa_roboflow(f, raiz, baixar)
            total += r.get("bytes") or 0
            extras = " ".join(
                f"{k}={v}" for k, v in r.items()
                if k not in ("id", "estado", "bytes", "por_classe") and v is not None
            )
            print(f"    → {r['estado']}  {humano(r['bytes'])}  {extras}".rstrip())
            if r.get("por_classe"):
                for c, n in r["por_classe"].items():
                    print(f"        {c}: {n} caixas")
        except (RuntimeError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            falhas += 1
            print(f"    ⛔ NÃO FOI POSSÍVEL: {e}")
        print()

    print(f"total {'baixado' if baixar else 'estimado'}: {humano(total)}")
    if falhas:
        print(f"{falhas} fonte(s) falharam — nada foi simulado, nada foi inventado.")
    return 1 if falhas else 0


def autoteste() -> int:
    """Checa o que dá para checar sem rede: gate de licença e procedência."""
    import tempfile

    # o gate reprova divergência, aceita igualdade e reprova ausência
    _confere_licenca("CC BY 4.0", "CC BY 4.0", "t")
    for api, esperado in (("CC BY-NC-SA 4.0", "CC BY 4.0"), (None, "CC BY 4.0")):
        try:
            _confere_licenca(api, esperado, "t")
            raise AssertionError(f"gate deixou passar {api!r}")
        except RuntimeError:
            pass

    # CC BY exige crédito; CC0 dispensa mas registra
    assert "CC BY 4.0" in texto_atribuicao(ROBOFLOW[0])
    assert "domínio público" in texto_atribuicao(ROBOFLOW[3])

    with tempfile.TemporaryDirectory() as d:
        alvo = Path(d) / "x"
        assert ja_baixado(alvo) is False
        grava_procedencia(alvo, ROBOFLOW[0], {"completo": False})
        assert ja_baixado(alvo) is False, "incompleto não pode contar como baixado"
        grava_procedencia(alvo, ROBOFLOW[0], {"completo": True})
        assert ja_baixado(alvo) is True
        assert (alvo / "ATRIBUICAO.txt").exists()

    assert not any("sh17" in json.dumps(f).lower() for f in ROBOFLOW), "SH17 é NC — vetado"
    print("autoteste: OK")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("modo", nargs="?", choices=["baixar", "autoteste"], default="baixar")
    p.add_argument("--destino", type=Path, default=Path("/dados/publicos"))
    p.add_argument("--baixar", action="store_true", help="baixa de verdade (padrão: dry-run)")
    p.add_argument("--so", nargs="+", metavar="ID", help="só estas fontes (r1 r2 r3 r6 oid)")
    args = p.parse_args()
    if args.modo == "autoteste":
        return autoteste()
    return executa(args.destino, args.baixar, args.so)


if __name__ == "__main__":
    sys.exit(main())
