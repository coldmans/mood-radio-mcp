from __future__ import annotations

import re
from urllib.parse import urlparse

MAX_TITLE_LENGTH = 80
MAX_ARTIST_LENGTH = 80
MAX_MESSAGE_LENGTH = 160
MAX_NICKNAME_LENGTH = 32

URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
INLINE_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
BLOCKED_WORDS = {
    "죽어",
    "자살",
    "혐오",
    "개새끼",
    "병신",
}
CONTACT_HINTS = {
    "카톡",
    "카카오톡",
    "오픈채팅",
    "open.kakao",
    "텔레그램",
    "telegram",
    "디스코드",
    "discord",
    "인스타",
    "instagram",
    "계좌",
    "입금",
    "후원",
}
ALLOWED_LINK_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "melon.com",
    "www.melon.com",
    "spotify.com",
    "open.spotify.com",
    "soundcloud.com",
    "www.soundcloud.com",
    "music.apple.com",
}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?82[-.\s]?)?0?1[016789][-\s.]?\d{3,4}[-\s.]?\d{4}")
LONG_NUMBER_RE = re.compile(r"\d{4}[-\s.]?\d{4}[-\s.]?\d{4,}")
REPEATED_CHAR_RE = re.compile(r"(.)\1{11,}")
LYRICS_LABEL_RE = re.compile(r"(가사|lyrics|후렴|chorus)\s*[:：]", re.IGNORECASE)


def clean_text(value: str, *, max_length: int, field_name: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError(f"{field_name} is required.")
    if len(text) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return text


def clean_optional_url(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    if len(text) > 500:
        raise ValueError("link is too long.")
    if not URL_RE.match(text):
        raise ValueError("link must be an http(s) URL.")
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_LINK_HOSTS:
        raise ValueError("link must point to a supported music or search service.")
    return text


def validate_community_text(text: str) -> None:
    lowered = text.lower()
    if any(word in lowered for word in BLOCKED_WORDS):
        raise ValueError("message contains unsafe or abusive wording.")
    if any(hint in lowered for hint in CONTACT_HINTS):
        raise ValueError("message must not include contact, payment, or solicitation details.")
    if EMAIL_RE.search(text) or PHONE_RE.search(text) or LONG_NUMBER_RE.search(text):
        raise ValueError("message must not include direct personal contact or payment identifiers.")
    if INLINE_URL_RE.search(text):
        raise ValueError("message must not include URLs; use the link field for music links.")
    if REPEATED_CHAR_RE.search(text):
        raise ValueError("message looks like spam.")
    if LYRICS_LABEL_RE.search(text):
        raise ValueError("message must not include lyrics excerpts.")


def validate_public_metadata(text: str, *, field_name: str) -> None:
    if EMAIL_RE.search(text) or PHONE_RE.search(text) or LONG_NUMBER_RE.search(text):
        raise ValueError(f"{field_name} must not include contact or payment identifiers.")
    if INLINE_URL_RE.search(text):
        raise ValueError(f"{field_name} must not include URLs; use the link field for music links.")
    if REPEATED_CHAR_RE.search(text):
        raise ValueError(f"{field_name} looks like spam.")
