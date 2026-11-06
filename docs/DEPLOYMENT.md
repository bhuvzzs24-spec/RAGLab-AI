# Reproducible setup and hosting

## Native setup

Use Node 20+ (CI: Node 20) and Python 3.12 or 3.13. The verified local environment is Python 3.13 on Apple Silicon. Install from the root:

```sh
npm ci
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt -c apps/api/requirements.lock.txt
cp .env.example apps/web/.env.local
python -m uvicorn main:app --app-dir apps/api --host 127.0.0.1 --port 8000
# Second terminal, same root:
npm run build
npm run start -w apps/web
```

The committed npm lock and Python constraints record the actual tested versions. Binary Torch/FAISS wheels are platform-dependent; unsupported Python/architectures need compatible wheels, not a claim of identical binaries. The CI workflow validates Linux Python 3.12 as well. The first embedding request downloads the two pinned model revisions; allow several GB of disk and RAM for Python dependencies, models and indexes. No GPU is required. Keep runtime data on a local disk, not cloud-only placeholder files.

Python uses exported environment variables, not Next.js `.env.local`. Set an absolute `RAGLAB_DATA_DIR` and `HF_HOME` for stable storage. After the first successful model download, `HF_HUB_OFFLINE=1` enables a fully local retrieval demo. `.env` and private artifacts are ignored. Keys must never use a `NEXT_PUBLIC_` prefix. Changing API_URL requires rebuilding production Next.js because proxy rewrites are compiled.

## Docker Compose

```sh
cp .env.example .env
# Optional: fill in provider variables locally. No key is needed for retrieval.
docker compose up --build
# Open http://localhost:3000
# Stop while retaining data:
docker compose down
```

The API runs as an unprivileged user and uses persistent named volumes for SQLite/indexes and model weights. The web waits for API health. The proxy build uses `http://api:8000`; it does not send that hostname to a browser. Ports bind only to localhost. Do not use `down -v` if data must be retained. Docker was unavailable on the implementation machine: container execution is **NOT TESTED**, not a verified deployment. The native application is tested independently.

## Hosting choices and boundaries

For a faculty demo, run both processes locally or on a single Linux VM/container host with persistent disk, adequate RAM, TLS and an access-control reverse proxy. Keep a single API worker. Back up the whole runtime directory consistently while the service is stopped, including SQLite, indexes and vectors. The application stores extracted source text, not original PDF binaries; source highlights refer to extracted pages.

A separately hosted Next.js frontend can proxy to a long-lived Python backend. Configure the backend URL at frontend build time. A hosted backend needs durable disk for SQLite/FAISS/model cache; an ephemeral filesystem loses state. The current application is a local research tool without multi-user authentication, quotas or tenant isolation; add those before sharing it on the public internet.

Vercel is a possible frontend host. This repository does **not** automatically run its heavy sentence-transformers models, persistent SQLite, FAISS artifacts or in-process benchmark executors on Vercel Functions. Request-bound serverless lifetimes and limits require a separate durable worker/backend design. Moving to PostgreSQL/object storage and an external job queue is a future architecture change, not an implemented capability.

Primary deployment references (checked 2026-11-05): [Next.js self-hosting](https://nextjs.org/docs/app/guides/self-hosting), [FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/), [Docker Compose health dependencies](https://docs.docker.com/compose/how-tos/startup-order/), [Vercel Functions limits](https://vercel.com/docs/functions/limitations). No cloud deployment or paid hosting resource was created.

## Checks

```sh
pytest apps/api/tests -q
npm run build
npm run typecheck
python apps/api/scripts/smoke_benchmark.py --repeat --output work/benchmark-evidence.json
python apps/api/scripts/smoke_adaptive.py --output work/adaptive-evidence.json --pdf work/adaptive-report.pdf
npx playwright install chromium
RAGLAB_PYTHON="$PWD/.venv/bin/python" npm run test:e2e
python scripts/audit_staged.py
```

Real smoke scripts use disposable source databases, genuine pinned models and FAISS. Browser tests own production Next.js and API servers; stop existing processes on 3000/8000 first and never point browser test storage at private research data. CI offers manual `real_benchmark=true` to run both real-model smokes and desktop/mobile browser flows.

## Upgrade and troubleshooting (research/editorial edition)

Stop the single API process and back up the complete runtime directory before upgrading. Additive review tables are created at startup; historical snapshots and generated indexes remain intact. Existing approvals have no invented historical events. Use the original pinned model cache and a stable absolute RAGLAB_DATA_DIR outside cloud-only placeholder storage.

If ports 3000/8000 are occupied, identify the owner before stopping anything; the E2E suite deliberately refuses to reuse an unknown server. It owns isolated test servers and must never use private runtime data. After a production rebuild, start Next.js again. Next.js API_URL rewrites are compiled at build time.

A 429 upload means two PDF parsers are active; retry after completion. A PDF resource-limit error means split/simplify the file. A 429 benchmark means three active jobs already exist, including resumed work. Cancel/finish one; completed results remain available. Review 409 responses mean reload the latest dataset/answer-review revision before resubmitting. A model-list probe does not prove generation access; inspect actual grounded answers separately.

Browser verification includes locked `@axe-core/playwright` checks, keyboard focus, reduced motion, mobile bounds, the native-scroll tour, explicit review events and actual model retrieval. Automated checks are not a certification of complete WCAG conformance or a penetration test. The native-code PDF worker limits resources but is not a general security sandbox.
