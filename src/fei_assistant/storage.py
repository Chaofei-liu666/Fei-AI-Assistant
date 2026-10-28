from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import boto3

from .config import Settings, get_settings


SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def make_object_key(category: str, object_id: str, filename: str) -> str:
    safe_category = SAFE_NAME.sub("_", category).strip("._") or "files"
    safe_id = SAFE_NAME.sub("_", object_id).strip("._")
    if not safe_id:
        raise ValueError("invalid object id")
    safe_name = SAFE_NAME.sub("_", Path(filename).name).strip(".") or "upload"
    return f"{safe_category}/{safe_id}/{safe_name}"


@dataclass(frozen=True)
class StoredObject:
    key: str
    sha256: str
    size: int


class ObjectStorage:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.bucket = self.settings.minio_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=self.settings.minio_endpoint,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
            use_ssl=self.settings.minio_secure,
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, category: str, object_id: str, filename: str, data: bytes, content_type: str) -> StoredObject:
        key = make_object_key(category, object_id, filename)
        self.ensure_bucket()
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return StoredObject(key=key, sha256=hashlib.sha256(data).hexdigest(), size=len(data))

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def download_url(self, key: str, expires: int = 300) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires
        )
