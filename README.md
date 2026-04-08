# AegisHealth

A robust federated learning framework for privacy-preserving health anomaly detection using non-IID data.

## Architecture

- **Presentation Tier**: Next.js web application with RBAC (Server + Client views)
- **Application Tier**: FastAPI REST API + gRPC Central Orchestrator + Headless Edge Agents
- **Data Tier**: Supabase (Auth, Postgres with RLS, Realtime)

## Tech Stack

| Layer       | Technology                                            |
|-------------|-------------------------------------------------------|
| Frontend    | Next.js 16, TypeScript, Tailwind CSS, shadcn/ui       |
| Backend API | Python 3.12+, FastAPI, gRPC (TLS)                     |
| ML          | PyTorch, Opacus (DP), TenSEAL (HE)              |
| Database    | Supabase (PostgreSQL)                                 |
| Dataset     | eICU Collaborative Research Database v2.0             |

## Project Structure

```
aegishealth/
├── backend/           # Python: FastAPI + gRPC orchestrator + edge agents
├── frontend/
│   ├── web/           # Next.js server dashboard
│   └── desktop/       # Electron client app
├── supabase/          # Database migrations
└── data/
    ├── eicu-collaborative-research-database-2.0/  # Raw eICU dataset
    └── raw/                                       # Per-client raw CSVs
        └── client_{id}/
            ├── patients.csv
            └── vitals.csv
```

## Setup

### 1. Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Run migration: Supabase Dashboard → SQL Editor → paste contents of `supabase/migrations/001_create_aegishealth_schema.sql` → Run (or use Supabase MCP `apply_migration`)
3. Copy your project URL, publishable key, and secret key (Settings → API)

### 2. Backend

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure `.env` (see `backend/.env.example`):

- **Supabase**: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`
- **gRPC port**: `GRPC_PORT` (default `50051`). Start the REST API with Uvicorn on port `8000` by default (`--port 8000`); if you use another port, set `NEXT_PUBLIC_API_URL` on the web app to match
- **gRPC TLS**: `GRPC_TLS_CERT` and `GRPC_TLS_KEY` (paths under `backend/`). If the files are missing, the server attempts to generate dev certificates under `backend/certs/`
- **Data**: `DATA_DIR` — root of the extracted eICU dataset (used by `split_eicu_by_client`; default points at the repo `data/eicu-...` folder)
- **Production CORS**: `CORS_ORIGINS` — comma-separated extra origins (local `localhost` / `127.0.0.1` dev origins are always allowed)

```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Web dashboard

```bash
cd frontend/web
cp .env.example .env.local
npm install
npm run dev
```

Set in `.env.local` (see `frontend/web/.env.example`):

- **Supabase**: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- **Backend REST API**: `NEXT_PUBLIC_API_URL` — base URL including `/api`, e.g. `http://localhost:8000/api` for local dev (must match where Uvicorn is reachable from the browser)
- **Optional**: `NEXT_PUBLIC_DESKTOP_APP_GITHUB_REPO` — enables the “Download Desktop App” link from the latest GitHub release

### 4. Desktop client (Electron)

The desktop shell loads the **client** dashboard from a URL; Supabase and API calls are made by that embedded web app using **its** `NEXT_PUBLIC_*` values.

```bash
cd frontend/desktop
cp .env.example .env
npm install
npm start
```

In `.env`, set `ELECTRON_APP_URL` if the client UI is not at the default `http://localhost:3000/dashboard/client` (required when packaging against a deployed web app).

### 5. Seed Users

1. **Server user**: Create in Supabase Dashboard (Auth > Users > Add User). The `handle_new_user` trigger creates a profile with role `server` by default. Set `full_name` in Table Editor → `profiles` if desired.

2. **Client users**: Log in as the server user, open the dashboard → Management tab → Register Client. This creates both the client (participating site) and its auth user in one step. No manual profile editing needed.

### Data Setup

Place the eICU dataset in `data/eicu-collaborative-research-database-2.0/`, then split it into per-client raw CSVs:

```bash
cd backend && source venv/bin/activate
python -m scripts.split_eicu_by_client
```

This creates `data/raw/client_{id}/patients.csv` and `vitals.csv` for each hospital. No separate preprocessing step is needed — agents preprocess their own data locally on startup.

In a real deployment, each hospital provides its own `patients.csv` and `vitals.csv` directly.

## Usage

You can run federated training in two ways:

### Option A: In-process simulation (quick test)

Runs the full FL loop in one process. Does not use the dashboard or edge agents.

```bash
cd backend
source venv/bin/activate
python -m scripts.run_simulation --num-clients 10 --rounds 50
```

### Option B: Dashboard with edge agents

Uses the web UI to create and monitor jobs. Edge agents run as separate processes and connect via gRPC.

1. **Start the backend** (if not already running):
   ```bash
   cd backend && source venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   ```

2. **Open the dashboard** at http://localhost:3000 and log in as the **server** user.

3. **Register clients**: Management tab → Register Client. Each client gets an ID (e.g. 1, 2, 3).

4. **Create a job**: Training Config → set hyperparameters → Create Job → Start.

5. **Start edge agents** (one terminal per client):
   ```bash
   cd backend && source venv/bin/activate
   python -m agents.agent --client-id 1 --server localhost:50051
   ```
   Each agent reads raw CSVs from `data/raw/client_{id}/` and preprocesses locally on startup. Use `--data-dir` to override the default path. Agents auto-discover the active job from the orchestrator.

6. **Client view**: Use the **desktop app**. It opens the web client dashboard in a native window and adds agent control (start/stop, file picker). For development:
   ```bash
   # Start the web app (if not already running)
   cd frontend/web && npm run dev

   # Start the desktop app
   cd frontend/desktop && npm install && npm start
   ```
   Log in as a client user to start the edge agent, view Agent Health, Privacy Budget, and Audit Logs.

### Deploy desktop app

```bash
cd frontend/desktop
npm run package   # Runs build:agent, then electron-forge package → e.g. out/AegisHealth-darwin-arm64/AegisHealth.app (macOS)
npm run make      # Runs build:agent, then installers (ZIP on darwin, plus Squirrel/Deb/Rpm per forge.config)
```

`package` and `make` both invoke `build:agent` (PyInstaller agent under `backend/dist/agent`, bundled as an `extraResource`). Run `npm run build:agent` alone only when you want the agent binary without packaging.

**Production URL**: When packaging for production, set `ELECTRON_APP_URL` to your deployed web app URL so the desktop app loads the correct dashboard:
```bash
ELECTRON_APP_URL=https://your-app.vercel.app/dashboard/client npm run package
```

**Client download from web**: Set `NEXT_PUBLIC_DESKTOP_APP_GITHUB_REPO=owner/repo` in the web app env. Create a GitHub release and upload the ZIP from `frontend/desktop/out/make/zip/darwin/<arch>/` (exact folder and filename depend on platform and `version` in `frontend/desktop/package.json`). Signed-in clients see a "Download Desktop App" button that fetches the latest release.

## Key Algorithms

- **FedProx**: Federated optimization with proximal term for non-IID robustness
- **LSTM**: Stacked Long Short-Term Memory network for temporal anomaly detection
- **Differential Privacy**: Per-sample gradient clipping + Gaussian noise (Opacus)

## Released Models

When a training job completes, the final global model is exported and uploaded to Supabase Storage:

- **Bucket**: `models`
- **Artifacts per job**:
  - PyTorch state dict: `jobs/{job_id}/model.pt`
  - ONNX export: `jobs/{job_id}/model.onnx`
- Paths are stored on the `training_jobs` row as `model_path_pt` and `model_path_onnx`.

You can download released models from the **Server dashboard** in the job detail card:

- Use **PyTorch** artifacts for further training or direct use with the original codebase.
- Use **ONNX** artifacts to run inference in other runtimes that support ONNX.

## Dataset

Uses the [eICU Collaborative Research Database v2.0](https://physionet.org/content/eicu-crd/2.0/) containing ~200K ICU patient stays from 208 hospitals. The anomaly detection task predicts critical events from time-series vital signs. Place the extracted dataset in `data/eicu-collaborative-research-database-2.0/` and run `split_eicu_by_client` to generate per-client raw CSVs.
