"""
Recognition — Test Fixtures.

Fixtures para testes unitários e integração.
Storage é mockado (não chama R2 real).
Database pool é mockado para testes unitários.
"""
from unittest.mock import MagicMock

import pytest

from app import create_app
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.storage.base import StorageStrategy


class MockStorageStrategy(StorageStrategy):
    """Mock storage para testes — não chama R2 real."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def generate_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", ttl: int = 900
    ) -> str:
        return f"https://mock-r2.test/upload/{key}?ttl={ttl}"

    def generate_presigned_download_url(
        self, key: str, ttl: int = 3600, response_content_type: str | None = None
    ) -> str:
        return f"https://mock-r2.test/download/{key}?ttl={ttl}"

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self._store[key] = data

    def download_bytes(self, key: str) -> bytes:
        if key not in self._store:
            raise FileNotFoundError(f"Key not found: {key}")
        return self._store[key]

    def upload_file(self, key: str, local_path: str) -> None:
        self._store[key] = b"file-content"

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self._store

    def list_keys(self, prefix: str) -> list[str]:
        return [k for k in self._store if k.startswith(prefix)]

    def copy_object(self, src_key: str, dest_key: str) -> None:
        if src_key in self._store:
            self._store[dest_key] = self._store[src_key]


@pytest.fixture
def app():
    """Flask app para testes."""
    application = create_app("testing")
    yield application


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def mock_storage():
    """Mock storage strategy."""
    return MockStorageStrategy()


@pytest.fixture
def mock_db_pool():
    """Mock database pool para testes unitários."""
    pool = MagicMock(spec=DatabasePool)
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    pool.get_connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
    pool.get_connection.return_value.__exit__ = MagicMock(return_value=False)
    return pool, mock_conn, mock_cursor
