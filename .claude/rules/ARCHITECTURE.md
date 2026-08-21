# Architecture

## Stack

- **Backend** — Python 3.14, FastAPI, SQLAlchemy 2.0 async, SQLite in WAL mode,
  Alembic, argon2 for passwords, Fernet for provider API keys.
- **Frontend** — Vite + React 19 + TypeScript, MUI with a hand-built Material 3
  theme, i18next (en/ru). Compiles to static files served by FastAPI itself.
- **Media** — ffmpeg. No ML library is installed anywhere in this repository;
  speech-to-text and summarisation are remote OpenAI-compatible services.
- **Packaging** — one Docker image, one `/data` volume, one compose file.

## Commands

| What | Where | Command |
|---|---|---|
| Tests | `backend/` | `uv run pytest` |
| API (dev) | `backend/` | `uv run uvicorn app.main:create_app --factory --reload --port 8927` |
| Worker (dev) | `backend/` | `uv run python -m app.worker` |
| UI (dev) | `frontend/` | `npm run dev` |
| Typecheck UI | `frontend/` | `npm run typecheck` |
| Image | root | `docker build -t tany:dev .` |
| New migration | `backend/` | `DATA_DIR=/tmp/x uv run alembic revision -m "..." --autogenerate` |

Alembic needs `DATA_DIR` because it migrates whichever database the settings
point at; the app passes the URL programmatically, the CLI falls back to the
same settings. Migration files are renamed to `000N_slug.py` by hand to keep
them readable in order.

## Layout

```
.
├── Dockerfile                  multi-stage: node builds the SPA, python runs it
├── docker-compose.yml          published image; .dev.yml overrides with build
├── SPEC.md                     design decisions with rationale (Russian)
├── backend/
│   ├── app/
│   │   ├── main.py             app factory + lifespan (migrations, db, secret)
│   │   ├── config.py           Settings, unprefixed env vars
│   │   ├── db.py               engine, session factory, SQLite pragmas
│   │   ├── models.py           SQLAlchemy models
│   │   ├── schemas.py          shared pydantic models
│   │   ├── deps.py             session/settings/current-user dependencies
│   │   ├── errors.py           ApiError -> {"error": {code, message, params}}
│   │   ├── security.py         argon2 hashing
│   │   ├── sessions.py         signed httpOnly session cookies
│   │   ├── secrets.py          /data/secret.key
│   │   ├── static.py           SPA serving with an /api-safe catch-all
│   │   ├── migrator.py         alembic upgrade head, in-process
│   │   ├── crypto.py           Fernet encryption and masking for API keys
│   │   ├── seed.py             env -> database bootstrap for providers
│   │   ├── storage.py          streaming upload to disk with SHA-256
│   │   ├── media.py            ffprobe and ffmpeg; the only media knowledge
│   │   ├── stt.py              OpenAI transcription protocol client
│   │   ├── llm.py              OpenAI chat protocol client, plain and streamed
│   │   ├── chunking.py         where to cut a long recording
│   │   ├── summarize.py        token budget and map-reduce splitting
│   │   ├── summary_runner.py   produces one summary, in one pass or in stages
│   │   ├── presets.py          the built-in prompts
│   │   ├── worker.py           claim loop; also the worker entrypoint
│   │   └── api/                health, setup, auth, jobs, providers, presets,
│   │                           summaries
│   ├── migrations/             alembic
│   └── tests/                  pytest, async, real HTTP through ASGITransport
│       └── stubs.py            stand-in STT server (a stub, never a patch)
└── frontend/src/
    ├── api/client.ts           fetch wrapper, throws ApiError with a code
    ├── theme.ts                M3 palette generated from one seed colour
    ├── i18n.ts + locales/      en, ru
    ├── useApiError.ts          error code -> translated message
    ├── components/             AppShell, AuthLayout, LanguageSwitch
    └── pages/                  Setup, Login, Jobs, Transcript
```

## Invariants

1. **No ML in the backend.** STT and LLM are two independent HTTP clients with
   different protocols, never a shared "AI provider" abstraction.
2. **Raw STT output is immutable.** Exports (txt/md/srt/vtt) and user edits are
   layers computed on top; changing an export format never re-transcribes.
3. **`owner_id` exists from the first migration.** Retrofitting it later would
   mean rewriting every query.
4. **The queue is the `jobs` table.** No broker. Claiming is a single
   `UPDATE ... RETURNING` transaction; stale heartbeats requeue on worker start.
5. **The API is the whole product surface.** Anything the UI can do is reachable
   with a bearer token.

## Status

Milestones 0 to 3 complete: auth, the transcription pipeline, chunking on
silence, live progress over SSE, cancellation that really stops the work,
per-chunk retries, crash recovery, a player that follows the transcript, and
summaries by preset with automatic map-reduce and a kept history.

Not built yet, in the order [SPEC.md](../../SPEC.md) plans them: URL and yt-dlp
ingest, search and export and sharing, diarisation.

Known gaps left deliberately open:

- Summaries have no cancel button and no retry. The transcription path has
  both; the summary path does not, and a stuck summary needs deleting.
- The token estimate is characters divided by three, not a tokeniser. It is
  deliberately pessimistic, so it splits earlier than strictly necessary.

- A provider can only be created from the environment; editing it in the UI
  arrives with the settings screen.
- `language` comes back from the provider verbatim and is fed straight back to
  later chunks. OpenAI answers `english` where faster-whisper answers `en`, and
  only the second form is a valid input. Against a cloud endpoint this silently
  weakens the forcing rather than breaking it, so it needs a normalising table
  before the provider list widens.
- Segment edits have a column and an export path but no endpoint yet.
- Both SSE streams poll the database on a timer. That is fine at this size and
  survives multiple API processes, which a shared in-memory bus would not.
- The worker has no healthcheck; `docker-compose.yml` disables the inherited
  one. A real probe belongs on `heartbeat_at`.
