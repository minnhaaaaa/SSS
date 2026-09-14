from __future__ import annotations

import re

from sss_core.extraction import UnsafeInputError

_SHELL_OPERATOR = re.compile(r"&&|[;|`]|\$\(|(?:^|\s)(?:<|>|<<|>>)(?:\s|$)")


def reject_shell_operators(text: str) -> None:
    if _SHELL_OPERATOR.search(text):
        raise UnsafeInputError("shell operators and substitutions are not accepted")
