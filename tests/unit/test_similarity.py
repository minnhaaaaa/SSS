from __future__ import annotations

from sss_core.repositories.similarity import package_name_similarity


def test_similarity_uses_canonical_names_and_handles_empty_values() -> None:
    assert package_name_similarity("Django_REST.Framework", "django-rest-framework") == 1.0
    assert package_name_similarity("requests", "request") == 0.875
    assert package_name_similarity("", "anything") == 0.0
    assert package_name_similarity("", "") == 1.0
