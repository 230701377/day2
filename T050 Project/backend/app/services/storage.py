import os
import io
import hashlib
from pathlib import Path
from typing import BinaryIO, Optional

from app.core.config import settings


class LocalStorage:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _full(self, key: str) -> Path:
        safe = key.replace("..", "_")
        p = self.base_path / safe
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put(self, key: str, data: bytes) -> str:
        path = self._full(key)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._full(key).read_bytes()

    def open(self, key: str) -> BinaryIO:
        return open(self._full(key), "rb")

    def delete(self, key: str) -> None:
        p = self._full(key)
        if p.exists():
            p.unlink()

    def exists(self, key: str) -> bool:
        return self._full(key).exists()


def get_storage():
    if settings.STORAGE_BACKEND == "s3" and settings.S3_ENDPOINT_URL:
        try:
            import boto3
            client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
            )
            return _S3Storage(client, settings.S3_BUCKET)
        except Exception:
            pass
    return LocalStorage(settings.STORAGE_LOCAL_PATH)


class _S3Storage:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def put(self, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def get(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def open(self, key: str) -> BinaryIO:
        return io.BytesIO(self.get(key))

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_stream(stream: BinaryIO, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    stream.seek(0)
    while True:
        b = stream.read(chunk)
        if not b:
            break
        h.update(b)
    stream.seek(0)
    return h.hexdigest()
