from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import tempfile
import uuid

from fastmcp import Client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mood_radio_mcp.repository import MoodRadioRepository  # noqa: E402
from mood_radio_mcp.server import create_mcp  # noqa: E402


def _letters_only_id() -> str:
    return "".join(chr(ord("a") + byte % 26) for byte in uuid.uuid4().bytes[:8])


def _line(label: str, value: object) -> str:
    return f"- {label}: {value}"


async def _collect_demo(client_target: object) -> str:
    run_id = _letters_only_id()
    lines = [
        "# 무드라디오 MCP 심사 데모",
        "",
        "## 1. 무드방 확인",
        "",
        'Prompt: "무드라디오 방 목록 보여줘."',
        "",
    ]

    async with Client(client_target) as client:
        rooms = await client.call_tool("get_radio_rooms", {})
        lines.extend(
            [
                "Tool: `get_radio_rooms`",
                _line("ok", rooms.data["ok"]),
                _line("room_count", len(rooms.data["rooms"])),
                _line("policy", rooms.data["policy"]["does_not_store"]),
                "",
                "## 2. 상황 문장으로 노래 받기",
                "",
                'Prompt: "오늘 야근 끝나고 집 가는 길 기분으로 사람들이 남긴 노래 하나 줘."',
                "",
            ]
        )

        delivery = await client.call_tool(
            "get_song",
            {
                "situation": "오늘 야근 끝나고 집 가는 길 기분",
                "listener_hint": f"reviewer-demo-listener-{run_id}",
            },
        )
        song = delivery.data["song"]
        lines.extend(
            [
                "Tool: `get_song`",
                _line("delivery_id", delivery.data["delivery_id"]),
                _line("matched_mood", delivery.data["match"]["matched_mood"]),
                _line("song", f"{song['artist']} - {song['title']}"),
                _line("from", song["from"]),
                _line("message", song["message"]),
                "",
                "## 3. 받은 노래 저장하기",
                "",
                'Prompt: "방금 받은 노래 저장해줘."',
                "",
            ]
        )

        saved = await client.call_tool(
            "react_song",
            {
                "delivery_id": delivery.data["delivery_id"],
                "reaction": "save",
                "actor_hint": f"reviewer-demo-react-{run_id}",
            },
        )
        lines.extend(
            [
                "Tool: `react_song`",
                _line("ok", saved.data["ok"]),
                _line("saves", saved.data["post"]["stats"]["saves"]),
                "",
                "## 4. 다음 사람에게 노래 이어 보내기",
                "",
                'Prompt: "방금 받은 노래에서 이어달리기로 aespa의 Supernova를 다음 사람에게 넘겨줘."',
                "",
            ]
        )

        passed = await client.call_tool(
            "pass_song",
            {
                "delivery_id": delivery.data["delivery_id"],
                "title": f"Supernova Demo {run_id}",
                "artist": "aespa",
                "mood": "운동",
                "message": f"심사 데모에서 다음 사람에게 넘기는 노래 {run_id}",
                "nickname": "데모",
                "actor_hint": f"reviewer-demo-pass-{run_id}",
            },
        )
        lines.extend(
            [
                "Tool: `pass_song`",
                _line("ok", passed.data["ok"]),
                _line("new_post_id", passed.data["post"]["post_id"]),
                _line("relay_depth", passed.data["relay"]["depth"]),
                "",
                "## 5. 공유 카드 만들기",
                "",
                'Prompt: "방금 넘긴 노래 공유 카드 만들어줘."',
                "",
            ]
        )

        share_card = await client.call_tool(
            "get_share_card",
            {
                "post_id": passed.data["post"]["post_id"],
            },
        )
        lines.extend(
            [
                "Tool: `get_share_card`",
                _line("ok", share_card.data["ok"]),
                _line("card_text", share_card.data["share_card"]["card_text"].replace("\n", " / ")),
                "",
                "## 6. 릴레이 기록과 커뮤니티 보드 확인",
                "",
                'Prompt: "방금 넘긴 노래의 릴레이 기록 보여줘."',
                "",
            ]
        )

        chain = await client.call_tool(
            "get_relay_chain",
            {
                "post_id": passed.data["post"]["post_id"],
            },
        )
        board = await client.call_tool("get_community_board", {"limit": 3})
        lines.extend(
            [
                "Tool: `get_relay_chain`, `get_community_board`",
                _line("relay_chain_length", len(chain.data["songs"])),
                _line("relay_board_count", len(board.data["relay_board"])),
                _line("top_chain_length", board.data["relay_board"][0]["chain_length"]),
                "",
                "## 7. 차트 확인",
                "",
                'Prompt: "오늘 사람들이 가장 많이 공감한 무드라디오 차트 보여줘."',
                "",
            ]
        )

        chart = await client.call_tool("get_mood_chart", {"period": "all", "limit": 3})
        chart_songs = [f"{item['artist']} - {item['title']}" for item in chart.data["songs"]]
        lines.extend(
            [
                "Tool: `get_mood_chart`",
                _line("chart_count", len(chart.data["songs"])),
                _line("top_songs", "; ".join(chart_songs)),
            ]
        )

    return "\n".join(lines) + "\n"


async def build_demo(endpoint: str | None = None, db_path: Path | None = None) -> str:
    if endpoint:
        return await _collect_demo(endpoint)
    if db_path is not None:
        return await _collect_demo(create_mcp(MoodRadioRepository(db_path)))
    with tempfile.TemporaryDirectory() as temp_dir:
        return await _collect_demo(create_mcp(MoodRadioRepository(Path(temp_dir) / "reviewer-demo.sqlite")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a reviewer-friendly Mood Radio MCP demo transcript.")
    parser.add_argument("--endpoint", help="Optional Streamable HTTP endpoint, e.g. https://example.com/mcp")
    args = parser.parse_args()
    print(asyncio.run(build_demo(args.endpoint)), end="")


if __name__ == "__main__":
    main()
