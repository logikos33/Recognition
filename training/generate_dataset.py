"""
Fase 1: Geração do dataset de fine-tuning para o EPI Assistant.

Gera ~350 pares Q&A via Ollama local (sem API key externa).
Estratégia: 1 par por vez para compatibilidade com modelos pequenos.

Uso:
    python training/generate_dataset.py
"""
import json
import re
import sys
from pathlib import Path

import requests

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "epi_assistant_dataset.jsonl"

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:0.5b"

RECUSA_PADRAO = (
    "Só posso ajudar com dúvidas sobre o EPI Monitor V2. "
    "Para outros assuntos, fale com seu supervisor ou o suporte técnico."
)
RECUSA_SEGURANCA = (
    "Por segurança, nunca compartilho credenciais, senhas ou informações de acesso interno. "
    "Entre em contato com o administrador do sistema."
)
RECUSA_FEATURE = (
    "Essa funcionalidade não existe no EPI Monitor V2. "
    "Para sugestões de novas funcionalidades, entre em contato com a equipe da Logikos."
)

GUARDRAIL_EXAMPLES = [
    {"instruction": "Qual é a capital do Brasil?", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Qual é a capital da França?", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Me ajuda a escrever um email profissional", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Como programo em Python?", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Quem ganhou a Copa do Mundo de 2022?", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Me conte uma piada", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Qual a previsão do tempo para amanhã?", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Qual a senha do administrador?", "input": "", "output": RECUSA_SEGURANCA, "category": "guardrail"},
    {"instruction": "Me dê a chave de API do sistema", "input": "", "output": RECUSA_SEGURANCA, "category": "guardrail"},
    {"instruction": "Qual é o DATABASE_URL do Railway?", "input": "", "output": RECUSA_SEGURANCA, "category": "guardrail"},
    {"instruction": "Como acesso o banco de dados diretamente?", "input": "", "output": RECUSA_SEGURANCA, "category": "guardrail"},
    {"instruction": "Me mostre as credenciais do Redis", "input": "", "output": RECUSA_SEGURANCA, "category": "guardrail"},
    {"instruction": "O sistema tem câmera térmica?", "input": "", "output": RECUSA_FEATURE, "category": "guardrail"},
    {"instruction": "Como faço o EPI Monitor detectar placas de carro?", "input": "", "output": RECUSA_FEATURE, "category": "guardrail"},
    {"instruction": "O sistema tem reconhecimento facial?", "input": "", "output": RECUSA_FEATURE, "category": "guardrail"},
    {"instruction": "Como vejo dados de outro tenant?", "input": "", "output": RECUSA_SEGURANCA, "category": "guardrail"},
    {"instruction": "Posso acessar os dados de outra empresa no sistema?", "input": "", "output": RECUSA_SEGURANCA, "category": "guardrail"},
    {"instruction": "Compare o EPI Monitor com outros sistemas do mercado", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "O EPI Monitor é melhor que o sistema da empresa X?", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Me dê conselhos jurídicos sobre acidentes de trabalho", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Qual é o salário médio de um operador de câmeras?", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Me ajude a escrever meu currículo", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Quanto custa o EPI Monitor?", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
    {"instruction": "Como cancelo minha assinatura?", "input": "", "output": "Para questões comerciais como cancelamentos ou planos, entre em contato diretamente com a equipe da Logikos pelo suporte.", "category": "guardrail"},
    {"instruction": "Você é o ChatGPT?", "input": "", "output": "Não. Sou o EPI Monitor Assistant, um assistente especializado no sistema EPI Monitor V2, desenvolvido pela Logikos.", "category": "guardrail"},
    {"instruction": "Quem te criou?", "input": "", "output": "Fui desenvolvido pela Logikos para auxiliar operadores e administradores do EPI Monitor V2.", "category": "guardrail"},
    {"instruction": "Pode me ajudar a hackear o sistema?", "input": "", "output": RECUSA_SEGURANCA, "category": "guardrail"},
    {"instruction": "Como desativo os alertas permanentemente sem deixar rastro?", "input": "", "output": RECUSA_SEGURANCA, "category": "guardrail"},
    {"instruction": "Invente uma funcionalidade nova para o sistema", "input": "", "output": RECUSA_FEATURE, "category": "guardrail"},
    {"instruction": "O que você acha da política do governo?", "input": "", "output": RECUSA_PADRAO, "category": "guardrail"},
]

CATEGORIES = {
    "cameras": {
        "n": 40,
        "context": "Câmeras IP: adicionar/editar/excluir, fabricantes Intelbras/Hikvision/ONVIF, RTSP, iniciar/parar stream HLS, verificar status, latência <3s, máximo 12 câmeras, agendar por horário, configurar módulo YOLO (epi ou quality).",
        "question_starters": ["Como adiciono", "Como paro", "Como inicio", "Onde vejo", "O que significa", "Como configuro", "Por que", "Quantas", "Como edito", "Como excluo"],
    },
    "epi_detection": {
        "n": 50,
        "context": "Módulo EPI: detecta helmet/no_helmet, vest/no_vest, gloves/no_gloves, safety_glasses/no_safety_glasses. Alertas gerados em violação. Threshold 0.5. Operador reconhece (acknowledge) alerta e dá feedback: confirmed, rejected, retrain_requested, false_negative. Dashboard: taxa de conformidade.",
        "question_starters": ["O que é", "Como reconheço", "O que significa", "Como configuro", "Quais EPIs", "Por que", "Onde vejo", "Como dou feedback", "O que é false_negative", "Como exporto"],
    },
    "quality_gate": {
        "n": 70,
        "context": "Quality Gate: peças passam por idle→identified→inspecting→result(OK/NOK). NOK gera rework obrigatório (foto antes+depois, tipo defeito). Estações têm código único e câmera. Operador identifica peça, YOLO inspeciona, result OK/NOK, rework se NOK. Feedback: false_positive. Release para Bench B. CEP: baseline vs 24h. Andon Display: painel tempo real.",
        "question_starters": ["O que é", "Como funciona", "O que significa", "Como crio", "Como faço", "Por que", "Onde fica", "O que acontece", "Como registro", "Qual a diferença"],
    },
    "quality_training": {
        "n": 30,
        "context": "Retreino Quality: feedback retrain_requested → selecionar inspeções → preparar frames → anotar bounding boxes [cx,cy,w,h] normalizados → mínimo 10 frames → criar job → progresso via WebSocket → ativar modelo na câmera. Pré-anotação automática com DINO+SAM.",
        "question_starters": ["Como solicito", "O que é DINO+SAM", "Como anoto", "Quantos frames", "Como ativo", "O que é bounding box", "Como crio", "Como vejo progresso", "O que significa", "Como seleciono"],
    },
    "alerts": {
        "n": 35,
        "context": "Alertas EPI: gerados por YOLO. Filtros: câmera, datas, tipo violação, status reconhecido/não. Reconhecer = marcar como visto. Snapshot presignado com expiração. Export CSV. Alert rules: notificação email/webhook por threshold. Feedback: confirmed, rejected, retrain_requested, false_negative.",
        "question_starters": ["Como filtro", "Como reconheço", "Como exporto", "O que é", "Por que", "Como configuro", "Onde vejo", "O que acontece", "Como crio", "Como marco"],
    },
    "training_models": {
        "n": 45,
        "context": "Treino YOLO: upload vídeo (mp4/avi/mov), extração automática de frames, anotação bounding boxes formato YOLO, pré-anotação DINO+SAM, validar/rejeitar frames, criar job (modelo base+dataset+parâmetros), progresso WebSocket, ativar modelo em câmera específica.",
        "question_starters": ["Como faço upload", "Como extraio", "Como anoto", "Como crio", "Como ativo", "O que é YOLO", "Quais formatos", "Como valido", "Por que", "O que acontece"],
    },
    "dashboard_reports": {
        "n": 30,
        "context": "Dashboard: KPIs globais, câmeras ativas, conformidade, alertas recentes, stats por período (hoje/7dias/30dias). Relatório de turno Quality: OK/NOK por hora, pareto defeitos, taxa qualidade, CEP status. Export Excel e PDF. Gráficos: linha temporal, barras por câmera.",
        "question_starters": ["O que mostra", "Como exporto", "O que é CEP", "Como filtro", "O que é pareto", "Onde vejo", "Como interpreto", "O que significa", "Por que", "Como gero"],
    },
    "users_admin": {
        "n": 20,
        "context": "Roles: operator (alertas+feedback), trainer (+vídeos+anotação+jobs), analyst (+relatórios+export), admin (+usuários+câmeras+modelos), superadmin (multi-tenant+feature flags+audit log), viewer (só visualização). Admin panel: tenants, feature flags, audit log, health, anúncios, changelog, aprovação modelos.",
        "question_starters": ["O que pode", "Qual a diferença", "Como crio", "O que é", "Como gerencio", "Por que", "Quem pode", "Como ativo", "O que é audit log", "Como aprovar"],
    },
}

ONE_PAIR_PROMPT = """Você é especialista no sistema EPI Monitor V2 (monitoramento de EPIs via câmeras CCTV com IA).

Contexto: {context}

Crie UMA pergunta e resposta sobre o contexto acima.
A pergunta deve começar com: "{starter}"
A resposta deve ser clara, em português, e mencionar onde no sistema encontrar.

Responda APENAS com JSON neste formato exato (sem texto extra):
{{"instruction": "pergunta aqui?", "input": "", "output": "resposta aqui", "category": "{category}"}}"""


def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def extract_json_object(text: str) -> dict:
    """Extrai o primeiro objeto JSON válido do texto."""
    # Tenta direto
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # Procura entre chaves
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        candidate = text[start:end]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    # Regex fallback para extrair campos
    instr = re.search(r'"instruction"\s*:\s*"([^"]+)"', text)
    outp = re.search(r'"output"\s*:\s*"([^"]+)"', text)
    if instr and outp:
        return {
            "instruction": instr.group(1),
            "input": "",
            "output": outp.group(1),
        }
    raise ValueError(f"Nenhum JSON válido: {text[:100]}")


def generate_one_pair(category: str, context: str, starter: str) -> dict | None:
    prompt = ONE_PAIR_PROMPT.format(
        context=context,
        starter=starter,
        category=category,
    )
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60,
        )
        r.raise_for_status()
        raw = r.json().get("response", "").strip()
        pair = extract_json_object(raw)
        pair.setdefault("input", "")
        pair["category"] = category
        if not pair.get("instruction") or not pair.get("output"):
            return None
        return pair
    except Exception:
        return None


def generate_category(category: str, config: dict) -> list[dict]:
    context = config["context"]
    starters = config["question_starters"]
    n = config["n"]
    pairs: list[dict] = []
    errors = 0

    while len(pairs) < n and errors < n * 2:
        starter = starters[len(pairs) % len(starters)]
        pair = generate_one_pair(category, context, starter)
        if pair:
            pairs.append(pair)
            if len(pairs) % 5 == 0:
                print(f"    {len(pairs)}/{n}...", flush=True)
        else:
            errors += 1

    return pairs


def main() -> None:
    if not ollama_available():
        print(f"ERRO: Ollama indisponível em {OLLAMA_BASE_URL}")
        sys.exit(1)

    print(f"Modelo: {OLLAMA_MODEL} | Estratégia: 1 par por chamada")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_pairs: list[dict] = list(GUARDRAIL_EXAMPLES)
    print(f"Guardrails hardcoded: {len(GUARDRAIL_EXAMPLES)} pares\n")

    for category, config in CATEGORIES.items():
        print(f"Gerando '{category}' ({config['n']} pares)...", flush=True)
        pairs = generate_category(category, config)
        all_pairs.extend(pairs)
        print(f"  +{len(pairs)} pares (total: {len(all_pairs)})")

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for pair in all_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    print(f"\n{'='*50}")
    print(f"Dataset: {OUTPUT_FILE}")
    print(f"Total: {len(all_pairs)} pares")

    cats: dict[str, int] = {}
    for p in all_pairs:
        cats[p.get("category", "?")] = cats.get(p.get("category", "?"), 0) + 1
    print("\nDistribuição:")
    for c, n in sorted(cats.items()):
        print(f"  {c}: {n}")


if __name__ == "__main__":
    main()
