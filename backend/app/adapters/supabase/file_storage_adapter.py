"""
Supabase File Storage adapter.

Implements FileStorageRepository using Supabase Storage buckets.

Extracted from app.services.storage (lines 269–333).
"""

import logging
from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseFileStorageAdapter:
    """
    Concrete FileStorageRepository backed by Supabase Storage.

    Handles binary file upload/download operations for PDFs and other assets.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    # -- FileStorageRepository Protocol ----------------------------------------

    def upload(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: str,
        bucket_name: str = "course_materials",
    ) -> str:
        """
        Upload PDF file to Supabase Storage.

        Args:
            file_bytes: PDF file bytes
            filename: Original filename
            user_id: User ID for organizing files
            bucket_name: Storage bucket name

        Returns:
            Storage path of uploaded file

        Raises:
            Exception: If upload fails
        """
        storage_path = f"{user_id}/{filename}"

        try:
            self._client.storage.from_(bucket_name).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "application/pdf", "upsert": "true"},
            )
            return storage_path
        except Exception as e:
            raise Exception(f"Failed to upload PDF to storage: {str(e)}")

    def download(
        self,
        path: str,
        bucket_name: str = "course_materials",
    ) -> bytes:
        """
        Download a file from Supabase Storage.

        Args:
            path: Storage path of the file
            bucket_name: Storage bucket name

        Returns:
            File content as bytes

        Raises:
            Exception: If download fails
        """
        try:
            response = self._client.storage.from_(bucket_name).download(path)
            return response
        except Exception as e:
            raise Exception(f"Failed to download file from storage: {str(e)}")
