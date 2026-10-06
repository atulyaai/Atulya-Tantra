import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_python_is_the_authoritative_package_and_webui_version():
    init = (ROOT / "atulya" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init, re.MULTILINE).group(1)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    webui = json.loads((ROOT / "webui" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "webui" / "package-lock.json").read_text(encoding="utf-8"))
    assert project["project"]["dynamic"] == ["version"]
    assert project["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "atulya.__version__"
    assert webui["version"] == version
    assert lock["version"] == version == lock["packages"][""]["version"]


def test_android_debug_apk_versions_follow_the_python_package(tmp_path):
    from webui.build_apk import apply_version

    gradle = tmp_path / "build.gradle"
    gradle.write_text("defaultConfig {\n    versionCode 1\n    versionName '1.0'\n}\n", encoding="utf-8")
    apply_version(gradle, "0.6.0")
    updated = gradle.read_text(encoding="utf-8")
    assert "versionCode 6000" in updated
    assert 'versionName "0.6.0"' in updated
