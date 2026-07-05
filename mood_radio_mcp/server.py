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
]


def create_mcp(repository: MoodRadioRepository | None = None) -> FastMCP:
    repo = repository or MoodRadioRepository(Path(os.getenv("MOOD_RADIO_DB", "data/mood-radio.sqlite")))
    tools = MoodRadioTools(repo)
    mcp = FastMCP("MoodRadio")

    @mcp.custom_route("/", methods=["GET"], include_in_schema=False)
    async def index(_: Request) -> JSONResponse:
        """
        Human-readable service metadata for cloud consoles and reviewers.
        """
        return JSONResponse(
            {
                "ok": True,
                "service": "mood-radio-mcp",
                "name": "무드라디오 MCP",
                "version": __version__,
                "description": "같은 기분인 사람들이 남긴 노래와 한 줄 메시지를 주고받는 익명 무드 라디오입니다.",
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
    def get_radio_rooms() -> dict[str, object]:
        """
        무드라디오의 방 목록, 예시 요청, 커뮤니티 정책을 확인합니다.
        """
        return tools.get_radio_rooms()

    @mcp.tool()
    def post_song(
        title: str,
        artist: str,
        mood: str,
        message: str,
        link: str | None = None,
        nickname: str = "익명",
        actor_hint: str | None = None,
    ) -> dict[str, object]:
        """
        무드라디오에 노래와 한 줄 메시지를 남깁니다.

        actor_hint는 남용 방지를 위한 선택값이며 원문 대신 해시만 저장합니다.
        가사나 음원 파일은 받지 않습니다. 곡명, 아티스트, 무드, 짧은 메시지만 저장합니다.
        """
        return tools.post_song(
            title=title,
            artist=artist,
            mood=mood,
            message=message,
            link=link,
            nickname=nickname,
            actor_hint=actor_hint,
        )

    @mcp.tool()
    def pass_song(
        delivery_id: str,
        title: str,
        artist: str,
        mood: str,
        message: str,
        link: str | None = None,
        nickname: str = "익명",
        actor_hint: str | None = None,
    ) -> dict[str, object]:
        """
        받은 노래의 delivery_id를 기준으로 다음 사람에게 노래를 이어 보냅니다.

        actor_hint는 남용 방지를 위한 선택값이며 원문 대신 해시만 저장합니다.
        무드라디오의 핵심 릴레이 기능입니다. 가사나 음원 파일은 받지 않습니다.
        """
        return tools.pass_song(
            delivery_id=delivery_id,
            title=title,
            artist=artist,
            mood=mood,
            message=message,
            link=link,
            nickname=nickname,
            actor_hint=actor_hint,
        )

    @mcp.tool()
    def get_song(
        mood: str | None = None,
        situation: str | None = None,
        listener_hint: str | None = None,
        avoid_seen: bool = True,
    ) -> dict[str, object]:
        """
        같은 기분인 사람들이 남긴 노래 하나를 받습니다.

        listener_hint는 같은 사용자에게 같은 노래를 반복 배달하지 않기 위한 선택값입니다.
        """
        return tools.get_song(
            mood=mood,
            situation=situation,
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
    def get_mood_chart(
        mood: str | None = None,
        period: str = "today",
        limit: int = 5,
    ) -> dict[str, object]:
        """
        무드별 또는 전체 인기 노래 차트를 봅니다.

        period는 today 또는 all입니다.
        """
        return tools.get_mood_chart(mood=mood, period=period, limit=limit)

    @mcp.tool()
    def get_community_board(mood: str | None = None, limit: int = 5) -> dict[str, object]:
        """
        활성 무드방과 인기 릴레이를 함께 봅니다.
        """
        return tools.get_community_board(mood=mood, limit=limit)

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
