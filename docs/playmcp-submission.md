# PlayMCP Submission Draft

## Console Copy

### Display Name

노래우체통 MCP

### Representative Image

`assets/playmcp-icon.png`

### Short Description

노래를 한 곡 받으면, 내가 좋아하는 다른 노래와 짧은 문구를 다음 사람에게 추천해 릴레이를 잇는 익명 음악 MCP입니다.

### Long Description

노래우체통은 AI가 임의로 노래를 추천하는 서버가 아니라, 사용자가 남긴 노래와 짧은 문구를 다음 사용자에게 배달하고, 노래를 받은 사용자가 자기가 좋아하는 다른 노래와 문구를 다음 사람에게 추천해 릴레이를 잇는 가벼운 커뮤니티 MCP입니다. 사용자는 노래 받기, 추천 이어가기, 공감/저장/스킵/신고 반응, 릴레이 기록 확인을 할 수 있습니다. 서버는 게시물, 배달 이력, 릴레이 체인, 반응, 신고 누적, 남용 방지용 해시 카운터를 저장하므로 시간이 지날수록 실제 사용자 취향과 릴레이 흐름이 쌓입니다. 가사나 음원 파일은 저장하거나 반환하지 않으며, 곡명/아티스트/검색 링크만 제공합니다.

### Suggested Tags

음악, 커뮤니티, 추천, 릴레이, 우체통

## Review Prompts

- 노래 하나 받을래.
- 나도 다음 사람에게 노래와 문구를 남길래.
- 아이유 밤편지를 다음 사람에게 추천해줘. 문구는 '오늘 밤 오래 들고 가도 좋은 노래'야.
- 방금 받은 노래에 공감 눌러줘.
- 방금 받은 노래 저장해줘.
- 방금 받은 노래 공유 카드 만들어줘.
- 지금 노래우체통에서 어떤 릴레이가 제일 길게 이어지고 있어?
- 방금 추천한 노래의 릴레이 기록 보여줘.
- 오늘 사람들이 가장 많이 공감한 추천곡 보여줘.

## Demo Transcript

Generate a reviewer-friendly tool-call transcript:

```bash
uv run --python 3.11 python scripts/reviewer_demo.py
uv run --python 3.11 python scripts/reviewer_demo.py --endpoint https://macmini.taild33a67.ts.net/mcp
```

## Endpoint

Register the Streamable HTTP endpoint:

```text
https://macmini.taild33a67.ts.net/mcp
```

Local default:

```text
http://127.0.0.1:8000/mcp
```

Health check for manual/cloud verification:

```text
https://macmini.taild33a67.ts.net/health
```

Browser metadata for manual/cloud verification:

```text
https://macmini.taild33a67.ts.net/
```

## Environment

```text
PORT=8000
MOOD_RADIO_DB=/data/mood-radio.sqlite
MOOD_RADIO_POST_LIMIT=20/3600
MOOD_RADIO_RECOMMEND_LIMIT=20/3600
MOOD_RADIO_REACT_LIMIT=80/3600
MOOD_RADIO_REPORT_LIMIT=20/3600
```

## PlayMCP Flow

1. Create a Kakao Cloud MCP server endpoint.
2. Register the endpoint in the PlayMCP developer console.
3. Use temporary registration while testing.
4. When final, request review from PlayMCP.
5. After approval, change visibility from private to public.
6. Submit the AGENTIC PLAYER 10 preliminary application.

## Review Notes

- This MCP needs a server because community posts, delivery history, relay chains, community boards, reactions, chart ranking, reports, and abuse-prevention counters are persisted in SQLite.
- The service never stores or returns lyrics or audio files.
- Community messages reject contact details, emails, open chat invitations, payment details, inline URLs, spam-like repetition, and lyrics labels.
- Direct user-supplied links are restricted to supported music services.
- Search links are generated for YouTube, Melon, and Spotify from song metadata.
- Reported posts are excluded from recommendations after repeated reports.
- Mutating tools can receive an optional `actor_hint`; the raw value is never stored, only a short hash for rate limiting.
- Follow-up actions can use either `post_id` or the `delivery_id` returned by `get_song`.
- Share cards are generated from stored song metadata and relay context, without lyrics or audio files.
- Exact duplicate song/message posts are rejected for 24 hours.
- Kakao Tools widget work is intentionally left as the next phase after preliminary qualification.
