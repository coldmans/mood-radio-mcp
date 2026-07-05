# Deployment Notes

## Runtime

Mood Radio MCP runs as a Streamable HTTP MCP server.

```text
MCP endpoint: /mcp
Health check: /health
Service metadata: /
Default port: 8000
```

`/health` returns readiness plus non-personal operational counters such as visible posts, hidden posts, deliveries, reactions, reports, relay posts, and active rate-limit buckets.
`/` returns non-personal service metadata, the MCP registration path, tool names, and safety notes for cloud consoles or reviewers.

## Required Environment

```text
PORT=8000
MOOD_RADIO_DB=/data/mood-radio.sqlite
```

Use a persistent disk or volume for `MOOD_RADIO_DB` if you want posts, reactions, and reports to survive container restarts.

Optional rate limit environment variables use `<limit>/<window_seconds>` format:

```text
MOOD_RADIO_POST_LIMIT=20/3600
MOOD_RADIO_PASS_LIMIT=20/3600
MOOD_RADIO_REACT_LIMIT=80/3600
MOOD_RADIO_REPORT_LIMIT=20/3600
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

Local compose run:

```bash
docker compose up --build
```

Check the process:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
make audit
make bundle
make docker-smoke
uv run --python 3.11 python scripts/submission_audit.py
uv run --python 3.11 python scripts/build_release_bundle.py
uv run --python 3.11 python scripts/reviewer_demo.py --endpoint http://127.0.0.1:8000/mcp
uv run --python 3.11 python scripts/smoke_http.py http://127.0.0.1:8000/mcp
uv run --python 3.11 python scripts/preflight_endpoint.py http://127.0.0.1:8000
```

## PlayMCP Registration

Register only the MCP endpoint, not the health endpoint:

```text
https://<kakao-cloud-endpoint>/mcp
```

Recommended flow:

1. Deploy the container to the Kakao Cloud MCP server endpoint.
2. Run `uv run --python 3.11 python scripts/submission_audit.py` before changing the registered endpoint.
3. Run `uv run --python 3.11 python scripts/build_release_bundle.py` if you need a tarball for upload or handoff.
4. Run `uv run --python 3.11 python scripts/reviewer_demo.py --endpoint https://<endpoint>/mcp` for a human-readable demo transcript.
5. Run `uv run --python 3.11 python scripts/preflight_endpoint.py https://<endpoint>`.
6. Confirm the preflight prints `health_ok: True`, `ready_for_feed: True`, `situation_match: 퇴근길`, `pass_ok: True`, and `share_card_ok: True`.
7. Register the endpoint in PlayMCP as a temporary registration.
8. Test the review prompts in `docs/playmcp-submission.md`.
9. When final, request PlayMCP review.

Equivalent Make targets:

```bash
make audit
make bundle
make preflight ENDPOINT=https://<endpoint>
```

## Release Bundle

For upload or handoff, create a source bundle:

```bash
uv run --python 3.11 python scripts/build_release_bundle.py
```

This writes:

```text
dist/mood-radio-mcp-<version>.tar.gz
dist/mood-radio-mcp-<version>.manifest.json
```

The manifest includes the archive SHA-256 and per-file SHA-256 hashes.

## Operational Notes

- The container runs as the non-root `appuser` user and writes community state under `/data`.
- SQLite uses WAL mode, foreign keys, a 10 second busy timeout, and indexes for mood lookup, relay chains, deliveries, and reactions.
- `/health` exposes aggregate operational counters only; it does not expose submitted messages, listener hints, actor hints, or raw user identifiers.
- `get_community_board` is computed from persisted posts and relay chains; no external analytics service is required for the MVP.
- `get_share_card` is read-only and formats stored song metadata plus relay context into shareable text.
- Startup includes a lightweight migration for older local SQLite files that do not yet have relay columns.
- Message, nickname, reply, and report-reason validation rejects direct contact/payment identifiers, inline URLs, spam-like repetition, and lyrics labels before data is stored.
- Public song metadata rejects direct contact/payment identifiers, inline URLs, and spam-like repetition before data is stored.
- Exact duplicate song/message posts in the same mood room are rejected for 24 hours to reduce low-effort feed spam.
- Mutating tools accept an optional `actor_hint`. The raw hint is never stored; only a short hash is used for server-side rate limits.
- User-supplied links are limited to supported music hosts; search links are generated from song metadata when no link is provided.
- This is enough for a small contest MVP, but a public Kakao Tools version should move community data to a managed database.
- The server stores song metadata and short messages only. It does not store lyrics, audio files, or personal contact details.
