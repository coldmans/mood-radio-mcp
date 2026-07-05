from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import tempfile

from fastmcp import Client
import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mood_radio_mcp.repository import MoodRadioRepository  # noqa: E402
from mood_radio_mcp.server import create_mcp  # noqa: E402
from mood_radio_mcp.tools import MoodRadioTools  # noqa: E402


EXPECTED_TOOLS = {
    "get_mailbox_info": set(),
    "recommend_song": {"delivery_id", "title", "artist", "message", "link", "nickname", "actor_hint"},
    "get_song": {"listener_hint", "avoid_seen"},
    "react_song": {"reaction", "post_id", "delivery_id", "reply_message", "actor_hint"},
    "get_song_chart": {"period", "limit"},
    "get_relay_board": {"limit"},
    "get_relay_chain": {"post_id", "delivery_id", "limit"},
    "get_share_card": {"post_id", "delivery_id"},
    "report_song": {"reason", "post_id", "delivery_id", "actor_hint"},
}

REQUIRED_FILES = (
    "Dockerfile",
    "Makefile",
    "compose.yaml",
    "README.md",
    "docs/deployment.md",
    "docs/playmcp-submission.md",
    "scripts/build_release_bundle.py",
    "scripts/reviewer_demo.py",
    "scripts/preflight_endpoint.py",
    "scripts/smoke_http.py",
)

REQUIRED_TEXT = {
    "Dockerfile": ("USER appuser", "PYTHONUNBUFFERED=1", "MOOD_RADIO_DB=/data/mood-radio.sqlite"),
    "Makefile": ("docker-smoke", "preflight_endpoint.py", "build_release_bundle.py"),
    ".dockerignore": ("dist/", "data/"),
    "README.md": ("/mcp", "/health", "actor_hint", "가사"),
    "docs/deployment.md": ("preflight_endpoint.py", "build_release_bundle.py", "MOOD_RADIO_POST_LIMIT"),
    "docs/playmcp-submission.md": ("노래우체통 MCP", "Review Prompts", "https://macmini.taild33a67.ts.net/mcp"),
}


async def inspect_tools(root: Path) -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = MoodRadioRepository(Path(temp_dir) / "audit.sqlite")
        mcp = create_mcp(repo)
        async with Client(mcp) as client:
            tools = await client.list_tools()

        found = {tool.name: tool for tool in tools}
        expected_names = set(EXPECTED_TOOLS)
        found_names = set(found)
        missing = sorted(expected_names - found_names)
        extra = sorted(found_names - expected_names)
        if missing:
            failures.append(f"missing tools: {', '.join(missing)}")
        if extra:
            failures.append(f"unexpected tools: {', '.join(extra)}")

        for name, expected_properties in EXPECTED_TOOLS.items():
            tool = found.get(name)
            if tool is None:
                continue
            schema_properties = set((tool.inputSchema.get("properties") or {}).keys())
            missing_properties = sorted(expected_properties - schema_properties)
            if missing_properties:
                failures.append(f"{name} missing input properties: {', '.join(missing_properties)}")
            if not tool.description:
                failures.append(f"{name} has no description")

        health = MoodRadioTools(repo).health()
        if health.get("ok") is not True:
            failures.append("health check did not return ok=True")
        if health.get("ready_for_feed") is not True:
            failures.append("seed data is not ready for feed")
        database = health.get("database") or {}
        for key in (
            "post_count",
            "visible_post_count",
            "hidden_post_count",
            "delivery_count",
            "reaction_count",
            "rate_limit_bucket_count",
        ):
            if key not in database:
                failures.append(f"health database missing key: {key}")

        transport = httpx.ASGITransport(app=mcp.http_app(transport="http"))
        async with httpx.AsyncClient(transport=transport, base_url="http://auditserver") as http_client:
            index_response = await http_client.get("/")
            health_response = await http_client.get("/health")

        if index_response.status_code != 200:
            failures.append(f"index route returned status: {index_response.status_code}")
        else:
            index_payload = index_response.json()
            if index_payload.get("service") != "mood-radio-mcp":
                failures.append("index route missing service identity")
            if (index_payload.get("endpoints") or {}).get("mcp") != "/mcp":
                failures.append("index route missing /mcp registration endpoint")
            if set(index_payload.get("tools") or []) != expected_names:
                failures.append("index route tool list does not match MCP tool list")

        if health_response.status_code != 200:
            failures.append(f"health route returned status: {health_response.status_code}")

    return failures


def inspect_files(root: Path) -> list[str]:
    failures: list[str] = []
    for file_name in REQUIRED_FILES:
        if not (root / file_name).is_file():
            failures.append(f"missing required file: {file_name}")

    for file_name, snippets in REQUIRED_TEXT.items():
        path = root / file_name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                failures.append(f"{file_name} missing text: {snippet}")

    return failures


async def audit(root: Path) -> list[str]:
    root = root.resolve()
    failures = []
    failures.extend(inspect_files(root))
    failures.extend(await inspect_tools(root))
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Song Mailbox MCP files and tool schema before PlayMCP submission.")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="Project root. Defaults to this repository.")
    args = parser.parse_args()

    failures = asyncio.run(audit(Path(args.root)))
    if failures:
        print("submission_audit_ok: False")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("submission_audit_ok: True")
    print(f"tools: {', '.join(EXPECTED_TOOLS)}")
    print("docs: README.md, docs/deployment.md, docs/playmcp-submission.md")


if __name__ == "__main__":
    main()
