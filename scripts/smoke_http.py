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
                "get_mailbox_info",
                "recommend_song",
                "get_song",
                "react_song",
                "get_song_chart",
                "get_relay_board",
                "get_relay_chain",
                "get_share_card",
                "report_song",
            },
            "missing expected tools",
        )

        info = await client.call_tool("get_mailbox_info", {})
        print("info_ok:", info.data["ok"])
        require(info.data["ok"] is True, "get_mailbox_info failed")

        chart = await client.call_tool("get_song_chart", {"period": "all", "limit": 3})
        print("chart_count:", len(chart.data["songs"]))
        require(chart.data["ok"] is True, "get_song_chart failed")

        delivery = await client.call_tool(
            "get_song",
            {
                "listener_hint": "smoke-listener",
            },
        )
        print("delivery_id:", delivery.data["delivery_id"])
        require(delivery.data["ok"] is True, "get_song failed")

        saved = await client.call_tool(
            "react_song",
            {
                "delivery_id": delivery.data["delivery_id"],
                "reaction": "save",
                "actor_hint": f"smoke-react-{run_id}",
            },
        )
        print("save_ok:", saved.data["ok"])
        require(saved.data["ok"] is True, "react_song by delivery_id failed")

        recommended = await client.call_tool(
            "recommend_song",
            {
                "delivery_id": delivery.data["delivery_id"],
                "title": f"밤편지 Smoke {run_id}",
                "artist": "아이유",
                "message": f"스모크 테스트에서 다음 사람에게 남긴 추천 문구 {run_id}",
                "actor_hint": f"smoke-recommend-{run_id}",
            },
        )
        print("recommend_ok:", recommended.data["ok"])
        require(recommended.data["ok"] is True, "recommend_song failed")

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
                "post_id": recommended.data["post"]["post_id"],
            },
        )
        print("share_card_ok:", share_card.data["ok"])
        require(share_card.data["ok"] is True, "get_share_card failed")
        require("노래우체통" in share_card.data["share_card"]["card_text"], "share card missing brand text")

        board = await client.call_tool("get_relay_board", {"limit": 3})
        print("relay_board_count:", len(board.data["relay_board"]))
        require(board.data["ok"] is True, "get_relay_board failed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a Song Mailbox MCP HTTP endpoint.")
    parser.add_argument("endpoint", help="Streamable HTTP endpoint, e.g. https://example.com/mcp")
    args = parser.parse_args()
    asyncio.run(smoke(args.endpoint))


if __name__ == "__main__":
    main()
