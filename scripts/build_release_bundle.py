from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "mood-radio-mcp"

INCLUDE_PATHS = (
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "Makefile",
    "README.md",
    "compose.yaml",
    "docs",
    "mood_radio_mcp",
    "pyproject.toml",
    "requirements.txt",
    "scripts",
    "tests",
    "uv.lock",
)

EXCLUDED_DIRS = {
    ".pytest_cache",
    "__pycache__",
    "data",
    "dist",
}


def project_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    return str(pyproject["project"]["version"])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_releasable_file(path: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return False
    if path.suffix in {".pyc", ".sqlite", ".db"}:
        return False
    if path.name.endswith((".sqlite-shm", ".sqlite-wal")):
        return False
    return path.is_file()


def collect_release_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for include_path in INCLUDE_PATHS:
        path = root / include_path
        if path.is_file():
            files.append(path.relative_to(root))
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if _is_releasable_file(child):
                    files.append(child.relative_to(root))
    return sorted(set(files), key=lambda item: item.as_posix())


def _add_file_to_tar(archive: tarfile.TarFile, source: Path, arcname: str) -> None:
    info = archive.gettarinfo(str(source), arcname)
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    with source.open("rb") as handle:
        archive.addfile(info, handle)


def build_release_bundle(root: Path = PROJECT_ROOT, output_dir: Path | None = None) -> dict[str, object]:
    root = root.resolve()
    version = project_version(root)
    output_dir = (output_dir or root / "dist").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    release_stem = f"{PROJECT_NAME}-{version}"
    archive_path = output_dir / f"{release_stem}.tar.gz"
    manifest_path = output_dir / f"{release_stem}.manifest.json"
    release_files = collect_release_files(root)

    with tarfile.open(archive_path, "w:gz") as archive:
        for relative_path in release_files:
            _add_file_to_tar(
                archive,
                root / relative_path,
                f"{release_stem}/{relative_path.as_posix()}",
            )

    manifest = {
        "project": PROJECT_NAME,
        "version": version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive": archive_path.name,
        "archive_sha256": sha256_file(archive_path),
        "file_count": len(release_files),
        "files": [
            {
                "path": relative_path.as_posix(),
                "size": (root / relative_path).stat().st_size,
                "sha256": sha256_file(root / relative_path),
            }
            for relative_path in release_files
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "archive_path": archive_path,
        "manifest_path": manifest_path,
        "manifest": manifest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Mood Radio MCP release tarball and checksum manifest.")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="Project root. Defaults to this repository.")
    parser.add_argument("--output-dir", default=None, help="Output directory. Defaults to <root>/dist.")
    args = parser.parse_args()

    result = build_release_bundle(
        root=Path(args.root),
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    manifest = result["manifest"]
    print("release_bundle_ok: True")
    print(f"archive: {result['archive_path']}")
    print(f"manifest: {result['manifest_path']}")
    print(f"archive_sha256: {manifest['archive_sha256']}")
    print(f"file_count: {manifest['file_count']}")


if __name__ == "__main__":
    main()
