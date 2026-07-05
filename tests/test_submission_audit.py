from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "submission_audit.py"
spec = importlib.util.spec_from_file_location("submission_audit", MODULE_PATH)
assert spec is not None
submission_audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(submission_audit)


def test_submission_audit_passes_for_project_root() -> None:
    failures = asyncio.run(submission_audit.audit(Path(__file__).resolve().parents[1]))

    assert failures == []


def test_submission_audit_detects_missing_docs(tmp_path: Path) -> None:
    failures = submission_audit.inspect_files(tmp_path)

    assert any("README.md" in failure for failure in failures)
