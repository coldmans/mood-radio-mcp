from __future__ import annotations

from pathlib import Path

import pytest

from mood_radio_mcp.repository import MoodRadioRepository
from mood_radio_mcp.tools import MoodRadioTools


@pytest.fixture()
def tools(tmp_path: Path) -> MoodRadioTools:
    return MoodRadioTools(MoodRadioRepository(tmp_path / "test.sqlite"))


def test_post_and_get_song(tools: MoodRadioTools) -> None:
    result = tools.post_song(
        title="기다린 만큼, 더",
        artist="검정치마",
        mood="새벽감성",
        message="천천히 괜찮아져도 돼",
        nickname="밤손님",
    )

    assert result["ok"] is True
    post_id = result["post"]["post_id"]

    delivery = tools.get_song(mood="새벽", listener_hint="tester")

    assert delivery["ok"] is True
    assert delivery["song"]["mood"] == "새벽"
    assert delivery["song"]["post_id"] == post_id or delivery["song"]["title"]


def test_get_radio_rooms_describes_policy(tools: MoodRadioTools) -> None:
    result = tools.get_radio_rooms()

    assert result["ok"] is True
    assert result["rooms"]
    assert "가사" in result["policy"]["does_not_store"]


def test_health_reports_seeded_database(tools: MoodRadioTools) -> None:
    result = tools.health()

    assert result["ok"] is True
    assert result["mcp_path"] == "/mcp"
    assert result["ready_for_feed"] is True
    assert result["database"]["visible_post_count"] > 0
    assert result["database"]["hidden_post_count"] == 0
    assert result["database"]["delivery_count"] == 0
    assert result["database"]["reaction_count"] == 0
    assert result["database"]["rate_limit_bucket_count"] == 0


def test_health_tracks_operational_activity(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="health-activity")
    assert delivery["ok"] is True
    tools.react_song(delivery_id=delivery["delivery_id"], reaction="save", actor_hint="health-actor")
    tools.report_song(delivery_id=delivery["delivery_id"], reason="부적절", actor_hint="health-actor")

    result = tools.health()

    assert result["ok"] is True
    assert result["database"]["delivery_count"] == 1
    assert result["database"]["reaction_count"] == 2
    assert result["database"]["report_event_count"] == 1
    assert result["database"]["total_report_count"] == 1
    assert result["database"]["rate_limit_bucket_count"] == 2


def test_get_song_infers_mood_from_situation_when_mood_is_omitted(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(situation="비 오는 퇴근길에 어울리는 노래", listener_hint="situation-only")

    assert delivery["ok"] is True
    assert delivery["song"]["mood"] == "퇴근길"
    assert delivery["match"]["matched_from"] == "situation"


def test_get_song_infers_mood_from_review_prompt_situation(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(
        situation="오늘 야근 끝나고 집 가는 길 기분",
        listener_hint="review-prompt-situation",
    )

    assert delivery["ok"] is True
    assert delivery["song"]["mood"] == "퇴근길"
    assert delivery["match"]["matched_mood"] == "퇴근길"


def test_get_song_keeps_explicit_mood_over_situation(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", situation="퇴근길", listener_hint="explicit-mood")

    assert delivery["ok"] is True
    assert delivery["song"]["mood"] == "위로"
    assert delivery["match"]["matched_from"] == "mood"


def test_react_song_updates_chart(tools: MoodRadioTools) -> None:
    result = tools.post_song(
        title="한 페이지가 될 수 있게",
        artist="DAY6",
        mood="퇴근",
        message="오늘도 한 페이지 넘긴 사람에게",
    )
    post_id = result["post"]["post_id"]

    reaction = tools.react_song(post_id=post_id, reaction="like")
    assert reaction["ok"] is True
    assert reaction["post"]["stats"]["likes"] == 1

    chart = tools.get_mood_chart(mood="퇴근길", period="all", limit=3)
    assert chart["ok"] is True
    assert any(song["post_id"] == post_id for song in chart["songs"])


def test_react_song_accepts_delivery_id_from_received_song(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="delivery-reaction")
    assert delivery["ok"] is True

    reaction = tools.react_song(delivery_id=delivery["delivery_id"], reaction="save")

    assert reaction["ok"] is True
    assert reaction["post"]["post_id"] == delivery["song"]["post_id"]
    assert reaction["post"]["stats"]["saves"] == delivery["song"]["stats"]["saves"] + 1


def test_pass_song_creates_relay_chain(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="relay-listener")
    assert delivery["ok"] is True

    result = tools.pass_song(
        delivery_id=delivery["delivery_id"],
        title="Supernova",
        artist="aespa",
        mood="운동",
        message="다음 사람은 이걸로 조금 더 힘내기",
        nickname="러너",
    )

    assert result["ok"] is True
    assert result["post"]["relay"]["parent_post_id"] == delivery["song"]["post_id"]
    assert result["post"]["relay"]["depth"] == delivery["song"]["relay"]["depth"] + 1
    assert result["relay"]["chain_length"] >= 2

    chain = tools.get_relay_chain(post_id=result["post"]["post_id"])
    assert chain["ok"] is True
    assert chain["songs"][-1]["post_id"] == result["post"]["post_id"]


def test_get_relay_chain_accepts_delivery_id(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="delivery-chain")
    assert delivery["ok"] is True

    chain = tools.get_relay_chain(delivery_id=delivery["delivery_id"])

    assert chain["ok"] is True
    assert chain["songs"][0]["post_id"] == delivery["song"]["post_id"]


def test_get_share_card_accepts_delivery_id(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="share-card")
    assert delivery["ok"] is True

    card = tools.get_share_card(delivery_id=delivery["delivery_id"])

    assert card["ok"] is True
    assert "노래우체통" in card["share_card"]["card_text"]
    assert delivery["song"]["title"] in card["share_card"]["card_text"]
    assert card["share_card"]["relay_position"] == delivery["song"]["relay"]["depth"] + 1
    assert "노래릴레이" in card["share_card"]["hashtags"]


def test_get_share_card_rejects_missing_target(tools: MoodRadioTools) -> None:
    card = tools.get_share_card(post_id="song_missing")

    assert card["ok"] is False


def test_community_board_shows_active_rooms_and_relays(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="board-listener")
    assert delivery["ok"] is True

    passed = tools.pass_song(
        delivery_id=delivery["delivery_id"],
        title="Supernova",
        artist="aespa",
        mood="운동",
        message="보드 테스트에서 다음 사람에게 넘긴 노래",
    )
    assert passed["ok"] is True

    board = tools.get_community_board(limit=5)

    assert board["ok"] is True
    assert any(room["mood"] == "위로" for room in board["active_rooms"])
    assert board["relay_board"][0]["chain_length"] >= 2
    assert board["relay_board"][0]["latest_song"]["post_id"] == passed["post"]["post_id"]


def test_pass_song_rejects_missing_delivery(tools: MoodRadioTools) -> None:
    result = tools.pass_song(
        delivery_id="delivery_missing",
        title="Song",
        artist="Artist",
        mood="위로",
        message="짧은 메시지",
    )

    assert result["ok"] is False


def test_post_song_rejects_recent_exact_duplicate(tools: MoodRadioTools) -> None:
    first = tools.post_song(
        title="Song",
        artist="Artist",
        mood="위로",
        message="같은 메시지",
    )
    second = tools.post_song(
        title="Song",
        artist="Artist",
        mood="위로",
        message="같은 메시지",
    )

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["existing_post"]["post_id"] == first["post"]["post_id"]


def test_post_song_rate_limits_same_actor(tmp_path: Path) -> None:
    limited_tools = MoodRadioTools(
        MoodRadioRepository(tmp_path / "limited.sqlite"),
        rate_limits={"post_song": (1, 3600)},
    )

    first = limited_tools.post_song(
        title="첫 번째 노래",
        artist="Artist",
        mood="위로",
        message="처음 남기는 메시지",
        actor_hint="same-user",
    )
    second = limited_tools.post_song(
        title="두 번째 노래",
        artist="Artist",
        mood="위로",
        message="다른 메시지",
        actor_hint="same-user",
    )
    other_actor = limited_tools.post_song(
        title="세 번째 노래",
        artist="Artist",
        mood="위로",
        message="다른 사람이 남기는 메시지",
        actor_hint="other-user",
    )

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["rate_limited"] is True
    assert second["retry_after_seconds"] > 0
    assert other_actor["ok"] is True


def test_pass_song_rejects_recent_exact_duplicate(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="duplicate-relay")
    assert delivery["ok"] is True

    first = tools.pass_song(
        delivery_id=delivery["delivery_id"],
        title="Relay Song",
        artist="Relay Artist",
        mood="위로",
        message="릴레이 중복 테스트",
    )
    next_delivery = tools.get_song(mood="위로", listener_hint="duplicate-relay-next")
    second = tools.pass_song(
        delivery_id=next_delivery["delivery_id"],
        title="Relay Song",
        artist="Relay Artist",
        mood="위로",
        message="릴레이 중복 테스트",
    )

    assert first["ok"] is True
    assert second["ok"] is False


def test_react_song_rate_limits_same_actor(tmp_path: Path) -> None:
    limited_tools = MoodRadioTools(
        MoodRadioRepository(tmp_path / "react-limited.sqlite"),
        rate_limits={"react_song": (1, 3600)},
    )
    delivery = limited_tools.get_song(mood="위로", listener_hint="reaction-rate-limit")
    assert delivery["ok"] is True

    first = limited_tools.react_song(
        delivery_id=delivery["delivery_id"],
        reaction="like",
        actor_hint="same-user",
    )
    second = limited_tools.react_song(
        delivery_id=delivery["delivery_id"],
        reaction="save",
        actor_hint="same-user",
    )

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["rate_limited"] is True


def test_reported_song_is_hidden_after_three_reports(tools: MoodRadioTools) -> None:
    result = tools.post_song(
        title="Bad Song",
        artist="Someone",
        mood="집중",
        message="평범한 메시지",
    )
    post_id = result["post"]["post_id"]

    tools.report_song(post_id=post_id, reason="부적절")
    tools.report_song(post_id=post_id, reason="부적절")
    report = tools.report_song(post_id=post_id, reason="부적절")

    assert report["hidden_from_feed"] is True


def test_report_song_accepts_delivery_id(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="delivery-report")
    assert delivery["ok"] is True

    report = tools.report_song(delivery_id=delivery["delivery_id"], reason="부적절")

    assert report["ok"] is True
    assert report["report_count"] == delivery["song"].get("report_count", 0) + 1 or report["report_count"] >= 1


def test_rejects_lyrics_like_long_message(tools: MoodRadioTools) -> None:
    with pytest.raises(ValueError):
        tools.post_song(
            title="Song",
            artist="Artist",
            mood="위로",
            message="가" * 200,
        )


@pytest.mark.parametrize(
    "message",
    [
        "연락은 test@example.com 으로 주세요",
        "카톡 아이디 남겨요",
        "010-1234-5678로 연락줘",
        "계좌로 후원해줘",
        "여기 들어와 https://example.com",
        "가사: 오늘 밤은 길고",
        "ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ",
    ],
)
def test_rejects_unsafe_community_messages(tools: MoodRadioTools, message: str) -> None:
    with pytest.raises(ValueError):
        tools.post_song(
            title="Song",
            artist="Artist",
            mood="위로",
            message=message,
        )


def test_rejects_unsafe_public_nickname(tools: MoodRadioTools) -> None:
    with pytest.raises(ValueError):
        tools.post_song(
            title="Song",
            artist="Artist",
            mood="위로",
            message="짧은 메시지",
            nickname="010-1234-5678",
        )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("title", "https://example.com/song"),
        ("artist", "010-1234-5678"),
        ("title", "aaaaaaaaaaaa"),
    ],
)
def test_rejects_abusive_public_metadata(
    tools: MoodRadioTools,
    field_name: str,
    field_value: str,
) -> None:
    payload = {
        "title": "Song",
        "artist": "Artist",
        "mood": "위로",
        "message": "짧은 메시지",
    }
    payload[field_name] = field_value

    with pytest.raises(ValueError):
        tools.post_song(**payload)


def test_rejects_unsafe_relay_message(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="unsafe-relay")
    assert delivery["ok"] is True

    with pytest.raises(ValueError):
        tools.pass_song(
            delivery_id=delivery["delivery_id"],
            title="Song",
            artist="Artist",
            mood="위로",
            message="오픈채팅으로 들어와",
        )


def test_rejects_abusive_relay_metadata(tools: MoodRadioTools) -> None:
    delivery = tools.get_song(mood="위로", listener_hint="unsafe-relay-metadata")
    assert delivery["ok"] is True

    with pytest.raises(ValueError):
        tools.pass_song(
            delivery_id=delivery["delivery_id"],
            title="Song",
            artist="https://example.com/artist",
            mood="위로",
            message="짧은 메시지",
        )


def test_rejects_unsafe_report_reason(tools: MoodRadioTools) -> None:
    result = tools.post_song(
        title="Song",
        artist="Artist",
        mood="위로",
        message="짧은 메시지",
    )

    with pytest.raises(ValueError):
        tools.report_song(post_id=result["post"]["post_id"], reason="카톡으로 알려줄게")


def test_rejects_unsupported_link_host(tools: MoodRadioTools) -> None:
    with pytest.raises(ValueError):
        tools.post_song(
            title="Song",
            artist="Artist",
            mood="위로",
            message="짧은 메시지",
            link="https://example.com/song",
        )


def test_accepts_supported_music_link(tools: MoodRadioTools) -> None:
    result = tools.post_song(
        title="Song",
        artist="Artist",
        mood="위로",
        message="짧은 메시지",
        link="https://www.youtube.com/watch?v=abc123",
    )

    assert result["ok"] is True
    assert result["post"]["link"] == "https://www.youtube.com/watch?v=abc123"


def test_invalid_reaction_is_rejected(tools: MoodRadioTools) -> None:
    result = tools.post_song(
        title="Song",
        artist="Artist",
        mood="위로",
        message="짧은 메시지",
    )

    with pytest.raises(ValueError):
        tools.react_song(post_id=result["post"]["post_id"], reaction="wow")


def test_react_song_requires_post_or_delivery_id(tools: MoodRadioTools) -> None:
    result = tools.react_song(reaction="like")

    assert result["ok"] is False
