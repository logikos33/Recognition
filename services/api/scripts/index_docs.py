"""
Fase 3: Indexa documentação do sistema no pgvector para RAG.

Pré-requisitos:
  - Ollama rodando com nomic-embed-text: ollama pull nomic-embed-text
  - Migration 036 aplicada: psql epi_monitor -f migrations/036_pgvector_assistant.sql
  - .env.local com DATABASE_URL e OLLAMA_BASE_URL

Uso:
    cd backend
    set -a && source .env.local && set +a
    python scripts/index_docs.py
"""
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

DOCS = [
    (ROOT / "CLAUDE.md", "CLAUDE.md"),
]

# Adiciona descrições das páginas dos módulos frontend
FRONTEND_PAGES = ROOT / "frontend" / "src" / "modules"
if FRONTEND_PAGES.exists():
    for tsx in FRONTEND_PAGES.rglob("*.tsx"):
        if "pages" in tsx.parts:
            DOCS.append((tsx, f"frontend/{tsx.name}"))

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    embed_model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    if not db_url:
        print("ERRO: DATABASE_URL não definida")
        sys.exit(1)

    import psycopg2
    import requests

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Limpa docs anteriores para reindexação limpa
    cur.execute("DELETE FROM assistant_docs")
    conn.commit()

    total = 0
    for doc_path, source_name in DOCS:
        if not doc_path.exists():
            print(f"  Pulando {source_name} (não encontrado)")
            continue

        text = doc_path.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text)
        print(f"Indexando {source_name} ({len(chunks)} chunks)...")

        for chunk in chunks:
            if len(chunk.strip()) < 50:
                continue
            try:
                r = requests.post(
                    f"{ollama_url}/api/embeddings",
                    json={"model": embed_model, "prompt": chunk},
                    timeout=30,
                )
                r.raise_for_status()
                embedding = r.json()["embedding"]
                vec_str = "[" + ",".join(str(x) for x in embedding) + "]"

                cur.execute(
                    "INSERT INTO assistant_docs (id, content, embedding, source) VALUES (%s, %s, %s::vector, %s)",
                    (str(uuid.uuid4()), chunk, vec_str, source_name),
                )
                total += 1
            except Exception as e:
                print(f"  Erro no chunk: {e}")

        conn.commit()

    cur.close()
    conn.close()
    print(f"\nIndexação concluída: {total} chunks inseridos.")
    print("Verifique: psql epi_monitor -c \"SELECT count(*) FROM assistant_docs;\"")


if __name__ == "__main__":
    main()
