# PlayMCP Submission Draft

## Console Copy

### Display Name

무드라디오 MCP

### Short Description

같은 기분인 사람들이 남긴 노래가 도착하고, 받은 사람이 다음 사람에게 다시 노래를 넘기는 익명 무드 라디오입니다.

### Long Description

무드라디오는 AI가 임의로 노래를 추천하는 서버가 아니라, 사용자들이 무드방에 남긴 노래와 한 줄 메시지를 다음 사용자에게 배달하고, 받은 사용자가 다시 다음 사람에게 노래를 이어 보내는 가벼운 커뮤니티 MCP입니다. 사용자는 새벽, 퇴근길, 비오는날, 위로 같은 방에서 노래를 받고, 이어달리기, 공감/저장/스킵/신고 반응을 남길 수 있습니다. 서버는 게시물, 배달 이력, 릴레이 체인, 활성 무드방, 반응, 신고 누적, 남용 방지용 해시 카운터를 저장하므로 시간이 지날수록 실제 사용자 취향과 분위기가 반영됩니다. 가사나 음원 파일은 저장하거나 반환하지 않으며, 곡명/아티스트/검색 링크만 제공합니다.

### Suggested Tags

음악, 커뮤니티, 추천, 릴레이, 무드

## Review Prompts

- 무드라디오 방 목록 보여줘.
- 새벽 감성방에서 사람들이 남긴 노래 하나 줘.
- 비 오는 퇴근길에 어울리는 노래 받아줘.
- 오늘 야근 끝나고 집 가는 길 기분으로 사람들이 남긴 노래 하나 줘.
- 방금 받은 노래에서 이어달리기로 aespa의 Supernova를 다음 사람에게 넘겨줘. 메시지는 "조금 더 힘내기"야.
- 지금 무드라디오에서 어떤 릴레이가 제일 길게 이어지고 있어?
- 방금 넘긴 노래의 릴레이 기록 보여줘.
- 방금 넘긴 노래 공유 카드 만들어줘.
- 방금 받은 노래에 공감 눌러줘.
- 방금 받은 노래 저장해줘.
- 오늘 사람들이 가장 많이 공감한 무드라디오 차트 보여줘.

## Demo Transcript

Generate a reviewer-friendly tool-call transcript:

```bash
uv run --python 3.11 python scripts/reviewer_demo.py
uv run --python 3.11 python scripts/reviewer_demo.py --endpoint https://<kakao-cloud-endpoint>/mcp
```

## Endpoint

Register the Streamable HTTP endpoint:

```text
https://<kakao-cloud-endpoint>/mcp
```

Local default:

```text
http://127.0.0.1:8000/mcp
```

Health check for manual/cloud verification:

```text
https://<kakao-cloud-endpoint>/health
```

Browser metadata for manual/cloud verification:

```text
https://<kakao-cloud-endpoint>/
```

## Environment

```text
PORT=8000
MOOD_RADIO_DB=/data/mood-radio.sqlite
MOOD_RADIO_POST_LIMIT=20/3600
MOOD_RADIO_PASS_LIMIT=20/3600
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
- Situation-only prompts can be mapped to a matching mood room before a song is delivered.
- Follow-up actions can use either `post_id` or the `delivery_id` returned by `get_song`.
- Share cards are generated from stored song metadata and relay context, without lyrics or audio files.
- Exact duplicate song/message posts in the same mood room are rejected for 24 hours.
- Kakao Tools widget work is intentionally left as the next phase after preliminary qualification.
