from __future__ import annotations

from pathlib import Path
import sqlite3

from mood_radio_mcp.repository import MoodRadioRepository


def test_existing_database_without_relay_columns_is_migrated(tmp_path: Path) -> None:
    db_path = tmp_path / "old.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE song_posts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                mood TEXT NOT NULL,
                message TEXT NOT NULL,
                link TEXT,
                nickname TEXT NOT NULL,
                created_at TEXT NOT NULL,
                like_count INTEGER NOT NULL DEFAULT 0,
                save_count INTEGER NOT NULL DEFAULT 0,
                skip_count INTEGER NOT NULL DEFAULT 0,
                report_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE deliveries (
                id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                listener_key TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE reactions (
                id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                reaction TEXT NOT NULL,
                reply_message TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO song_posts
                (id, title, artist, mood, message, link, nickname, created_at)
            VALUES
                ('song_old', 'Old Song', 'Old Artist', '위로', '오래된 메시지', NULL, '익명', '2026-07-04T00:00:00+00:00')
            """
        )

    repo = MoodRadioRepository(db_path)
    post = repo.get_post("song_old")

    assert post is not None
    assert post.parent_post_id is None
    assert post.relay_root_id is None
    assert post.relay_depth == 0


def test_rate_limit_window_blocks_then_resets(tmp_path: Path) -> None:
    repo = MoodRadioRepository(tmp_path / "rate-limit.sqlite")

    first = repo.consume_rate_limit(
        scope="post_song",
        actor_key="actor",
        limit=1,
        window_seconds=3600,
    )
    second = repo.consume_rate_limit(
        scope="post_song",
        actor_key="actor",
        limit=1,
        window_seconds=3600,
    )
    other_actor = repo.consume_rate_limit(
        scope="post_song",
        actor_key="other",
        limit=1,
        window_seconds=3600,
    )

    assert first["allowed"] is True
    assert second["allowed"] is False
    assert second["retry_after_seconds"] > 0
    assert other_actor["allowed"] is True
