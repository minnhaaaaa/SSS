from __future__ import annotations

from packaging.utils import canonicalize_name


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def package_name_similarity(left: str, right: str) -> float:
    canonical_left = str(canonicalize_name(left)) if left else ""
    canonical_right = str(canonicalize_name(right)) if right else ""
    maximum = max(len(canonical_left), len(canonical_right))
    if maximum == 0:
        return 1.0
    return round(1 - (_edit_distance(canonical_left, canonical_right) / maximum), 6)
