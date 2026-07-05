from __future__ import annotations

import hashlib
import os

from .models import SongPost
from .moods import VALID_MOODS, infer_mood_from_text, mood_rooms, normalize_mood
from .repository import MoodRadioRepository, build_search_links
from .safety import (
    MAX_ARTIST_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_NICKNAME_LENGTH,
    MAX_TITLE_LENGTH,
    clean_optional_url,
    clean_text,
    validate_community_text,
    validate_public_metadata,
)


def listener_key_from_hint(hint: str | None) -> str:
    raw = (hint or "anonymous").strip().lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _rate_limit_from_env(name: str, default: tuple[int, int]) -> tuple[int, int]:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        limit_text, window_text = raw.split("/", 1)
        limit = int(limit_text)
        window_seconds = int(window_text)
    except ValueError as exc:
        raise ValueError(f"{name} must use '<limit>/<window_seconds>' format.") from exc
    if limit < 1 or window_seconds < 1:
        raise ValueError(f"{name} must use positive integers.")
    return limit, window_seconds


def post_to_public_dict(post: SongPost) -> dict[str, object]:
    return {
        "post_id": post.id,
        "title": post.title,
        "artist": post.artist,
        "mood": post.mood,
        "message": post.message,
        "from": post.nickname,
        "link": post.link,
        "search_links": build_search_links(post),
        "stats": {
            "likes": post.like_count,
            "saves": post.save_count,
            "skips": post.skip_count,
        },
        "relay": {
            "root_id": post.relay_root_id or post.id,
            "parent_post_id": post.parent_post_id,
            "depth": post.relay_depth,
        },
    }


def post_to_share_card(post: SongPost, *, chain_length: int) -> dict[str, object]:
    relay_position = post.relay_depth + 1
    hashtags = ["노래우체통", "노래추천", "노래릴레이"]
    card_text = "\n".join(
        [
            "[노래우체통] 누군가에게 도착한 추천곡",
            f"{post.artist} - {post.title}",
            f'"{post.message}"',
            f"from {post.nickname}",
            f"릴레이 {relay_position}번째 노래 · 전체 {chain_length}곡",
            " ".join(f"#{tag}" for tag in hashtags),
        ]
    )
    return {
        "card_text": card_text,
        "hashtags": hashtags,
        "relay_position": relay_position,
        "chain_length": chain_length,
        "song": post_to_public_dict(post),
    }


class MoodRadioTools:
    DEFAULT_RATE_LIMITS = {
        "post_song": _rate_limit_from_env("MOOD_RADIO_POST_LIMIT", (20, 3600)),
        "recommend_song": _rate_limit_from_env("MOOD_RADIO_RECOMMEND_LIMIT", (20, 3600)),
        "react_song": _rate_limit_from_env("MOOD_RADIO_REACT_LIMIT", (80, 3600)),
        "report_song": _rate_limit_from_env("MOOD_RADIO_REPORT_LIMIT", (20, 3600)),
    }

    def __init__(
        self,
        repository: MoodRadioRepository,
        rate_limits: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        self.repository = repository
        self.rate_limits = dict(rate_limits or self.DEFAULT_RATE_LIMITS)

    def _rate_limit_response(self, scope: str, actor_hint: str | None) -> dict[str, object] | None:
        limit = self.rate_limits.get(scope)
        if limit is None:
            return None
        allowed = self.repository.consume_rate_limit(
            scope=scope,
            actor_key=listener_key_from_hint(actor_hint),
            limit=limit[0],
            window_seconds=limit[1],
        )
        if allowed["allowed"]:
            return None
        return {
            "ok": False,
            "message": "짧은 시간 안에 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
            "rate_limited": True,
            "scope": scope,
            "retry_after_seconds": allowed["retry_after_seconds"],
        }

    def _resolve_post_for_action(self, *, post_id: str | None, delivery_id: str | None) -> SongPost | None:
        if post_id:
            return self.repository.get_post(clean_text(post_id, max_length=64, field_name="post_id"))
        if delivery_id:
            return self.repository.get_post_by_delivery(
                clean_text(delivery_id, max_length=64, field_name="delivery_id")
            )
        return None

    def health(self) -> dict[str, object]:
        try:
            database = self.repository.health()
        except Exception as exc:
            return {
                "ok": False,
                "service": "mood-radio-mcp",
                "mcp_path": "/mcp",
                "error": str(exc),
            }
        return {
            "ok": True,
            "service": "mood-radio-mcp",
            "mcp_path": "/mcp",
            "ready_for_feed": database["visible_post_count"] > 0,
            "database": database,
        }

    def get_mailbox_info(self) -> dict[str, object]:
        return {
            "ok": True,
            "message": "노래우체통은 누군가의 노래와 문구를 받고, 내가 좋아하는 다른 노래와 문구를 다음 사람에게 추천하는 익명 릴레이입니다.",
            "examples": [
                "노래 하나 받을래.",
                "나도 다음 사람에게 노래 추천할래.",
                "아이유 밤편지를 다음 사람에게 추천해줘.",
            ],
            "policy": {
                "stores": "곡명, 아티스트, 한 줄 추천 문구, 선택 링크, 릴레이 기록",
                "does_not_store": "가사, 음원 파일, 개인 연락처",
                "moderation": "신고가 누적된 게시물은 추천 피드에서 제외됩니다.",
            },
        }

    def get_radio_rooms(self) -> dict[str, object]:
        return {
            **self.get_mailbox_info(),
            "rooms": mood_rooms(),
        }

    def post_song(
        self,
        title: str,
        artist: str,
        message: str,
        link: str | None = None,
        nickname: str = "익명",
        actor_hint: str | None = None,
        mood: str | None = None,
    ) -> dict[str, object]:
        title_clean = clean_text(title, max_length=MAX_TITLE_LENGTH, field_name="title")
        artist_clean = clean_text(artist, max_length=MAX_ARTIST_LENGTH, field_name="artist")
        normalized_mood = normalize_mood(mood)
        message_clean = clean_text(message, max_length=MAX_MESSAGE_LENGTH, field_name="message")
        nickname_clean = clean_text(nickname, max_length=MAX_NICKNAME_LENGTH, field_name="nickname")
        validate_public_metadata(title_clean, field_name="title")
        validate_public_metadata(artist_clean, field_name="artist")
        validate_community_text(message_clean)
        validate_community_text(nickname_clean)
        limited = self._rate_limit_response("post_song", actor_hint)
        if limited:
            return limited
        duplicate = self.repository.find_recent_duplicate(
            title=title_clean,
            artist=artist_clean,
            mood=normalized_mood,
            message=message_clean,
        )
        if duplicate:
            return {
                "ok": False,
                "message": "같은 노래와 추천 문구가 최근 24시간 안에 이미 남겨져 있습니다.",
                "existing_post": post_to_public_dict(duplicate),
            }
        post = self.repository.create_post(
            title=title_clean,
            artist=artist_clean,
            mood=normalized_mood,
            message=message_clean,
            link=clean_optional_url(link),
            nickname=nickname_clean,
        )
        return {
            "ok": True,
            "message": "노래우체통에 추천곡과 문구를 남겼습니다.",
            "post": post_to_public_dict(post),
        }

    def recommend_song(
        self,
        delivery_id: str,
        title: str,
        artist: str,
        message: str,
        link: str | None = None,
        nickname: str = "익명",
        actor_hint: str | None = None,
        mood: str | None = None,
    ) -> dict[str, object]:
        title_clean = clean_text(title, max_length=MAX_TITLE_LENGTH, field_name="title")
        artist_clean = clean_text(artist, max_length=MAX_ARTIST_LENGTH, field_name="artist")
        normalized_mood = normalize_mood(mood)
        message_clean = clean_text(message, max_length=MAX_MESSAGE_LENGTH, field_name="message")
        nickname_clean = clean_text(nickname, max_length=MAX_NICKNAME_LENGTH, field_name="nickname")
        validate_public_metadata(title_clean, field_name="title")
        validate_public_metadata(artist_clean, field_name="artist")
        validate_community_text(message_clean)
        validate_community_text(nickname_clean)
        limited = self._rate_limit_response("recommend_song", actor_hint)
        if limited:
            return limited
        duplicate = self.repository.find_recent_duplicate(
            title=title_clean,
            artist=artist_clean,
            mood=normalized_mood,
            message=message_clean,
        )
        if duplicate:
            return {
                "ok": False,
                "message": "같은 노래와 추천 문구가 최근 24시간 안에 이미 남겨져 있습니다.",
                "existing_post": post_to_public_dict(duplicate),
            }
        result = self.repository.create_relay_post(
            delivery_id=clean_text(delivery_id, max_length=64, field_name="delivery_id"),
            title=title_clean,
            artist=artist_clean,
            mood=normalized_mood,
            message=message_clean,
            link=clean_optional_url(link),
            nickname=nickname_clean,
        )
        if result is None:
            return {
                "ok": False,
                "message": "답장할 수 있는 노래 배달 기록을 찾지 못했습니다.",
            }
        post, parent = result
        chain = self.repository.relay_chain(post_id=post.id, limit=20)
        return {
            "ok": True,
            "message": "내 추천곡과 문구를 다음 사람에게 남겼습니다.",
            "received_song": post_to_public_dict(parent),
            "recommended_song": post_to_public_dict(post),
            "post": post_to_public_dict(post),
            "relay": {
                "root_id": post.relay_root_id or post.id,
                "depth": post.relay_depth,
                "chain_length": len(chain),
            },
        }

    def pass_song(
        self,
        delivery_id: str,
        title: str,
        artist: str,
        message: str,
        link: str | None = None,
        nickname: str = "익명",
        actor_hint: str | None = None,
        mood: str | None = None,
    ) -> dict[str, object]:
        return self.recommend_song(
            delivery_id=delivery_id,
            title=title,
            artist=artist,
            message=message,
            link=link,
            nickname=nickname,
            actor_hint=actor_hint,
            mood=mood,
        )

    def get_song(
        self,
        mood: str | None = None,
        situation: str | None = None,
        listener_hint: str | None = None,
        avoid_seen: bool = True,
    ) -> dict[str, object]:
        inferred = infer_mood_from_text(situation)
        normalized = normalize_mood(mood) if mood else inferred
        delivery = self.repository.pick_post(
            mood=normalized,
            listener_key=listener_key_from_hint(listener_hint),
            avoid_seen=avoid_seen,
        )
        if delivery is None:
            return {
                "ok": False,
                "message": "아직 받을 수 있는 노래가 없습니다.",
                "available_moods": VALID_MOODS,
            }
        return {
            "ok": True,
            "delivery_id": delivery.delivery_id,
            "message": "누군가의 노래와 추천 문구가 도착했습니다. 마음에 남는 다른 노래와 문구로 다음 사람에게 답장해 주세요.",
            "next_step": "recommend_song 도구에 delivery_id, title, artist, message를 넣어 다음 사람에게 내 추천곡을 남기세요.",
            "match": {
                "requested_mood": mood,
                "situation": situation,
                "matched_mood": normalized or "전체",
                "matched_from": "mood" if mood else "situation" if inferred else "default",
            },
            "song": post_to_public_dict(delivery.post),
        }

    def react_song(
        self,
        reaction: str,
        post_id: str | None = None,
        delivery_id: str | None = None,
        reply_message: str | None = None,
        actor_hint: str | None = None,
    ) -> dict[str, object]:
        reply = None
        if reply_message:
            reply = clean_text(reply_message, max_length=MAX_MESSAGE_LENGTH, field_name="reply_message")
            validate_community_text(reply)
        limited = self._rate_limit_response("react_song", actor_hint)
        if limited:
            return limited
        target = self._resolve_post_for_action(post_id=post_id, delivery_id=delivery_id)
        if target is None:
            return {"ok": False, "message": "해당 노래를 찾지 못했습니다."}
        post = self.repository.react(post_id=target.id, reaction=reaction, reply_message=reply)
        if post is None:
            return {"ok": False, "message": "해당 노래를 찾지 못했습니다."}
        return {
            "ok": True,
            "message": "반응을 남겼습니다.",
            "post": post_to_public_dict(post),
        }

    def get_mood_chart(
        self,
        mood: str | None = None,
        period: str = "today",
        limit: int = 5,
    ) -> dict[str, object]:
        if period not in {"today", "all"}:
            raise ValueError("period must be either 'today' or 'all'.")
        posts = self.repository.chart(mood=mood, period=period, limit=limit)
        return {
            "ok": True,
            "message": "노래우체통 인기 추천곡입니다.",
            "period": period,
            "mood": normalize_mood(mood) if mood else None,
            "songs": [post_to_public_dict(post) for post in posts],
        }

    def get_song_chart(
        self,
        period: str = "today",
        limit: int = 5,
    ) -> dict[str, object]:
        return self.get_mood_chart(mood=None, period=period, limit=limit)

    def get_community_board(self, mood: str | None = None, limit: int = 5) -> dict[str, object]:
        relay_items = self.repository.relay_board(mood=mood, limit=limit)
        rooms = self.repository.room_stats()
        return {
            "ok": True,
            "message": "노래우체통 릴레이 보드입니다.",
            "mood": normalize_mood(mood) if mood else None,
            "active_rooms": rooms,
            "relay_board": [
                {
                    "root_id": item["root_id"],
                    "chain_length": item["chain_length"],
                    "max_depth": item["max_depth"],
                    "likes": item["like_count"],
                    "saves": item["save_count"],
                    "last_post_at": item["last_post_at"],
                    "started_with": post_to_public_dict(item["root"]),
                    "latest_song": post_to_public_dict(item["latest"]),
                }
                for item in relay_items
            ],
        }

    def get_relay_board(self, limit: int = 5) -> dict[str, object]:
        return self.get_community_board(mood=None, limit=limit)

    def get_relay_chain(
        self,
        post_id: str | None = None,
        delivery_id: str | None = None,
        limit: int = 10,
    ) -> dict[str, object]:
        target = self._resolve_post_for_action(post_id=post_id, delivery_id=delivery_id)
        chain = self.repository.relay_chain(post_id=target.id, limit=limit) if target else []
        if not chain:
            return {
                "ok": False,
                "message": "해당 노래의 릴레이를 찾지 못했습니다.",
            }
        root = chain[0]
        return {
            "ok": True,
            "message": "노래 릴레이 기록입니다.",
            "root_id": root.relay_root_id or root.id,
            "songs": [post_to_public_dict(post) for post in chain],
        }

    def get_share_card(
        self,
        post_id: str | None = None,
        delivery_id: str | None = None,
    ) -> dict[str, object]:
        target = self._resolve_post_for_action(post_id=post_id, delivery_id=delivery_id)
        if target is None:
            return {
                "ok": False,
                "message": "공유 카드로 만들 노래를 찾지 못했습니다.",
            }
        chain = self.repository.relay_chain(post_id=target.id, limit=20)
        return {
            "ok": True,
            "message": "공유하기 좋은 노래우체통 카드 문구입니다.",
            "share_card": post_to_share_card(target, chain_length=max(len(chain), 1)),
        }

    def report_song(
        self,
        reason: str,
        post_id: str | None = None,
        delivery_id: str | None = None,
        actor_hint: str | None = None,
    ) -> dict[str, object]:
        reason_clean = clean_text(reason, max_length=MAX_MESSAGE_LENGTH, field_name="reason")
        validate_community_text(reason_clean)
        limited = self._rate_limit_response("report_song", actor_hint)
        if limited:
            return limited
        target = self._resolve_post_for_action(post_id=post_id, delivery_id=delivery_id)
        if target is None:
            return {"ok": False, "message": "해당 노래를 찾지 못했습니다."}
        post = self.repository.report(post_id=target.id, reason=reason_clean)
        if post is None:
            return {"ok": False, "message": "해당 노래를 찾지 못했습니다."}
        hidden = post.report_count >= 3
        return {
            "ok": True,
            "message": "신고를 접수했습니다. 누적 신고가 많은 노래는 추천에서 제외됩니다.",
            "hidden_from_feed": hidden,
            "report_count": post.report_count,
        }
