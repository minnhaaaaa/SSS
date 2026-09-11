from __future__ import annotations

import io
import stat
import tarfile
import zipfile

import pytest
from sss_gateway.artifacts import ArchiveLimits, UnsafeArchiveError, inspect_tar, inspect_zip
from sss_gateway.artifacts.common import validate_entry_path


@pytest.fixture
def limits() -> ArchiveLimits:
    return ArchiveLimits(
        max_compressed_bytes=100_000,
        max_expanded_bytes=10_000,
        max_entries=4,
        max_file_bytes=5_000,
        max_compression_ratio=50,
    )


def _zip(entries: list[tuple[str, bytes]]) -> io.BytesIO:
    result = io.BytesIO()
    with zipfile.ZipFile(result, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    result.seek(0)
    return result


def _tar(entries: list[tuple[str, bytes]], *, link: tuple[str, str] | None = None) -> io.BytesIO:
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:gz") as archive:
        for name, content in entries:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        if link:
            info = tarfile.TarInfo(link[0])
            info.type = tarfile.SYMTYPE
            info.linkname = link[1]
            archive.addfile(info)
    result.seek(0)
    return result


def test_zip_inspection_returns_bounded_metadata(limits: ArchiveLimits) -> None:
    result = inspect_zip(_zip([("package/index.js", b"safe")]), limits=limits)

    assert result.format == "zip"
    assert result.entry_count == 1
    assert result.expanded_bytes == 4


@pytest.mark.parametrize(
    "name",
    ["../escape", "/absolute", "C:/absolute", "C:relative", "package//module.py", "./file"],
)
def test_zip_rejects_unsafe_paths(name: str, limits: ArchiveLimits) -> None:
    with pytest.raises(UnsafeArchiveError):
        inspect_zip(_zip([(name, b"unsafe")]), limits=limits)


def test_common_path_validation_rejects_windows_separator() -> None:
    with pytest.raises(UnsafeArchiveError):
        validate_entry_path("package\\escape")


def test_zip_rejects_links(limits: ArchiveLimits) -> None:
    source = io.BytesIO()
    with zipfile.ZipFile(source, mode="w") as archive:
        link = zipfile.ZipInfo("package/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "target")
    source.seek(0)

    with pytest.raises(UnsafeArchiveError, match="links"):
        inspect_zip(source, limits=limits)


def test_zip_rejects_too_many_entries(limits: ArchiveLimits) -> None:
    entries = [(f"package/{index}", b"x") for index in range(limits.max_entries + 1)]

    with pytest.raises(UnsafeArchiveError, match="too many"):
        inspect_zip(_zip(entries), limits=limits)


def test_zip_rejects_duplicate_casefolded_paths(limits: ArchiveLimits) -> None:
    with pytest.raises(UnsafeArchiveError, match="duplicate"):
        inspect_zip(
            _zip([("package/Module.py", b"first"), ("package/module.py", b"second")]),
            limits=limits,
        )


def test_zip_rejects_oversized_file(limits: ArchiveLimits) -> None:
    with pytest.raises(UnsafeArchiveError, match="file-size"):
        inspect_zip(_zip([("package/large", b"x" * 5_001)]), limits=limits)


def test_tar_inspection_returns_bounded_metadata(limits: ArchiveLimits) -> None:
    result = inspect_tar(_tar([("package/module.py", b"safe")]), limits=limits)

    assert result.format == "tar"
    assert result.entry_count == 1
    assert result.expanded_bytes == 4


def test_tar_rejects_traversal(limits: ArchiveLimits) -> None:
    with pytest.raises(UnsafeArchiveError, match="extraction root"):
        inspect_tar(_tar([("../escape", b"unsafe")]), limits=limits)


def test_tar_rejects_links(limits: ArchiveLimits) -> None:
    with pytest.raises(UnsafeArchiveError, match="links and special"):
        inspect_tar(_tar([], link=("package/link", "../target")), limits=limits)


def test_tar_rejects_duplicate_casefolded_paths(limits: ArchiveLimits) -> None:
    with pytest.raises(UnsafeArchiveError, match="duplicate"):
        inspect_tar(
            _tar([("package/Module.py", b"first"), ("package/module.py", b"second")]),
            limits=limits,
        )


def test_invalid_archives_fail_closed(limits: ArchiveLimits) -> None:
    with pytest.raises(UnsafeArchiveError, match="invalid ZIP"):
        inspect_zip(io.BytesIO(b"not a zip"), limits=limits)
    with pytest.raises(UnsafeArchiveError, match="invalid tar"):
        inspect_tar(io.BytesIO(b"not a tar"), limits=limits)
