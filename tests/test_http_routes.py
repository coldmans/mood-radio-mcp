from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from mood_radio_mcp.repository import MoodRadioRepository
from mood_radio_mcp.server import create_mcp


def test_index_route_describes_registration_endpoint(tmp_path: Path) -> None:
    async def run() -> httpx.Response:
        mcp = create_mcp(MoodRadioRepository(tmp_path / "index.sqlite"))
        transport = httpx.ASGITransport(app=mcp.http_app(transport="http"))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/")

    response = asyncio.run(run())

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "mood-radio-mcp"
    assert payload["name"] == "노래우체통 MCP"
    assert payload["endpoints"]["mcp"] == "/mcp"
    assert payload["endpoints"]["health"] == "/health"
    assert "PlayMCP" in payload["playmcp_registration"]
    assert "get_song" in payload["tools"]
    assert "lyrics" in payload["safety"]["does_not_store"]


def test_health_route_reports_ready_database(tmp_path: Path) -> None:
    async def run() -> httpx.Response:
        mcp = create_mcp(MoodRadioRepository(tmp_path / "health.sqlite"))
        transport = httpx.ASGITransport(app=mcp.http_app(transport="http"))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/health")

    response = asyncio.run(run())

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "mood-radio-mcp"
    assert payload["mcp_path"] == "/mcp"
    assert payload["ready_for_feed"] is True
    assert payload["database"]["visible_post_count"] > 0
    assert payload["database"]["hidden_post_count"] == 0
    assert payload["database"]["delivery_count"] == 0


def test_health_route_stays_healthy_when_feed_is_empty(tmp_path: Path) -> None:
    async def run() -> httpx.Response:
        repo = MoodRadioRepository(tmp_path / "hidden.sqlite")
        with repo.connect() as conn:
            conn.execute("UPDATE song_posts SET report_count = 3")
        mcp = create_mcp(repo)
        transport = httpx.ASGITransport(app=mcp.http_app(transport="http"))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/health")

    response = asyncio.run(run())

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["ready_for_feed"] is False
    assert payload["database"]["visible_post_count"] == 0
    assert payload["database"]["hidden_post_count"] == payload["database"]["post_count"]
