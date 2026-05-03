"""Serviço do EPI Assistant — RAG retrieval + montagem de prompt."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Você é o EPI Monitor Assistant, assistente especializado no sistema "
    "EPI Monitor V2. Responda apenas sobre funcionalidades, fluxos e dúvidas "
    "relacionadas à plataforma. Seja direto e claro em português."
)

MAX_HISTORY = 6  # últimas N mensagens do histórico


def build_prompt(
    message: str,
    context_chunks: list[str],
    history: list[dict[str, str]],
) -> str:
    """Monta o prompt final com sistema + contexto RAG + histórico + pergunta."""
    parts = [f"[SISTEMA]\n{SYSTEM_PROMPT}"]

    if context_chunks:
        ctx = "\n---\n".join(context_chunks[:3])
        parts.append(f"[CONTEXTO RELEVANTE DA DOCUMENTAÇÃO]\n{ctx}")

    if history:
        recent = history[-MAX_HISTORY:]
        hist_lines = []
        for msg in recent:
            role = "Usuário" if msg.get("role") == "user" else "Assistente"
            hist_lines.append(f"{role}: {msg.get('text', '')}")
        parts.append("[HISTÓRICO DA CONVERSA]\n" + "\n".join(hist_lines))

    parts.append(f"[PERGUNTA DO USUÁRIO]\n{message}")
    parts.append("[RESPOSTA DO ASSISTENTE]")

    return "\n\n".join(parts)


def retrieve_context(
    message: str,
    db_pool: Any,
    ollama_client: Any,
    top_k: int = 3,
) -> list[str]:
    """Busca chunks relevantes via similaridade coseno no pgvector."""
    try:
        embedding = ollama_client.embed(message)
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"

        with db_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content
                    FROM assistant_docs
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vec_str, top_k),
                )
                rows = cur.fetchall()
            db_pool.putconn(conn)

        return [row[0] for row in rows]
    except Exception as exc:
        logger.warning("rag_retrieval_failed: %s", exc)
        return []
