from __future__ import annotations

MOOD_ALIASES: dict[str, str] = {
    "새벽": "새벽",
    "새벽감성": "새벽",
    "새벽 감성": "새벽",
    "밤": "새벽",
    "잠 안 오는 밤": "새벽",
    "잠안오는밤": "새벽",
    "불면": "새벽",
    "퇴근": "퇴근길",
    "퇴근길": "퇴근길",
    "퇴근 후": "퇴근길",
    "퇴근후": "퇴근길",
    "야근": "퇴근길",
    "집 가는 길": "퇴근길",
    "집가는길": "퇴근길",
    "귀가": "퇴근길",
    "일 끝": "퇴근길",
    "일끝": "퇴근길",
    "회사 끝": "퇴근길",
    "회사끝": "퇴근길",
    "비": "비오는날",
    "비오는": "비오는날",
    "비오는날": "비오는날",
    "비 오는 날": "비오는날",
    "장마": "비오는날",
    "우산": "비오는날",
    "빗소리": "비오는날",
    "집중": "집중",
    "공부": "집중",
    "작업": "집중",
    "마감": "집중",
    "코딩": "집중",
    "과제": "집중",
    "이별": "이별",
    "헤어짐": "이별",
    "설렘": "설렘",
    "썸": "설렘",
    "데이트": "설렘",
    "산책": "산책",
    "걷기": "산책",
    "위로": "위로",
    "힘든날": "위로",
    "지친날": "위로",
    "괜찮아지고": "위로",
    "운동": "운동",
    "러닝": "운동",
    "헬스": "운동",
    "조깅": "운동",
}

DEFAULT_MOOD = "위로"
VALID_MOODS = sorted(set(MOOD_ALIASES.values()))


def normalize_mood(value: str | None) -> str:
    if not value:
        return DEFAULT_MOOD
    compact = "".join(str(value).lower().split())
    return MOOD_ALIASES.get(compact, str(value).strip()[:24] or DEFAULT_MOOD)


def infer_mood_from_text(value: str | None) -> str | None:
    if not value:
        return None
    compact = "".join(str(value).lower().split())
    aliases = sorted(MOOD_ALIASES, key=len, reverse=True)
    for alias in aliases:
        alias_compact = "".join(alias.lower().split())
        if alias_compact and alias_compact in compact:
            return MOOD_ALIASES[alias]
    return None


def mood_rooms() -> list[dict[str, object]]:
    rooms: dict[str, list[str]] = {}
    for alias, mood in MOOD_ALIASES.items():
        rooms.setdefault(mood, []).append(alias)
    return [
        {
            "mood": mood,
            "aliases": sorted(set(aliases)),
        }
        for mood, aliases in sorted(rooms.items())
    ]
