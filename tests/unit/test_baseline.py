from __future__ import annotations

from sss_worker.jobs.baseline import BaselineBuilder


def test_pypi_baseline_is_sorted_and_reproducible() -> None:
    builder = BaselineBuilder(normalization_version="pep503-v1")

    first = builder.build(["Zope.Interface", "django_rest_framework", "Requests"])
    second = builder.build(["Requests", "Zope.Interface", "django-rest-framework"])

    assert first.content == b"django-rest-framework\nrequests\nzope-interface\n"
    assert second.content == first.content
    assert second.sha256 == first.sha256
    assert second.project_count == 3
