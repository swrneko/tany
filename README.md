# tany

Self-hosted transcription. Feed it a file or a link, get timestamped text, and
optionally an LLM summary shaped by your own presets.

Everything AI-shaped happens over OpenAI-compatible HTTP, so you can point it at
Ollama, LM Studio, vLLM, a local Whisper server, or a cloud API — the service
itself ships no model weights.

> **Status: early.** Milestone 0 is done — the service installs, runs, and has
> accounts. Transcription itself lands in the next milestone. See
> [SPEC.md](SPEC.md) for the full plan.

## Quick start

```bash
cp .env.example .env      # optional; every value has a default
docker compose up -d
```

Open `http://localhost:8927`. The first visit asks you to create an
administrator account — there is no default password and no open registration.

## Configuration

All settings are environment variables; see [.env.example](.env.example).

`AUTH_MODE` picks how identity works:

| Mode | Behaviour |
|---|---|
| `builtin` | Accounts live in this service. First start opens a setup wizard. |
| `proxy` | Identity comes from a reverse proxy header (Authelia, authentik). |
| `disabled` | No authentication. Only reasonable behind a trusted localhost. |

## Data and backups

Everything lives in one volume: the SQLite database, the normalised audio, and
the instance secret. To back up, copy the volume:

```bash
docker compose stop
tar czf tany-backup.tgz -C /var/lib/docker/volumes/tany_data/_data .
docker compose start
```

## Security notes

Read these before exposing the service to the internet.

- **There is no built-in HTTPS.** Put it behind Caddy, Traefik, or nginx. The
  service honours `X-Forwarded-*` so share links get the right scheme and host.
- **The encryption key sits next to the data it encrypts** (`/data/secret.key`).
  Provider API keys are encrypted with it, which protects them if a database
  backup leaks — it does *not* protect them from anyone who can read the
  volume. That trade-off is deliberate: a self-hosted service that demands
  external key management before it starts is a service nobody starts.
- **`AUTH_MODE=disabled` means exactly that.** Anyone who can reach the port has
  full access, including your provider API keys.

## Development

See [AGENTS.md](AGENTS.md).

## License

MIT
