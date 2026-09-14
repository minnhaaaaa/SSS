from __future__ import annotations

import hashlib

import pytest
from sss_gateway.streaming import ArtifactTooLargeError, BoundedHashingStream


async def chunks(*values: bytes):
    for value in values:
        yield value


@pytest.mark.asyncio
async def test_stream_hashes_bytes_without_buffering() -> None:
    stream = BoundedHashingStream(chunks(b"abc", b"def"), max_bytes=6)
    observed = [chunk async for chunk in stream]

    assert observed == [b"abc", b"def"]
    assert stream.bytes_seen == 6
    assert stream.sha256 == hashlib.sha256(b"abcdef").hexdigest()


@pytest.mark.asyncio
async def test_stream_stops_when_size_limit_is_crossed() -> None:
    stream = BoundedHashingStream(chunks(b"abcd", b"ef"), max_bytes=5)

    with pytest.raises(ArtifactTooLargeError):
        _ = [chunk async for chunk in stream]

    assert stream.bytes_seen == 4
