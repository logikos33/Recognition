"""
EPI Monitor V2 — Storage Strategy (Abstract).

Interface abstrata para storage. R2Storage implementa.
Permite trocar de R2 para S3 sem mudar código nas camadas superiores.
"""
from abc import ABC, abstractmethod


class StorageStrategy(ABC):
    """Abstração de object storage."""

    @abstractmethod
    def generate_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", ttl: int = 900
    ) -> str:
        """Gera URL presigned para upload direto do cliente."""
        ...

    @abstractmethod
    def generate_presigned_download_url(
        self, key: str, ttl: int = 3600, response_content_type: str | None = None
    ) -> str:
        """Gera URL presigned para download."""
        ...

    @abstractmethod
    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        """Upload de bytes para o storage."""
        ...

    @abstractmethod
    def download_bytes(self, key: str) -> bytes:
        """Download de bytes do storage."""
        ...

    @abstractmethod
    def upload_file(self, key: str, local_path: str) -> None:
        """Upload de arquivo local para o storage."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Deleta objeto do storage."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Verifica se objeto existe no storage."""
        ...

    @abstractmethod
    def list_keys(self, prefix: str) -> list[str]:
        """Lista chaves com o prefixo dado."""
        ...

    @abstractmethod
    def copy_object(self, src_key: str, dest_key: str) -> None:
        """Copia objeto de src_key para dest_key (server-side, sem download)."""
        ...
