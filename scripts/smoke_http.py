from __future__ import annotations

import argparse
import asyncio
import uuid

from fastmcp import Client


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def smoke(endpoint: str) -> None:
    run_id = "".join(chr(ord("a") + byte % 26) for byte in uuid.uuid4().bytes[:8])
    async with Client(endpoint) as client:
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]
        print("tools:", ", ".join(tool_names))
        require(
            set(tool_names)
            >= {
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
            },
            "missing expected tools",
        )

        rooms = await client.call_tool("get_radio_rooms", {})
        print("rooms_ok:", rooms.data["ok"])
        require(rooms.data["ok"] is True, "get_radio_rooms failed")

        chart = await client.call_tool("get_mood_chart", {"period": "all", "limit": 3})
        print("chart_count:", len(chart.data["songs"]))
        require(chart.data["ok"] is True, "get_mood_chart failed")

        situation_delivery = await client.call_tool(
            "get_song",
            {
                "situation": "오늘 야근 끝나고 집 가는 길 기분",
                "listener_hint": "smoke-situation",
            },
        )
        print("situation_match:", situation_delivery.data["match"]["matched_mood"])
        require(situation_delivery.data["ok"] is True, "situation get_song failed")
        require(
            situation_delivery.data["match"]["matched_mood"] == "퇴근길",
            "situation prompt did not match 퇴근길",
        )

        saved = await client.call_tool(
            "react_song",
            {
                "delivery_id": situation_delivery.data["delivery_id"],
                "reaction": "save",
                "actor_hint": f"smoke-react-{run_id}",
            },
        )
        print("save_ok:", saved.data["ok"])
        require(saved.data["ok"] is True, "react_song by delivery_id failed")

        delivery = await client.call_tool(
            "get_song",
            {
                "mood": "위로",
                "listener_hint": "smoke-relay",
            },
        )
        require(delivery.data["ok"] is True, "get_song for relay failed")
        passed = await client.call_tool(
            "pass_song",
            {
                "delivery_id": delivery.data["delivery_id"],
                "title": f"Supernova Smoke {run_id}",
                "artist": "aespa",
                "mood": "운동",
                "message": f"스모크 테스트에서 다음 사람에게 넘긴 노래 {run_id}",
                "actor_hint": f"smoke-pass-{run_id}",
            },
        )
        print("pass_ok:", passed.data["ok"])
        require(passed.data["ok"] is True, "pass_song failed")

        chain = await client.call_tool(
            "get_relay_chain",
            {
                "delivery_id": delivery.data["delivery_id"],
            },
        )
        print("chain_count:", len(chain.data["songs"]))
        require(chain.data["ok"] is True, "get_relay_chain by delivery_id failed")

        share_card = await client.call_tool(
            "get_share_card",
            {
                "post_id": passed.data["post"]["post_id"],
            },
        )
        print("share_card_ok:", share_card.data["ok"])
        require(share_card.data["ok"] is True, "get_share_card failed")
        require("무드라디오" in share_card.data["share_card"]["card_text"], "share card missing brand text")

        board = await client.call_tool("get_community_board", {"limit": 3})
        print("relay_board_count:", len(board.data["relay_board"]))
        require(board.data["ok"] is True, "get_community_board failed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a Mood Radio MCP HTTP endpoint.")
    parser.add_argument("endpoint", help="Streamable HTTP endpoint, e.g. https://example.com/mcp")
    args = parser.parse_args()
    asyncio.run(smoke(args.endpoint))


if __name__ == "__main__":
    main()
