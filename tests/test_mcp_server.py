from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys

from fastmcp import Client

from mood_radio_mcp.repository import MoodRadioRepository
from mood_radio_mcp.server import create_mcp


def test_mcp_lists_expected_tools(tmp_path: Path) -> None:
    async def run() -> None:
        mcp = create_mcp(MoodRadioRepository(tmp_path / "mcp.sqlite"))
        async with Client(mcp) as client:
            tools = await client.list_tools()

        tool_names = {tool.name for tool in tools}
        assert tool_names == {
            "get_radio_rooms",
            "post_song",
            "pass_song",
            "get_song",
            "react_song",
            "get_mood_chart",
            "get_community_board",
            "get_relay_chain",
            "get_share_card",
            "report_song",
        }

    asyncio.run(run())


def test_server_import_does_not_open_default_database(tmp_path: Path) -> None:
    env = dict(os.environ)
    project_root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = str(project_root)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pathlib; import mood_radio_mcp.server; print(pathlib.Path('data/mood-radio.sqlite').exists())",
        ],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_mcp_post_get_and_react_flow(tmp_path: Path) -> None:
    async def run() -> None:
        mcp = create_mcp(MoodRadioRepository(tmp_path / "mcp-flow.sqlite"))
        async with Client(mcp) as client:
            post_result = await client.call_tool(
                "post_song",
                {
                    "title": "기다린 만큼, 더",
                    "artist": "검정치마",
                    "mood": "새벽감성",
                    "message": "천천히 괜찮아져도 돼",
                    "nickname": "밤손님",
                },
            )
            post_id = post_result.data["post"]["post_id"]

            delivery_result = await client.call_tool(
                "get_song",
                {
                    "mood": "새벽",
                    "listener_hint": "mcp-test",
                },
            )
            assert delivery_result.data["ok"] is True
            assert delivery_result.data["song"]["mood"] == "새벽"

            reaction_result = await client.call_tool(
                "react_song",
                {
                    "delivery_id": delivery_result.data["delivery_id"],
                    "reaction": "like",
                    "reply_message": "이거 좋다",
                },
            )
            assert reaction_result.data["ok"] is True
            assert reaction_result.data["post"]["stats"]["likes"] >= 1

            pass_result = await client.call_tool(
                "pass_song",
                {
                    "delivery_id": delivery_result.data["delivery_id"],
                    "title": "Supernova",
                    "artist": "aespa",
                    "mood": "운동",
                    "message": "다음 사람은 이걸로 조금 더 힘내기",
                },
            )
            assert pass_result.data["ok"] is True
            assert pass_result.data["post"]["relay"]["parent_post_id"] == delivery_result.data["song"]["post_id"]

            chain_result = await client.call_tool(
                "get_relay_chain",
                {
                    "delivery_id": delivery_result.data["delivery_id"],
                },
            )
            assert chain_result.data["ok"] is True
            assert len(chain_result.data["songs"]) >= 1

            card_result = await client.call_tool(
                "get_share_card",
                {
                    "post_id": pass_result.data["post"]["post_id"],
                },
            )
            assert card_result.data["ok"] is True
            assert "Supernova" in card_result.data["share_card"]["card_text"]

            board_result = await client.call_tool("get_community_board", {"limit": 5})
            assert board_result.data["ok"] is True
            assert board_result.data["relay_board"][0]["chain_length"] >= 2

    asyncio.run(run())
