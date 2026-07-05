from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .repository import MoodRadioRepository
from .tools import MoodRadioTools


TOOL_NAMES = [
    "get_mailbox_info",
    "recommend_song",
    "get_song",
    "react_song",
    "get_song_chart",
    "get_relay_board",
    "get_relay_chain",
    "get_share_card",
    "report_song",
]


def create_mcp(repository: MoodRadioRepository | None = None) -> FastMCP:
    repo = repository or MoodRadioRepository(Path(os.getenv("MOOD_RADIO_DB", "data/mood-radio.sqlite")))
    tools = MoodRadioTools(repo)
    mcp = FastMCP("SongMailbox")

    @mcp.custom_route("/", methods=["GET"], include_in_schema=False)
    async def index(_: Request) -> JSONResponse:
        """
        Human-readable service metadata for cloud consoles and reviewers.
        """
        return JSONResponse(
            {
                "ok": True,
                "service": "mood-radio-mcp",
                "name": "노래우체통 MCP",
                "version": __version__,
                "description": "노래를 한 곡 받으면, 내가 좋아하는 다른 노래와 문구를 다음 사람에게 추천해 릴레이를 잇는 익명 노래우체통입니다.",
                "endpoints": {
                    "mcp": "/mcp",
                    "health": "/health",
                },
                "playmcp_registration": "PlayMCP에는 이 서버의 /mcp 엔드포인트를 등록하세요.",
                "tools": TOOL_NAMES,
                "safety": {
                    "does_not_store": ["lyrics", "audio_files", "personal_contact_details"],
                    "stores": ["song_metadata", "short_messages", "relay_history", "aggregate_reactions"],
                },
            }
        )

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_: Request) -> JSONResponse:
        """
        HTTP health check for cloud probes and manual endpoint checks.
        """
        payload = tools.health()
        return JSONResponse(payload, status_code=200 if payload["ok"] else 503)

    @mcp.tool()
    def get_mailbox_info() -> dict[str, object]:
        """
        노래우체통의 사용 흐름과 커뮤니티 정책을 확인합니다.
        """
        return tools.get_mailbox_info()

    @mcp.tool()
    def recommend_song(
        delivery_id: str,
        title: str,
        artist: str,
        message: str,
        link: str | None = None,
        nickname: str = "익명",
        actor_hint: str | None = None,
    ) -> dict[str, object]:
        """
        받은 노래에 답장하듯, 내가 좋아하는 다른 노래와 짧은 문구를 다음 사람에게 추천합니다.

        actor_hint는 남용 방지를 위한 선택값이며 원문 대신 해시만 저장합니다.
        노래우체통의 핵심 릴레이 기능입니다. message는 필수이며, 가사나 음원 파일은 받지 않습니다.
        """
        return tools.recommend_song(
            delivery_id=delivery_id,
            title=title,
            artist=artist,
            message=message,
            link=link,
            nickname=nickname,
            actor_hint=actor_hint,
        )

    @mcp.tool()
    def get_song(
        listener_hint: str | None = None,
        avoid_seen: bool = True,
    ) -> dict[str, object]:
        """
        이전 타자가 남긴 노래와 짧은 추천 문구를 하나 받습니다.

        listener_hint는 같은 사용자에게 같은 노래를 반복 배달하지 않기 위한 선택값입니다.
        """
        return tools.get_song(
            listener_hint=listener_hint,
            avoid_seen=avoid_seen,
        )

    @mcp.tool()
    def react_song(
        reaction: str,
        post_id: str | None = None,
        delivery_id: str | None = None,
        reply_message: str | None = None,
        actor_hint: str | None = None,
    ) -> dict[str, object]:
        """
        받은 노래에 반응을 남깁니다.

        reaction은 like, save, skip 중 하나입니다. actor_hint는 남용 방지를 위한 선택값입니다.
        """
        return tools.react_song(
            post_id=post_id,
            delivery_id=delivery_id,
            reaction=reaction,
            reply_message=reply_message,
            actor_hint=actor_hint,
        )

    @mcp.tool()
    def get_song_chart(
        period: str = "today",
        limit: int = 5,
    ) -> dict[str, object]:
        """
        공감과 저장이 많은 인기 추천곡을 봅니다.

        period는 today 또는 all입니다.
        """
        return tools.get_song_chart(period=period, limit=limit)

    @mcp.tool()
    def get_relay_board(limit: int = 5) -> dict[str, object]:
        """
        길게 이어진 노래 추천 릴레이를 봅니다.
        """
        return tools.get_relay_board(limit=limit)

    @mcp.tool()
    def get_relay_chain(
        post_id: str | None = None,
        delivery_id: str | None = None,
        limit: int = 10,
    ) -> dict[str, object]:
        """
        특정 노래가 속한 릴레이 기록을 봅니다.
        """
        return tools.get_relay_chain(post_id=post_id, delivery_id=delivery_id, limit=limit)

    @mcp.tool()
    def get_share_card(
        post_id: str | None = None,
        delivery_id: str | None = None,
    ) -> dict[str, object]:
        """
        받은 노래나 릴레이 노래를 공유하기 좋은 짧은 카드 문구로 만듭니다.

        post_id 또는 delivery_id를 사용할 수 있습니다. 가사나 음원 파일은 포함하지 않습니다.
        """
        return tools.get_share_card(post_id=post_id, delivery_id=delivery_id)

    @mcp.tool()
    def report_song(
        reason: str,
        post_id: str | None = None,
        delivery_id: str | None = None,
        actor_hint: str | None = None,
    ) -> dict[str, object]:
        """
        부적절한 노래나 메시지를 신고합니다.

        누적 신고가 많은 게시물은 추천 피드에서 제외됩니다. actor_hint는 남용 방지를 위한 선택값입니다.
        """
        return tools.report_song(post_id=post_id, delivery_id=delivery_id, reason=reason, actor_hint=actor_hint)

    return mcp


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    create_mcp().run(transport="http", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
