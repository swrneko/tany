# tany — transcribe anything

Self-hosted transcription service: any media file or link becomes timestamped
text, optionally summarised by an LLM. All AI runs behind OpenAI-compatible
HTTP endpoints, so the backend image carries no ML weights.

## Run

```bash
# Backend (from backend/)
uv sync
uv run pytest                                   # test suite
uv run uvicorn app.main:create_app --factory --reload --port 8927 \
  --env-file ../.env

# Frontend (from frontend/) — proxies /api to :8927
npm install
npm run dev

# Whole thing in Docker
docker compose up -d                            # published image
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Local development needs `DATA_DIR` pointed somewhere writable; the default is
`/data`, which only exists inside the container.

## Map

- Design decisions and their rationale: [SPEC.md](SPEC.md) (Russian)
- Architecture and module index: [.claude/rules/ARCHITECTURE.md](.claude/rules/ARCHITECTURE.md)

## Conventions

- **English only** in code, comments, identifiers, and commit messages. The UI
  is multilingual; user-facing strings live in `frontend/src/locales/`.
- **The API never returns a translated message.** Errors carry a stable `code`
  plus `params`; the frontend renders the text. `message` is an English
  fallback for curl and webhooks only.
- **TDD.** Test first, watch it fail, then implement. Tests drive the public
  HTTP surface through `httpx.AsyncClient` — internal classes are not mocked.
- **Mock only at system boundaries**: ffmpeg, the STT and LLM endpoints,
  yt-dlp, the filesystem. External HTTP is faked with a stub ASGI app, not with
  patches, so the wire format stays under test.
- **Primary keys are UUIDv7** (`uuid.uuid7()`, stdlib on Python 3.14).
- Migrations run automatically when the API starts; never ask a user to exec
  into a container.
