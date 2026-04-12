"""
EPI Monitor V2 — Cloudflare R2 Storage (S3-compatível via boto3).

Diferenças do S3:
- endpoint_url: https://{account_id}.r2.cloudflarestorage.com
- region_name: "auto"
- Zero egress fees
"""
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.exceptions import StorageError
from app.infrastructure.storage.base import StorageStrategy

logger = logging.getLogger(__name__)


class R2Storage(StorageStrategy):
    """Implementação Cloudflare R2."""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
    ) -> None:
        self._bucket = bucket
        try:
            self._client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="auto",
            )
            logger.info("r2_storage_initialized: bucket=%s", bucket)
        except Exception as exc:
            raise StorageError(f"Falha ao inicializar R2: {exc}") from exc
        self._configure_cors()

    def _configure_cors(self) -> None:
        """Configura CORS no bucket para uploads diretos do browser (presigned URLs)."""
        try:
            self._client.put_bucket_cors(
                Bucket=self._bucket,
                CORSConfiguration={
                    "CORSRules": [{
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["PUT", "GET", "HEAD"],
                        "AllowedOrigins": ["*"],
                        "MaxAgeSeconds": 3600,
                    }]
                },
            )
            logger.info("r2_cors_configured: bucket=%s", self._bucket)
        except Exception as exc:  # noqa: BLE001
            logger.warning("r2_cors_config_skipped: %s", exc)

    def generate_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", ttl: int = 900
    ) -> str:
        """Gera URL para upload PUT direto."""
        try:
            return self._client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=ttl,
            )
        except ClientError as exc:
            raise StorageError(f"Presigned upload URL failed: {exc}") from exc

    def generate_presigned_download_url(self, key: str, ttl: int = 3600) -> str:
        """Gera URL para download GET."""
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl,
            )
        except ClientError as exc:
            raise StorageError(f"Presigned download URL failed: {exc}") from exc

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        """Upload bytes para R2."""
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            logger.debug("r2_upload: key=%s, size=%d", key, len(data))
        except ClientError as exc:
            raise StorageError(f"Upload failed for {key}: {exc}") from exc

    def download_bytes(self, key: str) -> bytes:
        """Download bytes do R2."""
        try:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            return response["Body"].read()
        except ClientError as exc:
            raise StorageError(f"Download failed for {key}: {exc}") from exc

    def upload_file(self, key: str, local_path: str) -> None:
        """Upload arquivo local para R2."""
        try:
            self._client.upload_file(local_path, self._bucket, key)
            logger.debug("r2_upload_file: key=%s, path=%s", key, local_path)
        except ClientError as exc:
            raise StorageError(f"File upload failed for {key}: {exc}") from exc

    def delete(self, key: str) -> None:
        """Deleta objeto do R2."""
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
            logger.debug("r2_delete: key=%s", key)
        except ClientError as exc:
            raise StorageError(f"Delete failed for {key}: {exc}") from exc

    def exists(self, key: str) -> bool:
        """Verifica se objeto existe no R2."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def list_keys(self, prefix: str) -> list[str]:
        """Lista chaves com prefixo no R2."""
        try:
            response = self._client.list_objects_v2(
                Bucket=self._bucket,
                Prefix=prefix,
            )
            return [obj["Key"] for obj in response.get("Contents", [])]
        except ClientError as exc:
            raise StorageError(f"List keys failed for {prefix}: {exc}") from exc
