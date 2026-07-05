from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from smoke_http import smoke


def _replace_path(url: str, path: str) -> str:
    parsed = urlparse(url)
    clean_path = "/" + path.strip("/")
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))


def derive_urls(endpoint: str) -> tuple[str, str, str]:
    raw = endpoint.strip().rstrip("/")
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("endpoint must be an absolute http(s) URL.")
    if parsed.path.endswith("/mcp"):
        return _replace_path(raw, "/"), _replace_path(raw, "/health"), raw
    if parsed.path.endswith("/health"):
        return _replace_path(raw, "/"), raw, _replace_path(raw, "/mcp")
    return _replace_path(raw, "/"), _replace_path(raw, "/health"), _replace_path(raw, "/mcp")


def check_metadata(metadata_url: str) -> dict[str, object]:
    with urlopen(metadata_url, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("ok") is not True:
        raise AssertionError(f"metadata route returned not ok: {payload}")
    if (payload.get("endpoints") or {}).get("mcp") != "/mcp":
        raise AssertionError(f"metadata route does not describe /mcp endpoint: {payload}")
    if "get_song" not in (payload.get("tools") or []):
        raise AssertionError(f"metadata route does not list MCP tools: {payload}")
    return payload


def check_health(health_url: str, *, require_feed: bool) -> dict[str, object]:
    with urlopen(health_url, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("ok") is not True:
        raise AssertionError(f"health check returned not ok: {payload}")
    if require_feed and payload.get("ready_for_feed") is not True:
        raise AssertionError(f"health check is ok but feed is not ready: {payload}")
    return payload


async def preflight(endpoint: str, *, require_feed: bool) -> None:
    metadata_url, health_url, mcp_url = derive_urls(endpoint)
    print("metadata:", metadata_url)
    metadata_payload = check_metadata(metadata_url)
    print("metadata_ok:", metadata_payload.get("ok"))
    print("service:", metadata_payload.get("service"))
    print("health:", health_url)
    health_payload = check_health(health_url, require_feed=require_feed)
    database = health_payload.get("database") or {}
    print("health_ok:", health_payload.get("ok"))
    print("ready_for_feed:", health_payload.get("ready_for_feed"))
    print(
        "database:",
        f"posts={database.get('post_count')}",
        f"visible={database.get('visible_post_count')}",
        f"hidden={database.get('hidden_post_count')}",
        f"deliveries={database.get('delivery_count')}",
        f"reactions={database.get('reaction_count')}",
        f"rate_limits={database.get('rate_limit_bucket_count')}",
    )
    print("mcp:", mcp_url)
    await smoke(mcp_url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight a deployed Song Mailbox MCP endpoint.")
    parser.add_argument("endpoint", help="Base URL, health URL, or MCP URL, e.g. https://example.com/mcp")
    parser.add_argument(
        "--allow-empty-feed",
        action="store_true",
        help="Pass health even when ready_for_feed is false.",
    )
    args = parser.parse_args()
    asyncio.run(preflight(args.endpoint, require_feed=not args.allow_empty_feed))


if __name__ == "__main__":
    main()
