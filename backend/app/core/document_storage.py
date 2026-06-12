from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import boto3


@dataclass
class StoredDocument:
    storage_backend: str
    object_key: str
    uri: str
    size_bytes: int
    content_type: str


class DocumentStorage:
    def __init__(self) -> None:
        self.backend = str(os.getenv("MYAI_STORAGE_BACKEND", "local")).strip().lower()

    def _sanitize_filename(self, filename: str) -> str:
        cleaned = "".join(char for char in filename if char.isalnum() or char in {"-", "_", "."})
        return cleaned[:160] or "upload.bin"

    def store(
        self,
        *,
        tenant_id: str,
        org_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> StoredDocument:
        if self.backend in {"minio", "s3"}:
            return self._store_minio(
                tenant_id=tenant_id,
                org_id=org_id,
                filename=filename,
                content_type=content_type,
                content=content,
            )
        return self._store_local(
            tenant_id=tenant_id,
            org_id=org_id,
            filename=filename,
            content_type=content_type,
            content=content,
        )

    def _store_local(
        self,
        *,
        tenant_id: str,
        org_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> StoredDocument:
        root = Path(os.getenv("MYAI_STORAGE_LOCAL_ROOT", str(Path.home() / ".myai" / "storage")))
        safe_name = self._sanitize_filename(filename)
        object_key = f"{tenant_id}/{org_id}/{uuid4().hex}/{safe_name}"
        destination = root / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return StoredDocument(
            storage_backend="local",
            object_key=object_key,
            uri=f"local://{object_key}",
            size_bytes=len(content),
            content_type=content_type,
        )

    def _store_minio(
        self,
        *,
        tenant_id: str,
        org_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> StoredDocument:
        endpoint = str(os.getenv("MYAI_STORAGE_S3_ENDPOINT", "http://localhost:9000")).strip()
        access_key = str(os.getenv("MYAI_STORAGE_S3_ACCESS_KEY", "")).strip()
        secret_key = str(os.getenv("MYAI_STORAGE_S3_SECRET_KEY", "")).strip()
        region = str(os.getenv("MYAI_STORAGE_S3_REGION", "us-east-1")).strip()
        bucket = str(os.getenv("MYAI_STORAGE_S3_BUCKET", "myai-documents")).strip()
        if not access_key or not secret_key:
            raise ValueError("Object storage credentials are not configured.")

        safe_name = self._sanitize_filename(filename)
        object_key = f"{tenant_id}/{org_id}/{uuid4().hex}/{safe_name}"
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            client.create_bucket(Bucket=bucket)

        client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=content,
            ContentType=content_type or "application/octet-stream",
        )

        return StoredDocument(
            storage_backend="minio",
            object_key=object_key,
            uri=f"s3://{bucket}/{object_key}",
            size_bytes=len(content),
            content_type=content_type,
        )


document_storage = DocumentStorage()
