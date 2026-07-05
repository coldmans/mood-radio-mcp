# Mood Radio MCP

같은 기분인 사람들이 남긴 노래가 도착하고, 받은 사람이 다음 사람에게 다시 노래를 넘기는 익명 무드 라디오 MCP입니다.

이 서버는 AI가 임의로 노래를 추천하는 도구가 아니라, 사용자가 남긴 노래와 한 줄 메시지를 무드별 커뮤니티 피드와 릴레이 체인으로 저장하고 다시 배달합니다. 음원이나 가사는 제공하지 않고, 곡명/아티스트/검색 링크만 반환합니다.

## Tools

- `get_radio_rooms`: 무드방 목록, 예시 요청, 커뮤니티 정책을 확인합니다.
- `post_song`: 무드방에 노래와 한 줄 메시지를 남깁니다.
- `pass_song`: 받은 노래의 `delivery_id`를 기준으로 다음 사람에게 노래를 이어 보냅니다.
- `get_song`: 특정 무드 또는 자연어 상황에서 아직 신고 누적이 낮은 노래 하나를 받습니다.
- `react_song`: 받은 노래에 공감, 저장, 스킵 반응을 남깁니다. `post_id` 또는 `delivery_id`를 사용할 수 있습니다.
- `get_mood_chart`: 오늘 또는 전체 인기 무드/곡 차트를 봅니다.
- `get_community_board`: 활성 무드방과 인기 릴레이를 함께 봅니다.
- `get_relay_chain`: 특정 노래가 속한 릴레이 기록을 봅니다.
- `get_share_card`: 받은 노래나 릴레이 노래를 공유하기 좋은 카드 문구로 만듭니다.
- `report_song`: 부적절한 노래/메시지를 신고합니다.

## Why It Needs A Server

- 사용자가 남긴 노래와 메시지를 무드방별로 저장합니다.
- 같은 사용자에게 같은 노래가 반복 배달되지 않도록 배달 이력을 기록합니다.
- 받은 노래에서 다음 노래로 이어지는 릴레이 체인을 저장합니다.
- 활성 무드방과 길어진 릴레이를 커뮤니티 보드로 집계합니다.
- 공감/저장/스킵/신고 반응을 누적해 차트와 추천 우선순위에 반영합니다.
- 신고가 누적된 게시물을 추천 피드에서 제외합니다.
- 익명 사용자 힌트를 해시로 저장해 게시/릴레이/반응/신고 남용을 제한합니다.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mood-radio-mcp
```

기본 포트는 `8000`입니다.

```bash
PORT=8080 mood-radio-mcp
MOOD_RADIO_DB=/tmp/mood-radio.sqlite mood-radio-mcp
MOOD_RADIO_POST_LIMIT=20/3600 mood-radio-mcp
```

Streamable HTTP endpoint:

```text
http://127.0.0.1:8000/mcp
```

Health check:

```text
http://127.0.0.1:8000/health
```

Human-readable service metadata:

```text
http://127.0.0.1:8000/
```

## Docker

```bash
docker build -t mood-radio-mcp .
docker run --rm -p 8000:8000 \
  -e PORT=8000 \
  -e MOOD_RADIO_DB=/data/mood-radio.sqlite \
  -v mood-radio-data:/data \
  mood-radio-mcp
```

Docker Compose:

```bash
docker compose up --build
```

## Test

```bash
pytest
```

Convenience targets:

```bash
make test
make audit
make bundle
make docker-smoke
make preflight ENDPOINT=https://<kakao-cloud-endpoint>
```

HTTP endpoint smoke test:

```bash
uv run --python 3.11 python scripts/smoke_http.py http://127.0.0.1:8000/mcp
```

Reviewer-friendly demo transcript:

```bash
uv run --python 3.11 python scripts/reviewer_demo.py
uv run --python 3.11 python scripts/reviewer_demo.py --endpoint http://127.0.0.1:8000/mcp
```

Deployment preflight with health + MCP smoke:

```bash
uv run --python 3.11 python scripts/submission_audit.py
uv run --python 3.11 python scripts/build_release_bundle.py
uv run --python 3.11 python scripts/preflight_endpoint.py http://127.0.0.1:8000
```

## Example Prompts

- "무드라디오 방 목록 보여줘."
- "새벽 감성방에서 사람들이 남긴 노래 하나 줘."
- "비 오는 퇴근길에 어울리는 노래 받아줘."
- "그냥 오늘 야근 끝나고 집 가는 길 기분으로 하나 받아줘."
- "방금 받은 노래에서 이어달리기로 aespa의 Supernova를 다음 사람에게 넘겨줘. 메시지는 '조금 더 힘내기'야."
- "방금 받은 노래 저장해줘."
- "방금 넘긴 노래 공유 카드 만들어줘."
- "지금 무드라디오에서 어떤 릴레이가 제일 길게 이어지고 있어?"
- "이 노래가 어디서 이어져 왔는지 릴레이 기록 보여줘."
- "오늘 사람들이 가장 많이 공감한 무드라디오 차트 보여줘."

## PlayMCP Submission

제출용 콘솔 문구와 심사 프롬프트 초안은 `docs/playmcp-submission.md`에 정리했습니다.
배포 절차와 헬스체크는 `docs/deployment.md`에 정리했습니다.

## Safety Notes

- 가사와 음원 파일은 저장하거나 반환하지 않습니다.
- 링크가 없으면 YouTube/Melon/Spotify 검색 링크만 생성합니다.
- 메시지/답장에는 연락처, 이메일, 오픈채팅, 계좌, URL, 가사 라벨을 남길 수 없습니다.
- 곡명/아티스트처럼 공개 노출되는 메타데이터에도 URL, 연락처, 긴 숫자, 반복문자 스팸을 남길 수 없습니다.
- 공개 닉네임과 신고 사유에도 같은 커뮤니티 안전 규칙을 적용합니다.
- 같은 무드방에 같은 곡과 같은 메시지를 24시간 안에 반복해서 남길 수 없습니다.
- `actor_hint`가 제공되면 원문 대신 해시만 저장해 게시/릴레이/반응/신고 요청 수를 제한합니다.
- 직접 링크는 YouTube, Melon, Spotify, SoundCloud, Apple Music 등 지원 음악 서비스만 허용합니다.
- 신고가 누적된 게시물은 추천에서 제외됩니다.
- 같은 곡이 피드를 도배하지 않도록 최근 중복을 낮은 우선순위로 둡니다.
