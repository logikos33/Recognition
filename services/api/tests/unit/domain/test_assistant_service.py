"""
Tests: assistant_service — build_prompt (pure) + retrieve_context (DB+ollama mocked).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from app.domain.services.assistant_service import (
    MAX_HISTORY,
    SYSTEM_PROMPT,
    build_prompt,
    retrieve_context,
)


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:

    def test_system_prompt_included(self):
        result = build_prompt("hi", [], [])
        assert SYSTEM_PROMPT in result

    def test_user_message_included(self):
        result = build_prompt("What is Recognition?", [], [])
        assert "What is Recognition?" in result

    def test_no_context_no_context_section(self):
        result = build_prompt("hi", [], [])
        assert "CONTEXTO" not in result

    def test_context_chunks_included(self):
        result = build_prompt("hi", ["Chunk A", "Chunk B"], [])
        assert "Chunk A" in result
        assert "Chunk B" in result

    def test_only_first_3_chunks_used(self):
        chunks = ["alpha-chunk", "beta-chunk", "gamma-chunk", "delta-chunk", "epsilon-chunk"]
        result = build_prompt("hi", chunks, [])
        assert "alpha-chunk" in result
        assert "beta-chunk" in result
        assert "gamma-chunk" in result
        assert "delta-chunk" not in result
        assert "epsilon-chunk" not in result

    def test_no_history_no_history_section(self):
        result = build_prompt("hi", [], [])
        assert "HISTÓRICO" not in result

    def test_history_included(self):
        history = [{"role": "user", "text": "Hello"}, {"role": "assistant", "text": "Hi"}]
        result = build_prompt("hi", [], history)
        assert "HISTÓRICO" in result
        assert "Hello" in result
        assert "Hi" in result

    def test_history_truncated_to_max(self):
        history = [{"role": "user", "text": f"msg{i:03d}"} for i in range(MAX_HISTORY + 5)]
        result = build_prompt("hi", [], history)
        # First 5 messages (oldest) should be dropped
        for i in range(5):
            assert f"msg{i:03d}" not in result
        # Last MAX_HISTORY messages should appear
        for i in range(5, MAX_HISTORY + 5):
            assert f"msg{i:03d}" in result

    def test_user_role_prefixed_with_usuario(self):
        history = [{"role": "user", "text": "Hello"}]
        result = build_prompt("hi", [], history)
        assert "Usuário:" in result

    def test_non_user_role_prefixed_with_assistente(self):
        history = [{"role": "assistant", "text": "Hi there"}]
        result = build_prompt("hi", [], history)
        assert "Assistente:" in result

    def test_response_marker_at_end(self):
        result = build_prompt("hi", [], [])
        assert "[RESPOSTA DO ASSISTENTE]" in result
        last_line = result.strip().split("\n")[-1]
        assert last_line == "[RESPOSTA DO ASSISTENTE]"


# ---------------------------------------------------------------------------
# retrieve_context
# ---------------------------------------------------------------------------

class TestRetrieveContext:

    def _mock_pool(self, rows):
        """Build a mock db_pool with getconn() context manager and cursor."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_pool = MagicMock()

        @contextmanager
        def _getconn():
            yield mock_conn

        mock_pool.getconn = _getconn
        return mock_pool, mock_cursor

    def test_returns_content_list(self):
        mock_pool, _ = self._mock_pool([("doc1",), ("doc2",)])
        mock_ollama = MagicMock()
        mock_ollama.embed.return_value = [0.1, 0.2, 0.3]
        result = retrieve_context("what is epi?", mock_pool, mock_ollama)
        assert result == ["doc1", "doc2"]

    def test_calls_embed_with_message(self):
        mock_pool, _ = self._mock_pool([])
        mock_ollama = MagicMock()
        mock_ollama.embed.return_value = []
        retrieve_context("test query", mock_pool, mock_ollama)
        mock_ollama.embed.assert_called_once_with("test query")

    def test_embedding_formatted_as_vector(self):
        mock_pool, mock_cursor = self._mock_pool([])
        mock_ollama = MagicMock()
        mock_ollama.embed.return_value = [0.5, 0.6]
        retrieve_context("q", mock_pool, mock_ollama)
        query, params = mock_cursor.execute.call_args[0]
        assert "[0.5,0.6]" in params[0]

    def test_exception_returns_empty_list(self):
        mock_ollama = MagicMock()
        mock_ollama.embed.side_effect = Exception("ollama down")
        result = retrieve_context("q", MagicMock(), mock_ollama)
        assert result == []

    def test_db_exception_returns_empty_list(self):
        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = Exception("DB unreachable")
        mock_ollama = MagicMock()
        mock_ollama.embed.return_value = [0.1]
        result = retrieve_context("q", mock_pool, mock_ollama)
        assert result == []

    def test_empty_rows_returns_empty_list(self):
        mock_pool, _ = self._mock_pool([])
        mock_ollama = MagicMock()
        mock_ollama.embed.return_value = [0.1]
        result = retrieve_context("q", mock_pool, mock_ollama)
        assert result == []
