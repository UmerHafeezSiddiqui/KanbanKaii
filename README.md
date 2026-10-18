# KanbanKaii

KanbanKaii is an AI-driven ticket management dashboard that turns actionable
Slack messages into structured Kanban tickets. It combines a React dashboard,
FastAPI backend, Supabase Auth/Postgres, Redis background jobs, Slack OAuth, and
a pluggable AI provider layer for local or hosted model triage.

The goal is simple: keep work conversations inside Slack, but automatically
capture the real tasks into a board where they can be assigned, edited, moved,
and tracked.

## What it does

- Creates Kanban tickets from actionable Slack mentions.
- Ignores chatter, empty mentions, and non-task questions.
- Splits one message into multiple tickets when multiple tasks are present.
- Supports manual ticket creation, editing, deletion, search, filter, sort, and drag-and-drop status updates.
- Provides private `My Tasks` boards for each signed-in user.
- Supports organization workspaces with members, roles, project boards, and Slack channel-to-board mapping.
- Shows organization/project tickets based on the current user's role and board membership.
- Uses Supabase Realtime so new tickets can appear without refreshing the whole app.
- Uses Redis + ARQ workers so Slack webhooks respond quickly while AI processing happens in the background.
- Supports hosted Gemini models and local Ollama models through environment configuration.
- Includes PWA metadata so the app can be installed from mobile browsers.

## App flow

```text
Slack message
  ↓
FastAPI Slack webhook
  ↓
Signature check, duplicate check, empty-message filtering
  ↓
Redis / ARQ background job
  ↳ Temporary failures: retry after 5s, then 15s; stop after 3 attempts
  ↓
Slack user + channel + organization context resolution
  ↓
AI triage model
  ↓
Structured task JSON
  ↓
Ticket factory
  ↓
Supabase tickets table
  ↓
React Kanban board + Supabase Realtime updates
```

Slack does not send messages through the frontend. Slack talks directly to the
FastAPI backend. The frontend only reads the resulting tickets and lets users
manage them.

## Main features

### Personal board

Each authenticated user gets a private Kanban board with three columns:

- `Pending`
- `In Progress`
- `Completed`

Tickets can be created manually or generated from Slack. Users can update the
ticket details, delete tickets, and drag tickets between columns.
Ticket titles open details by mouse or keyboard; separate drag handles move
cards. Network failures show an error with a retry action instead of an empty
board. Personal and organization lists load all result pages.

### Organization board

Organizations add a team layer on top of personal tasks.

- Managers can create organizations and project boards.
- Members can be invited through the app.
- Invitation acceptance verifies the signed-in user's email and identity before
  a backend-only database function adds membership.
- Project boards can be linked to Slack channels.
- Organization tickets can show which project board they belong to.
- Members see the tickets for boards they are part of.
- Assigned users update their own task status from `My Tasks`; the organization view reflects that progress.

### Slack integration

Slack is connected with OAuth and verified webhooks.

The backend handles:

- OAuth connect/reconnect/disconnect
- Slack event signature verification
- bot-message and duplicate-event filtering
- public channel auto-join when scopes allow it
- private channel invite detection
- Slack display-name and channel-name resolution
- per-user AI rate limiting
- project-board routing through Slack channel IDs
- atomic ticket-batch writes and completed-delivery replay protection

The worker retries temporary network failures, HTTP 408/429/5xx responses and
selected temporary database errors after 5 seconds, then 15 seconds, with three
attempts total. Invalid messages, permission/credential errors and malformed
model output remain terminal. Investigate deliveries that exhaust retries;
there is no automatic requeue beyond this limit. Atomic batch writes protect
committed tickets when a delivery runs again.

### AI triage

The AI layer receives cleaned Slack text and returns strict structured task
data. The active model provider is selected from `backend/.env`.

Supported providers:

- `gemini`
- `ollama`

## Tech stack

Frontend:

- React
- TypeScript
- Vite
- Tailwind CSS
- Shadcn-style components
- dnd-kit
- Supabase JS client

Backend:

- Python 3.11+
- FastAPI
- Pydantic v2
- Supabase Python client
- Redis
- ARQ workers
- Slack OAuth + Events API

Infrastructure:

- Supabase Auth
- Supabase Postgres
- Supabase Realtime
- Redis for queues, rate limits, OAuth state, and short-lived invitations
- ngrok or Cloudflare Tunnel for local webhook testing
- Vercel-ready frontend

## Project structure

```text
kanbanticket/
├── frontend/                  # React app
│   ├── public/                # PWA assets, icons, manifest, service worker
│   └── src/
│       ├── api/               # API clients
│       ├── auth/              # Supabase auth context and guards
│       ├── components/        # UI components
│       ├── hooks/             # Page and feature hooks
│       ├── integrations/      # Slack frontend integration helpers
│       └── pages/             # Landing, auth, dashboard, org, settings pages
├── backend/                   # FastAPI app
│   ├── app/
│   │   ├── auth/              # Supabase JWT auth
│   │   ├── database/          # Supabase repositories
│   │   ├── integrations/      # Slack integration
│   │   ├── organizations/     # Organization APIs and repositories
│   │   ├── redis/             # Redis helpers
│   │   ├── routes/            # General API routes
│   │   ├── services/          # AI providers and ticket factory
│   │   └── workers/           # ARQ worker
│   └── tests/                 # Backend tests
├── supabase/migrations/       # Database schema and RLS
├── scripts/                   # Local startup scripts
└── README.md
```

Local `docs/`, `.runtime/`, `.playwright-cli/`, `playwright/` and
`output/playwright/` directories are ignored by Git. Audit reports and browser
verification artifacts stored there remain local.

## Environment variables

Create these files locally. Do not commit real secrets.

### `frontend/.env`

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your_supabase_publishable_key
```

### `backend/.env`

```env
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

REDIS_URL=redis://127.0.0.1:6379/0

AI_MODEL_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-3.1-flash-lite

SLACK_CLIENT_ID=your_slack_client_id
SLACK_CLIENT_SECRET=your_slack_client_secret
SLACK_SIGNING_SECRET=your_slack_signing_secret
SLACK_REDIRECT_URI=https://your-public-backend-url/api/integrations/slack/callback
SLACK_FRONTEND_RETURN_URL=http://localhost:5173/settings
INTEGRATION_ENCRYPTION_KEY=your_fernet_key

SLACK_AI_RATE_LIMIT_REQUESTS=10
SLACK_AI_RATE_LIMIT_WINDOW_SECONDS=60
```

Use `AI_MODEL_PROVIDER=gemini` for hosted Gemini. Use
`AI_MODEL_PROVIDER=ollama` when running a local Ollama model.

When using both local and hosted frontends, list every exact frontend origin in
`FRONTEND_ORIGINS`, separated by commas (for example, append
`,https://kanban-kaii.vercel.app` to the local origins above). Restart FastAPI after
changing this value. An `OPTIONS 400 Disallowed CORS origin` response means the
browser's origin is missing from this list; the ngrok backend URL is not the
frontend origin.

## Running locally

### 1. Clone and install frontend dependencies

```powershell
git clone <your-repo-url>
cd kanbanticket
cd frontend
npm install
```

Start the frontend:

```powershell
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

### 2. Install backend dependencies

Open another terminal:

```powershell
cd D:\kanbanticket\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use Python 3.11 or newer. If an old virtual environment points to a missing
Python installation, create `backend/.venv` with the current Python and install
the requirements there instead.

### 3. Start Redis

Redis is required for Slack queueing, OAuth state, invitations, and rate
limiting.

Start Docker Desktop. Create the Redis container once:

```powershell
docker run --name kanbankaii-redis --restart unless-stopped -v kanbankaii-redis-data:/data -p 127.0.0.1:6379:6379 -d redis:7-alpine redis-server --appendonly yes
```

The launcher starts the container on later runs and checks for `PONG`.
Redis 7 or newer is required for invitation index expiry. The named volume
preserves Redis data across container replacement; AOF enables persistence.
If an existing container publishes on all interfaces, recreate it with the
loopback binding above while preserving its existing `/data` volume. Do not
delete that volume. The launcher refuses unsafe bindings before startup.

### 4. Start the ARQ worker

From the repository root, this single command starts Redis, FastAPI and the
ARQ worker:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local-server.ps1

Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -match '^(python|pythonw|uvicorn|arq|ngrok|cloudflared)\.exe$' -and
    $_.CommandLine -match 'app\.main:app|app\.workers\.slack_worker\.WorkerSettings|ngrok.*http.*8000|cloudflared.*tunnel.*run'
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

docker stop kanbankaii-redis
```

The worker processes queued Slack events and calls the configured AI provider.
The launcher selects the first working Python environment containing Uvicorn
and ARQ from `backend/.venv`, `backend/venv`, then `.runtime/audit-venv`.
It never deletes containers or volumes and does not start or require Ollama.
Configure `backend/.env` before starting services.

API docs: http://127.0.0.1:8000/docs . The frontend starts separately with
`npm run dev` from `frontend/`.

### 5. Choose an AI provider

For Gemini, set this in `backend/.env`:

```env
AI_MODEL_PROVIDER=gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-3.1-flash-lite
```

Then set:

```env
AI_MODEL_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
```

### 6. Expose the backend for Slack

Slack needs a public HTTPS URL for OAuth and Event Subscriptions.

To start the backend services with ngrok, add `-UseNgrok` to the same launcher
command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local-server.ps1 -UseNgrok
```

ngrok defaults to `C:\ngrok\ngrok.exe`; use `-NgrokPath` for another location.
The launcher verifies the ARQ heartbeat before starting the tunnel. A real worker
failure stops startup and prints the last check output; check the worker terminal
for the cause. Successful ARQ messages on stderr are handled correctly in Windows
PowerShell. Re-running the command reuses existing services.
For an existing Cloudflare Tunnel, use `-TunnelName your-tunnel` instead of
`-UseNgrok`, with `-CloudflaredPath` if needed. Without either option, the
backend stays local.

Set these Slack URLs using your ngrok domain:

```text
OAuth callback:
https://your-ngrok-domain.ngrok-free.dev/api/integrations/slack/callback

Event Subscriptions:
https://your-ngrok-domain.ngrok-free.dev/api/webhooks/slack/events
```

Also update `SLACK_REDIRECT_URI` in `backend/.env` to match the OAuth callback
exactly.

## Supabase setup

1. Create a Supabase project.
2. Add the frontend Supabase URL and publishable key to `frontend/.env`.
3. Add the backend Supabase URL and service-role key to `backend/.env`.
4. For a new database, run SQL files from `supabase/migrations/` in filename
   order. For an existing database, inspect its schema and apply only missing
   migrations; do not blindly replay historical SQL.
5. Enable Supabase Realtime for the tickets table if required by the migration notes.
6. Configure Auth redirect URLs for your local and deployed frontend URLs.

## Slack setup

In your Slack app configuration:

1. Add the OAuth callback URL.
2. Add the Event Subscriptions request URL.
3. Add the required bot scopes.
4. Install the app to your workspace.
5. Connect Slack from KanbanKaii Settings or Organization settings.
6. Invite the app to private channels manually when needed.

Public channels can be auto-joined if the app has the correct scope. Private
channels must be invited from Slack.

## Useful checks

Frontend:

```powershell
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

Backend:

```powershell
cd backend
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Use `.venv\Scripts\python.exe` instead when that is your environment. From
the repository root, the local audit environment can run the same suite with
`.\.runtime\audit-venv\Scripts\python.exe -m unittest discover -s backend/tests -v`.
Migration source tests resolve SQL from the repository-root `supabase/migrations/`.

Frontend DOM regressions use jsdom and require Node 22.22.2, Node 24.15.0 or newer
within those major versions, or Node 26+. Run `npm ci` before the frontend checks.
They cover connection-error recovery, native keyboard controls, card text
contrast and associated filter labels. Browser verification remains a separate
check; intermittent Escape-to-close behavior in the ticket dialog remains open.

With Docker running, verify all migrations and rollback SQL in a separate local
test database (port 55432, project `kanbankaii-audit`):

```powershell
.\scripts\test-database.ps1
```

This command uses the pinned Supabase CLI through npx, applies repository
migrations to its isolated database and runs invitation, atomic rollback/replay,
retention and authenticated owner/lead/member/outsider RLS tests. It stops and
removes the test database afterward; no hosted credentials are used. The first
run downloads the CLI and database image. GitHub Actions runs the same gate,
backend tests, a real Redis queue-loss test, frontend checks and launcher tests.

The worker reconciles up to 100 pending Slack deliveries older than 15 minutes
at startup and every five minutes. Stable job IDs preserve queued/in-flight job
deduplication, and the database commit marker prevents replayed ticket inserts.
Permanent failures and exhausted retries remain terminal. If Redis and database
failure recording fail together, an unrecorded terminal attempt can be recovered
again; manual investigation is needed for such repeated failures.

The launcher waits for the worker heartbeat before reporting readiness. For a
manual check, run `python -m arq --check app.workers.slack_worker.WorkerSettings`
from `backend` using its Python environment. This proves recent worker polling;
it does not prove Slack or model availability. Production still requires process
supervision and monitoring of pending deliveries.

Health endpoints:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/health/redis
```

## Deployment notes

The current learning deployment model is:

- Vercel hosts the React frontend.
- Supabase hosts Auth, Postgres, RLS, and Realtime.
- FastAPI, Redis, and the ARQ worker can run locally during development.
- ngrok or another tunnel exposes the local backend to Slack.
- Hosted Gemini can replace local Ollama when you do not want to run a model on your machine.

For production, the backend, Redis, and worker should run on an always-on server
instead of a personal machine.

The backend requires migrations through `202610180029`. Pause the backend
and worker, apply migrations in filename order, deploy the matching backend,
then restart both processes. The invitation RPC and Slack batch writes require
these migrations. Migration `202610180029` retains pending Slack deliveries for
recovery and indexes the bounded recovery query. On a local Supabase database, run
`psql <local-database-url> -v ON_ERROR_STOP=1 -f supabase/tests/audit_regressions.sql`
to check invitation privileges, rollback and replay behavior; test data rolls back.
The launcher does not apply migrations. The current development database has
these migrations; schema and function privilege checks pass. Hosted write checks remain unavailable through the agent's read-only connection.
Use the isolated local database gate described above before deploying migrations.

## Security notes

- Never commit `.env` files.
- Keep Supabase service-role keys backend-only.
- Frontend API calls use Supabase JWTs.
- Slack webhook signatures are verified.
- Slack tokens are encrypted before storage.
- OAuth state and organization invitations are temporary Redis records.
- AI calls are rate-limited per connected Slack user.
- The triage endpoint requires a Supabase Bearer token whose user matches
  `owner_id`; exhausted limits return `429`, and limiter failures return `503`.
- Invitation membership writes use a service-role-only RPC with verified user
  identity; browser roles cannot call it directly.
- Slack ticket batches and delivery completion commit in one database
  transaction; a committed delivery cannot insert its tickets again.
- Invitation indexes retain the longest outstanding invitation lifetime.
- Local Redis ports must bind to loopback. Use private networking, ACLs and TLS
  for remote Redis; never expose an unauthenticated queue to the public network.
