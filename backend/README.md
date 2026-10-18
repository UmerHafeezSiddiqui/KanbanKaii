# AI Ticket Management API

## Local setup

From the repository root, use Python 3.11 or newer to install dependencies once:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Configure `backend/.env`, start Docker Desktop, and create the Redis container
using the loopback binding and named volume in the root README. Start the backend
services with one command from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local-server.ps1
```

The launcher starts Redis, FastAPI and the ARQ worker. It selects a working
environment from `backend/.venv`, `backend/venv`, then `.runtime/audit-venv`;
it rejects Redis port bindings outside loopback and never deletes stored data.
Add `-UseNgrok` for the default ngrok installation, or `-TunnelName your-tunnel`
for an existing Cloudflare Tunnel. The frontend starts separately.

API documentation is available at `http://localhost:8000/docs` and the health check at `http://localhost:8000/health`.

General route handlers live in `app/routes`; Slack and organization routes live
in their feature directories. Routers are registered in `app/main.py`.

Copy `backend/.env.example` to `backend/.env` and configure Supabase, Redis,
Slack and Gemini (`AI_MODEL_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL`).
The launcher does not start or require Ollama. Multiple frontend origins can be
supplied as a comma-separated `FRONTEND_ORIGINS` value.

The triage endpoint is `POST /api/webhook/triage`. It requires a Supabase Bearer token,
and the request's `owner_id` must match the authenticated user. It returns `201`
for an actionable task and `200` for ignored chatter. Redis must be available for
the per-user AI limit; exhausted limits return `429`, and limiter failures return
`503`. OAuth state is consumed once; invitation indexes preserve the longest
remaining invitation lifetime. Redis 7 or newer is required.

From the repository root, run backend checks with:

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Use the selected environment's Python if it differs. The worker retries temporary
network/service failures and selected temporary database errors after 5 and 15
seconds, for three attempts total. Invalid messages, permission/credential errors
and malformed model output are terminal. Monitor deliveries that exhaust retries.
The worker scans up to 100 uncommitted pending deliveries older than 15 minutes
at startup and every five minutes, enqueueing with the same stable job IDs.
Permanent/exhausted failures remain terminal. The launcher checks a five-second
worker heartbeat before reporting readiness. From this directory, use
`python -m arq --check app.workers.slack_worker.WorkerSettings` for a manual check.
A heartbeat proves worker polling, not Slack/model availability. Production
requires a supervisor and pending-delivery monitoring.

## Supabase setup

1. Create a Supabase project.
2. For a new database, run files from the repository-root `supabase/migrations/`
   in filename order. For an existing database, inspect the schema and apply
   only missing migrations.
3. Add the project URL and backend service-role key to `.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-server-only-service-role-key
```

Never expose the service-role key in the frontend. It bypasses row-level security
and is used only by trusted backend operations. Browser API requests use the
user's JWT so ticket and integration RLS policies apply.

Migrations through `202610180029` are required for service-role-only invitation
acceptance, atomic Slack ticket batches and retention of recoverable deliveries. Pause the API and worker,
apply missing migrations, deploy the matching backend, then restart. The launcher
does not migrate the database. From the repository root, run
`.\scripts\test-database.ps1` with Docker available to validate all migrations,
invitation privileges, atomic rollback/replay, pending-delivery retention and an
authenticated owner/lead/member/outsider permission matrix. The script uses a
separate disposable local Supabase database; it never connects to a hosted project.
The hosted database still needs migration `202610180029` applied separately.
