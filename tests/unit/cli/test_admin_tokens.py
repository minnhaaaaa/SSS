from __future__ import annotations

import json
from hashlib import sha256

from sss_cli.admin import generate_token


def test_token_generator_outputs_digest_not_raw_token_in_record() -> None:
    generated = generate_token("agent-01", frozenset({"agent:check"}))
    encoded = json.dumps(generated.record.to_json())

    assert generated.raw_token not in encoded
    assert generated.record.token_sha256 == sha256(generated.raw_token.encode()).hexdigest()
    assert len(generated.raw_token) >= 43
