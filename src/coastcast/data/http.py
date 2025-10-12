"""HTTP client with bounded retries and provider-friendly caching."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)


class CachedHttpClient:
    def __init__(
        self,
        cache_dir: Path,
        timeout_seconds: int,
        retries: int,
        backoff_seconds: float,
        user_agent: str,
    ) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.client = httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent, "Accept": "application/json, application/xml"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def get(self, url: str, params: dict[str, Any], suffix: str) -> bytes:
        request = self.client.build_request("GET", url, params=params)
        key = hashlib.sha256(str(request.url).encode()).hexdigest()
        cache_path = self.cache_dir / f"{key}.{suffix}"
        metadata_path = self.cache_dir / f"{key}.metadata.json"
        if cache_path.exists():
            LOGGER.info("cache hit: %s", request.url)
            payload = cache_path.read_bytes()
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                expected = metadata.get("content_sha256")
                observed = hashlib.sha256(payload).hexdigest()
                if expected and expected != observed:
                    raise RuntimeError(f"Cached response checksum mismatch: {cache_path}")
            return payload

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.client.send(request)
                if response.status_code in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                response.raise_for_status()
                payload = response.content
                temporary_cache = cache_path.with_suffix(cache_path.suffix + ".tmp")
                temporary_metadata = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
                temporary_cache.write_bytes(payload)
                temporary_metadata.write_text(
                    json.dumps(
                        {
                            "cache_key": key,
                            "url": str(request.url),
                            "status_code": response.status_code,
                            "content_type": response.headers.get("content-type"),
                            "retrieved_at_utc": datetime.now(UTC).isoformat(),
                            "content_bytes": len(payload),
                            "content_sha256": hashlib.sha256(payload).hexdigest(),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                temporary_cache.replace(cache_path)
                temporary_metadata.replace(metadata_path)
                return payload
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                if attempt == self.retries:
                    break
                delay = self.backoff_seconds * (2 ** (attempt - 1))
                LOGGER.warning("request failed, retrying in %.1f seconds: %s", delay, exc)
                time.sleep(delay)
        raise RuntimeError(
            f"Request failed after {self.retries} attempts: {request.url}"
        ) from last_error
