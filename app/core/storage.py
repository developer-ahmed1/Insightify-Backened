"""
Cloudflare R2 storage client (S3-compatible).
"""
from typing import Optional
from uuid import uuid4
from datetime import date

import boto3
from botocore.config import Config

from app.config import settings
from app.core.exceptions import StorageServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageClient:
    """S3-compatible storage client for Cloudflare R2."""

    # File size limits in bytes
    MAX_SIZES = {
        "image": 5 * 1024 * 1024,    # 5MB
        "audio": 25 * 1024 * 1024,   # 25MB
        "video": 100 * 1024 * 1024,  # 100MB
    }

    # Allowed content types
    ALLOWED_TYPES = {
        "image": ["image/jpeg", "image/png", "image/webp", "image/gif"],
        "audio": ["audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4"],
        "video": ["video/mp4", "video/webm", "video/quicktime"],
    }

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key,
            aws_secret_access_key=settings.r2_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.bucket = settings.r2_bucket
        self.public_url = settings.r2_public_url

    def _get_media_type(self, content_type: str) -> str:
        """Get media type from content type."""
        return content_type.split("/")[0]

    def _validate_content_type(self, content_type: str) -> None:
        """Validate content type is allowed."""
        media_type = self._get_media_type(content_type)
        allowed = self.ALLOWED_TYPES.get(media_type, [])
        if content_type not in allowed:
            raise StorageServiceError(
                f"Unsupported content type: {content_type}. "
                f"Allowed: {', '.join(allowed)}"
            )

    def _get_max_size(self, content_type: str) -> int:
        """Get max file size for content type."""
        media_type = self._get_media_type(content_type)
        return self.MAX_SIZES.get(media_type, self.MAX_SIZES["image"])

    def generate_key(
        self,
        user_id: str,
        content_type: str,
        folder: str = "uploads",
    ) -> str:
        """Generate a unique storage key."""
        media_type = self._get_media_type(content_type)
        ext = content_type.split("/")[-1]
        # Handle special cases
        if ext == "quicktime":
            ext = "mov"
        elif ext == "mpeg":
            ext = "mp3"
        
        today = date.today().isoformat()
        file_id = uuid4().hex
        return f"{folder}/{media_type}/{user_id}/{today}/{file_id}.{ext}"

    async def generate_upload_url(
        self,
        user_id: str,
        content_type: str,
        folder: str = "uploads",
    ) -> dict:
        """
        Generate a presigned URL for client-side upload.
        
        Args:
            user_id: User ID for path organization
            content_type: MIME type of the file
            folder: Storage folder (uploads, avatars, etc.)
            
        Returns:
            Dict with upload_url, fields, and public_url
        """
        self._validate_content_type(content_type)
        
        key = self.generate_key(user_id, content_type, folder)
        max_size = self._get_max_size(content_type)

        try:
            presigned = self.client.generate_presigned_post(
                self.bucket,
                key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 0, max_size],
                ],
                ExpiresIn=3600,  # 1 hour
            )

            return {
                "upload_url": presigned["url"],
                "fields": presigned["fields"],
                "key": key,
                "public_url": f"{self.public_url}/{key}",
                "max_size_bytes": max_size,
            }
        except Exception as e:
            logger.error(f"Failed to generate upload URL: {e}")
            raise StorageServiceError(f"Failed to generate upload URL: {str(e)}")

    async def delete_file(self, key: str) -> None:
        """Delete a file from storage."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"Deleted file: {key}")
        except Exception as e:
            logger.error(f"Failed to delete file {key}: {e}")
            raise StorageServiceError(f"Failed to delete file: {str(e)}")

    async def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned download URL for private files."""
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate download URL: {e}")
            raise StorageServiceError(f"Failed to generate download URL: {str(e)}")


# Singleton instance
_storage_client: Optional[StorageClient] = None


def get_storage() -> StorageClient:
    """Get storage client instance."""
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client
