from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tarfile

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_release_bundle.py"
spec = importlib.util.spec_from_file_location("build_release_bundle", MODULE_PATH)
assert spec is not None
build_release_bundle = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(build_release_bundle)


def test_collect_release_files_includes_deploy_sources() -> None:
    root = Path(__file__).resolve().parents[1]
    files = {path.as_posix() for path in build_release_bundle.collect_release_files(root)}

    assert "Dockerfile" in files
    assert "assets/playmcp-icon.png" in files
    assert "Makefile" in files
    assert ".env.example" in files
    assert "mood_radio_mcp/server.py" in files
    assert "scripts/preflight_endpoint.py" in files
    assert "tests/test_tools.py" in files
    assert not any(path.startswith("dist/") for path in files)


def test_build_release_bundle_writes_archive_and_manifest(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    result = build_release_bundle.build_release_bundle(root=root, output_dir=tmp_path)
    archive_path = result["archive_path"]
    manifest_path = result["manifest_path"]

    assert archive_path.is_file()
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["project"] == "mood-radio-mcp"
    assert manifest["archive"] == archive_path.name
    assert manifest["archive_sha256"] == build_release_bundle.sha256_file(archive_path)
    assert manifest["file_count"] == len(manifest["files"])
    assert any(file["path"] == "Dockerfile" for file in manifest["files"])
    assert any(file["path"] == "assets/playmcp-icon.png" for file in manifest["files"])
    assert any(file["path"] == "Makefile" for file in manifest["files"])

    with tarfile.open(archive_path, "r:gz") as archive:
        names = set(archive.getnames())

    assert f"mood-radio-mcp-{manifest['version']}/Dockerfile" in names
    assert f"mood-radio-mcp-{manifest['version']}/assets/playmcp-icon.png" in names
    assert f"mood-radio-mcp-{manifest['version']}/Makefile" in names
    assert f"mood-radio-mcp-{manifest['version']}/mood_radio_mcp/server.py" in names
