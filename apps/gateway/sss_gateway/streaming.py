"""Bounded artifact streaming with an incremental SHA-256 digest."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterable, AsyncIterator


class ArtifactTooLargeError(ValueError):
    """Raised as soon as an artifact crosses its configured byte limit."""


class BoundedHashingStream:
    def __init__(self, source: AsyncIterable[bytes], *, max_bytes: int) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self._source = source
        self._max_bytes = max_bytes
        self._size = 0
        self._hasher = hashlib.sha256()
        self._complete = False

    @property
    def bytes_seen(self) -> int:
        return self._size

    @property
    def sha256(self) -> str:
        if not self._complete:
            raise RuntimeError("digest is unavailable until the stream completes")
        return self._hasher.hexdigest()

    async def __aiter__(self) -> AsyncIterator[bytes]:
        if self._complete or self._size:
            raise RuntimeError("artifact stream can only be consumed once")
        async for chunk in self._source:
            if not chunk:
                continue
            proposed = self._size + len(chunk)
            if proposed > self._max_bytes:
                raise ArtifactTooLargeError(
                    f"artifact exceeds configured limit of {self._max_bytes} bytes"
                )
            self._size = proposed
            self._hasher.update(chunk)
            yield chunk
        self._complete = True
