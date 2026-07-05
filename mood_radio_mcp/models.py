from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SongPost:
    id: str
    title: str
    artist: str
    mood: str
    message: str
    link: str | None
    nickname: str
    created_at: str
    like_count: int = 0
    save_count: int = 0
    skip_count: int = 0
    report_count: int = 0
    parent_post_id: str | None = None
    relay_root_id: str | None = None
    relay_depth: int = 0


@dataclass(frozen=True)
class SongDelivery:
    delivery_id: str
    post: SongPost
    search_links: dict[str, str]
