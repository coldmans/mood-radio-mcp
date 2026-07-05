from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "reviewer_demo.py"
spec = importlib.util.spec_from_file_location("reviewer_demo", MODULE_PATH)
assert spec is not None
reviewer_demo = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(reviewer_demo)


def test_reviewer_demo_builds_markdown_transcript(tmp_path: Path) -> None:
    markdown = asyncio.run(reviewer_demo.build_demo(db_path=tmp_path / "demo.sqlite"))

    assert "# 무드라디오 MCP 심사 데모" in markdown
    assert "Tool: `get_song`" in markdown
    assert "matched_mood: 퇴근길" in markdown
    assert "Tool: `pass_song`" in markdown
    assert "Tool: `get_share_card`" in markdown
    assert "relay_chain_length" in markdown
