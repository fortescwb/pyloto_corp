"""Exportador para GCS."""

from __future__ import annotations

from datetime import UTC, datetime

from google.cloud import storage


class GCSHistoryExporter:
    """Persiste exports em bucket GCS (não público)."""

    def __init__(self, bucket_name: str, client: storage.Client | None = None) -> None:
        self._bucket_name = bucket_name
        self._client = client or storage.Client()

    def save(self, *, user_key: str, content: bytes, content_type: str = "text/plain") -> str:
        now = datetime.now(tz=UTC)
        object_name = (
            f"exports/conversations/{user_key}/{now.strftime('%Y%m%d_%H%M%S')}_history.txt"
        )
        bucket = self._client.bucket(self._bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_string(content, content_type=content_type)
        # Versioning/WORM: deve ser configurado no bucket (documentado em docs/security.md)
        return f"gs://{self._bucket_name}/{object_name}"
