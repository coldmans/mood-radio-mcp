from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import uuid

from .models import SongDelivery, SongPost
from .moods import normalize_mood

DEFAULT_DB_PATH = Path(os.getenv("MOOD_RADIO_DB", "data/mood-radio.sqlite"))


SEED_POSTS = (
    ("NewJeans", "Ditto", "새벽", "말없이 걷고 싶은 새벽에 남겨요.", None, "새벽손님"),
    ("잔나비", "주저하는 연인들을 위해", "비오는날", "비 오는 날에는 너무 빨리 괜찮아지려 하지 말기.", None, "우산"),
    ("DAY6", "한 페이지가 될 수 있게", "퇴근길", "오늘도 한 페이지 넘긴 사람에게.", None, "퇴근러"),
    ("LUCY", "개화", "설렘", "시작하는 사람한테 보내고 싶은 노래.", None, "봄"),
    ("Nujabes", "Aruarian Dance", "집중", "마감 전 조용히 몰입하고 싶을 때.", None, "커피"),
    ("HYUKOH", "TOMBOY", "산책", "혼자 걷다가 갑자기 생각 많아질 때.", None, "골목"),
    ("볼빨간사춘기", "나의 사춘기에게", "위로", "오늘 버틴 사람에게 조심스럽게 놓고 갑니다.", None, "익명"),
)


class MoodRadioRepository:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS song_posts (
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
                    report_count INTEGER NOT NULL DEFAULT 0,
                    parent_post_id TEXT,
                    relay_root_id TEXT,
                    relay_depth INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS deliveries (
                    id TEXT PRIMARY KEY,
                    post_id TEXT NOT NULL,
                    listener_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(post_id) REFERENCES song_posts(id)
                );

                CREATE TABLE IF NOT EXISTS reactions (
                    id TEXT PRIMARY KEY,
                    post_id TEXT NOT NULL,
                    reaction TEXT NOT NULL,
                    reply_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(post_id) REFERENCES song_posts(id)
                );

                CREATE TABLE IF NOT EXISTS rate_limits (
                    scope TEXT NOT NULL,
                    actor_key TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY (scope, actor_key)
                );

                """
            )
            self._ensure_song_post_columns(conn)
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_song_posts_mood_score
                    ON song_posts (mood, report_count, like_count, save_count, skip_count);

                CREATE INDEX IF NOT EXISTS idx_song_posts_created_at
                    ON song_posts (created_at);

                CREATE INDEX IF NOT EXISTS idx_song_posts_relay_root
                    ON song_posts (relay_root_id, relay_depth, created_at);

                CREATE INDEX IF NOT EXISTS idx_song_posts_parent_post
                    ON song_posts (parent_post_id);

                CREATE INDEX IF NOT EXISTS idx_deliveries_listener_post
                    ON deliveries (listener_key, post_id);

                CREATE INDEX IF NOT EXISTS idx_reactions_post_created_at
                    ON reactions (post_id, created_at);

                CREATE INDEX IF NOT EXISTS idx_rate_limits_window
                    ON rate_limits (window_start);
                """
            )
            count = conn.execute("SELECT COUNT(*) AS count FROM song_posts").fetchone()["count"]
            if count == 0:
                for artist, title, mood, message, link, nickname in SEED_POSTS:
                    post_id = f"song_{uuid.uuid4().hex[:12]}"
                    post = SongPost(
                        id=post_id,
                        title=title,
                        artist=artist,
                        mood=normalize_mood(mood),
                        message=message,
                        link=link,
                        nickname=nickname,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        relay_root_id=post_id,
                    )
                    conn.execute(
                        """
                        INSERT INTO song_posts
                            (
                                id, title, artist, mood, message, link, nickname, created_at,
                                parent_post_id, relay_root_id, relay_depth
                            )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            post.id,
                            post.title,
                            post.artist,
                            post.mood,
                            post.message,
                            post.link,
                            post.nickname,
                            post.created_at,
                            post.parent_post_id,
                            post.relay_root_id,
                            post.relay_depth,
                        ),
                    )

    @staticmethod
    def _ensure_song_post_columns(conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(song_posts)").fetchall()}
        if "parent_post_id" not in columns:
            conn.execute("ALTER TABLE song_posts ADD COLUMN parent_post_id TEXT")
        if "relay_root_id" not in columns:
            conn.execute("ALTER TABLE song_posts ADD COLUMN relay_root_id TEXT")
        if "relay_depth" not in columns:
            conn.execute("ALTER TABLE song_posts ADD COLUMN relay_depth INTEGER NOT NULL DEFAULT 0")

    def create_post(
        self,
        *,
        title: str,
        artist: str,
        mood: str,
        message: str,
        link: str | None,
        nickname: str,
        parent_post_id: str | None = None,
        relay_root_id: str | None = None,
        relay_depth: int = 0,
    ) -> SongPost:
        now = datetime.now(timezone.utc).isoformat()
        post_id = f"song_{uuid.uuid4().hex[:12]}"
        post = SongPost(
            id=post_id,
            title=title,
            artist=artist,
            mood=normalize_mood(mood),
            message=message,
            link=link,
            nickname=nickname,
            created_at=now,
            parent_post_id=parent_post_id,
            relay_root_id=relay_root_id or post_id,
            relay_depth=relay_depth,
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO song_posts
                    (
                        id, title, artist, mood, message, link, nickname, created_at,
                        parent_post_id, relay_root_id, relay_depth
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.id,
                    post.title,
                    post.artist,
                    post.mood,
                    post.message,
                    post.link,
                    post.nickname,
                    post.created_at,
                    post.parent_post_id,
                    post.relay_root_id,
                    post.relay_depth,
                ),
            )
        return post

    def find_recent_duplicate(
        self,
        *,
        title: str,
        artist: str,
        mood: str,
        message: str,
        hours: int = 24,
    ) -> SongPost | None:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM song_posts
                WHERE LOWER(title) = LOWER(?)
                  AND LOWER(artist) = LOWER(?)
                  AND mood = ?
                  AND LOWER(message) = LOWER(?)
                  AND created_at >= ?
                  AND report_count < 3
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (title, artist, normalize_mood(mood), message, cutoff),
            ).fetchone()
        return self._row_to_post(row) if row else None

    def create_relay_post(
        self,
        *,
        delivery_id: str,
        title: str,
        artist: str,
        mood: str,
        message: str,
        link: str | None,
        nickname: str,
    ) -> tuple[SongPost, SongPost] | None:
        parent = self.get_post_by_delivery(delivery_id)
        if parent is None:
            return None
        child = self.create_post(
            title=title,
            artist=artist,
            mood=mood,
            message=message,
            link=link,
            nickname=nickname,
            parent_post_id=parent.id,
            relay_root_id=parent.relay_root_id or parent.id,
            relay_depth=parent.relay_depth + 1,
        )
        return child, parent

    def get_post(self, post_id: str) -> SongPost | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM song_posts WHERE id = ?", (post_id,)).fetchone()
        return self._row_to_post(row) if row else None

    def get_post_by_delivery(self, delivery_id: str) -> SongPost | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT song_posts.*
                FROM deliveries
                JOIN song_posts ON song_posts.id = deliveries.post_id
                WHERE deliveries.id = ?
                  AND song_posts.report_count < 3
                """,
                (delivery_id,),
            ).fetchone()
        return self._row_to_post(row) if row else None

    def health(self) -> dict[str, int]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM song_posts) AS post_count,
                    (SELECT COUNT(*) FROM song_posts WHERE report_count < 3) AS visible_post_count,
                    (SELECT COUNT(*) FROM song_posts WHERE report_count >= 3) AS hidden_post_count,
                    (SELECT COUNT(*) FROM song_posts WHERE parent_post_id IS NOT NULL) AS relay_post_count,
                    (SELECT COUNT(*) FROM deliveries) AS delivery_count,
                    (SELECT COUNT(*) FROM reactions) AS reaction_count,
                    (SELECT COUNT(*) FROM reactions WHERE reaction = 'report') AS report_event_count,
                    (SELECT COALESCE(SUM(report_count), 0) FROM song_posts) AS total_report_count,
                    (SELECT COUNT(*) FROM rate_limits) AS rate_limit_bucket_count
                """
            ).fetchone()
        return {
            "post_count": int(row["post_count"] or 0),
            "visible_post_count": int(row["visible_post_count"] or 0),
            "hidden_post_count": int(row["hidden_post_count"] or 0),
            "relay_post_count": int(row["relay_post_count"] or 0),
            "delivery_count": int(row["delivery_count"] or 0),
            "reaction_count": int(row["reaction_count"] or 0),
            "report_event_count": int(row["report_event_count"] or 0),
            "total_report_count": int(row["total_report_count"] or 0),
            "rate_limit_bucket_count": int(row["rate_limit_bucket_count"] or 0),
        }

    def consume_rate_limit(
        self,
        *,
        scope: str,
        actor_key: str,
        limit: int,
        window_seconds: int,
    ) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        now_text = now.isoformat()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT window_start, count
                FROM rate_limits
                WHERE scope = ? AND actor_key = ?
                """,
                (scope, actor_key),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO rate_limits (scope, actor_key, window_start, count)
                    VALUES (?, ?, ?, 1)
                    """,
                    (scope, actor_key, now_text),
                )
                return {"allowed": True, "remaining": max(limit - 1, 0), "retry_after_seconds": 0}

            window_start = datetime.fromisoformat(row["window_start"])
            reset_at = window_start + timedelta(seconds=window_seconds)
            if now >= reset_at:
                conn.execute(
                    """
                    UPDATE rate_limits
                    SET window_start = ?, count = 1
                    WHERE scope = ? AND actor_key = ?
                    """,
                    (now_text, scope, actor_key),
                )
                return {"allowed": True, "remaining": max(limit - 1, 0), "retry_after_seconds": 0}

            count = int(row["count"])
            retry_after = max(int((reset_at - now).total_seconds()), 1)
            if count >= limit:
                return {
                    "allowed": False,
                    "remaining": 0,
                    "retry_after_seconds": retry_after,
                }

            conn.execute(
                """
                UPDATE rate_limits
                SET count = count + 1
                WHERE scope = ? AND actor_key = ?
                """,
                (scope, actor_key),
            )
        return {
            "allowed": True,
            "remaining": max(limit - count - 1, 0),
            "retry_after_seconds": 0,
        }

    def pick_post(self, *, mood: str | None, listener_key: str, avoid_seen: bool = True) -> SongDelivery | None:
        normalized_mood = normalize_mood(mood) if mood else None
        params: list[object] = []
        mood_clause = ""
        if normalized_mood:
            mood_clause = "AND mood = ?"
            params.append(normalized_mood)
        seen_clause = ""
        if avoid_seen:
            seen_clause = """
                AND id NOT IN (
                    SELECT post_id FROM deliveries WHERE listener_key = ?
                )
            """
            params.append(listener_key)

        query = f"""
            SELECT *
            FROM song_posts
            WHERE report_count < 3
              {mood_clause}
              {seen_clause}
            ORDER BY
              (like_count * 3 + save_count * 2 - skip_count - report_count * 5) DESC,
              RANDOM()
            LIMIT 1
        """
        with self.connect() as conn:
            row = conn.execute(query, params).fetchone()
            if row is None and avoid_seen:
                row = conn.execute(
                    """
                    SELECT *
                    FROM song_posts
                    WHERE report_count < 3
                      {mood_clause}
                    ORDER BY
                      (like_count * 3 + save_count * 2 - skip_count - report_count * 5) DESC,
                      RANDOM()
                    LIMIT 1
                    """,
                    params[:1] if normalized_mood else [],
                ).fetchone()
            if row is None:
                return None
            post = self._row_to_post(row)
            delivery_id = f"delivery_{uuid.uuid4().hex[:12]}"
            conn.execute(
                "INSERT INTO deliveries (id, post_id, listener_key, created_at) VALUES (?, ?, ?, ?)",
                (delivery_id, post.id, listener_key, datetime.now(timezone.utc).isoformat()),
            )
        return SongDelivery(delivery_id=delivery_id, post=post, search_links=build_search_links(post))

    def react(self, *, post_id: str, reaction: str, reply_message: str | None = None) -> SongPost | None:
        reaction_column = {
            "like": "like_count",
            "save": "save_count",
            "skip": "skip_count",
        }.get(reaction)
        if reaction_column is None:
            raise ValueError("reaction must be one of: like, save, skip.")
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM song_posts WHERE id = ?", (post_id,)).fetchone()
            if row is None:
                return None
            conn.execute(
                f"UPDATE song_posts SET {reaction_column} = {reaction_column} + 1 WHERE id = ?",
                (post_id,),
            )
            conn.execute(
                "INSERT INTO reactions (id, post_id, reaction, reply_message, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    f"reaction_{uuid.uuid4().hex[:12]}",
                    post_id,
                    reaction,
                    reply_message,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            updated = conn.execute("SELECT * FROM song_posts WHERE id = ?", (post_id,)).fetchone()
        return self._row_to_post(updated)

    def report(self, *, post_id: str, reason: str) -> SongPost | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM song_posts WHERE id = ?", (post_id,)).fetchone()
            if row is None:
                return None
            conn.execute("UPDATE song_posts SET report_count = report_count + 1 WHERE id = ?", (post_id,))
            conn.execute(
                "INSERT INTO reactions (id, post_id, reaction, reply_message, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    f"report_{uuid.uuid4().hex[:12]}",
                    post_id,
                    "report",
                    reason,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            updated = conn.execute("SELECT * FROM song_posts WHERE id = ?", (post_id,)).fetchone()
        return self._row_to_post(updated)

    def chart(self, *, mood: str | None, period: str, limit: int) -> list[SongPost]:
        period_clause = ""
        params: list[object] = []
        if mood:
            period_clause += " AND mood = ?"
            params.append(normalize_mood(mood))
        if period == "today":
            period_clause += " AND date(created_at) = date('now')"
        limit = max(1, min(limit, 10))
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM song_posts
                WHERE report_count < 3
                  {period_clause}
                ORDER BY (like_count * 3 + save_count * 2 - skip_count - report_count * 5) DESC,
                         created_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def room_stats(self) -> list[dict[str, object]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    mood,
                    COUNT(*) AS post_count,
                    SUM(CASE WHEN parent_post_id IS NOT NULL THEN 1 ELSE 0 END) AS relay_count,
                    SUM(like_count) AS like_count,
                    SUM(save_count) AS save_count,
                    MAX(created_at) AS last_post_at
                FROM song_posts
                WHERE report_count < 3
                GROUP BY mood
                ORDER BY post_count DESC, relay_count DESC, last_post_at DESC
                """
            ).fetchall()
        return [
            {
                "mood": row["mood"],
                "post_count": int(row["post_count"] or 0),
                "relay_count": int(row["relay_count"] or 0),
                "like_count": int(row["like_count"] or 0),
                "save_count": int(row["save_count"] or 0),
                "last_post_at": row["last_post_at"],
            }
            for row in rows
        ]

    def relay_board(self, *, mood: str | None, limit: int) -> list[dict[str, object]]:
        normalized_mood = normalize_mood(mood) if mood else None
        params: list[object] = []
        mood_clause = ""
        if normalized_mood:
            mood_clause = "AND mood = ?"
            params.append(normalized_mood)
        limit = max(1, min(limit, 10))
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM song_posts
                WHERE report_count < 3
                  {mood_clause}
                ORDER BY COALESCE(relay_root_id, id) ASC, relay_depth ASC, created_at ASC
                """,
                params,
            ).fetchall()

        chains: dict[str, list[SongPost]] = {}
        for row in rows:
            post = self._row_to_post(row)
            chains.setdefault(post.relay_root_id or post.id, []).append(post)

        board: list[dict[str, object]] = []
        for root_id, posts in chains.items():
            ordered = sorted(posts, key=lambda post: (post.relay_depth, post.created_at))
            root = ordered[0]
            latest = ordered[-1]
            board.append(
                {
                    "root_id": root_id,
                    "chain_length": len(ordered),
                    "max_depth": max(post.relay_depth for post in ordered),
                    "like_count": sum(post.like_count for post in ordered),
                    "save_count": sum(post.save_count for post in ordered),
                    "last_post_at": max(post.created_at for post in ordered),
                    "root": root,
                    "latest": latest,
                }
            )

        board.sort(
            key=lambda item: (
                int(item["chain_length"]),
                int(item["like_count"]) + int(item["save_count"]),
                str(item["last_post_at"]),
            ),
            reverse=True,
        )
        return board[:limit]

    def relay_chain(self, *, post_id: str, limit: int) -> list[SongPost]:
        post = self.get_post(post_id)
        if post is None:
            return []
        root_id = post.relay_root_id or post.id
        limit = max(1, min(limit, 20))
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM song_posts
                WHERE report_count < 3
                  AND (relay_root_id = ? OR id = ?)
                ORDER BY relay_depth ASC, created_at ASC
                LIMIT ?
                """,
                (root_id, root_id, limit),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    @staticmethod
    def _row_to_post(row: sqlite3.Row) -> SongPost:
        return SongPost(
            id=row["id"],
            title=row["title"],
            artist=row["artist"],
            mood=row["mood"],
            message=row["message"],
            link=row["link"],
            nickname=row["nickname"],
            created_at=row["created_at"],
            like_count=row["like_count"],
            save_count=row["save_count"],
            skip_count=row["skip_count"],
            report_count=row["report_count"],
            parent_post_id=row["parent_post_id"],
            relay_root_id=row["relay_root_id"],
            relay_depth=row["relay_depth"],
        )


def build_search_links(post: SongPost) -> dict[str, str]:
    from urllib.parse import quote_plus

    query = quote_plus(f"{post.artist} {post.title}")
    return {
        "youtube": f"https://www.youtube.com/results?search_query={query}",
        "melon": f"https://www.melon.com/search/total/index.htm?q={query}",
        "spotify": f"https://open.spotify.com/search/{query}",
    }
