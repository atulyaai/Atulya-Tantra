from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from tools import bootstrap
from tools.plugins.brain.local_llm import _extract_runtime


class _Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_bootstrap_download_checks_sha256_before_replacing_target(
    project_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"trusted asset"
    target = project_temp_dir / "asset.bin"
    target.write_bytes(b"existing verified asset")
    monkeypatch.setattr(bootstrap, "urlopen", lambda *_args, **_kwargs: _Response(content))

    with pytest.raises(OSError, match="integrity"):
        bootstrap._download("https://example.invalid/asset", target, expected_sha256="0" * 64)

    assert target.read_bytes() == b"existing verified asset"
    assert not target.with_suffix(".bin.part").exists()

    expected = hashlib.sha256(content).hexdigest()
    bootstrap._download("https://example.invalid/asset", target, expected_sha256=expected)
    assert target.read_bytes() == content


def test_runtime_tar_rejects_path_traversal(project_temp_dir: Path) -> None:
    archive_path = project_temp_dir / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        payload = b"outside"
        entry = tarfile.TarInfo("../outside.txt")
        entry.size = len(payload)
        archive.addfile(entry, io.BytesIO(payload))

    destination = project_temp_dir / "runtime"
    destination.mkdir()
    with pytest.raises(RuntimeError, match="unsafe path"):
        _extract_runtime(archive_path, destination)
    assert not (project_temp_dir / "outside.txt").exists()
