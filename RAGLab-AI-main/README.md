# RAGLab AI - Adaptive RAG Benchmarking & Optimization

**Research/editorial edition (2026-11-06):** explicit evidence decisions with append-only history, backend approval invalidation, honest provider probes, optional attributed human answer evaluation, bounded PDF ingestion, paired run comparisons, and a redesigned orchid/eggplant/orange studio. The optional cinematic intro and native-scroll Pipeline Tour use conceptual motion or actual stored data with clear labels. All previous phases and Git history remain.

- [Research upgrade: workflow, security bounds and honest limitations](docs/RESEARCH_UPGRADE.md)
- [Current verification results](docs/RESEARCH_VERIFICATION.md)


**Phase 4 extends the existing Phases 1-3.** Validation-only automatic search, configurable accuracy/latency objectives, Pareto analysis, frozen one-config held-out evaluation, split-aware evidence review, uncertainty/repeatability reporting and actual PDF/CSV/JSON reports are implemented. All supplied sample labels remain unreviewed; missing LLM credentials produce honest retrieval-only behavior.

- [Phase 4 workflow and API](docs/PHASE4.md)
- [Final verification evidence](docs/PHASE4_VERIFICATION.md)
- [Reproducible native setup, Compose and hosting boundaries](docs/DEPLOYMENT.md)
- [Faculty demonstration guide](docs/FACULTY_DEMO.md)
- [IEEE mini-project report guide](docs/IEEE_REPORT_GUIDE.md)


**Phases 1–3 are included in this repository.** Phase 3 adds CSV/JSON datasets, explicit human-review attestations and source evidence, repeatable 18-configuration benchmarks, real Precision@k/Recall@k/MRR and timing measurements, run recovery, measured charts/heatmaps, ranked comparisons, an explainable optimizer, and CSV/JSON exports. Retrieval benchmarking needs no external API key. The included CC0 judgments are unreviewed examples, and all resulting sample recommendations are provisional.

- [Phase 3 workflow and API](docs/PHASE3.md)
- [Research methodology and optimizer formulas](docs/METHODOLOGY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Audit and verification evidence](docs/VERIFICATION.md)


A local-first RAG benchmarking and optimization studio for university research. Phase 1's nine pages, upload/preview library, three chunkers, experiment registry, measured comparisons, reports, preferences, and colorful responsive UI are retained. Phase 2 adds two pinned local embedding models, persistent FAISS indexes, indexing jobs, actual PCA plots, side-by-side retrieval, original-source highlighting, and optional grounded LLM generation.

## Setup

Requires Node.js 20+, Python 3.12–3.13, and internet for package installation and the first model downloads. Allow several GB for Torch, both embedding models, and index storage.

```sh
npm ci
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt -c apps/api/requirements.lock.txt
cp .env.example apps/web/.env.local
```

From the repository root, start FastAPI:

```sh
source .venv/bin/activate
python -m uvicorn main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
npm run dev
```

Open http://localhost:3000. API documentation: http://localhost:8000/docs. Production: `npm run build`, then `npm run start -w apps/web`.

Next.js proxies `/api/*` to `API_URL` (default `http://127.0.0.1:8000`). Python does **not** read Next.js's `.env.local`: export backend variables in the API terminal. To load the root example manually after filling it in, use `set -a; source .env; set +a` with a local `.env` copy. Never commit credentials. The root `.env` and frontend `.env.local` are ignored.

SQLite lives at `./data/raglab.sqlite3`, relative to the API working directory; use a stable working directory or an absolute `RAGLAB_DATA_DIR`. FAISS binaries and normalized vectors live under `data/indexes/<index-id>/`. `package-lock.json` locks frontend dependencies; `apps/api/requirements.lock.txt` constrains the tested Python dependency versions; Linux Python 3.12 is checked in CI. Binary wheel availability is platform-dependent.

## First retrieval and RAG run

1. Upload a PDF, UTF-8 TXT, or Markdown document in Documents. Original CC0 samples are in `apps/api/samples/`. Previews preserve extracted pages. Phase 1 Chunking Lab still previews/saves exact chunk boundaries without requiring an index.
2. Open Embeddings or the index builder in RAG Playground. Select one or more documents, chunking method, word budget/overlap or semantic threshold, and MiniLM or BGE Small. Build the configuration.
3. Watch actual job phase and processed-vector progress. Cancellation is cooperative between model calls/batches; downloads and an in-progress inference call cannot safely be interrupted. Navigate away and return without losing the job.
4. Select a ready index. Adjust top-k and minimum cosine, ask a question, and inspect similarity scores, measured query/search timings, chunk positions, pages, and original source highlights.
5. Build another configuration and enable comparison to retrieve against both side-by-side. Each uses its own model, query formatting, index, provenance, and optional generated answer. No artificial search delays or fabricated steps are used.
6. With no LLM credentials, retrieval works normally and generation explicitly reports that it is unconfigured. Uncheck generation for retrieval only. An optional expected phrase performs a case-insensitive exact substring hit check, not a semantic quality score.
7. Inspect actual PCA vectors, vector counts, unit norms, index size, build time, revision, and cache reuse in Embeddings. Export JSON from Reports, including Phase 1 experiments and up to 500 recent retrieval/answer records. Preferences persist in Settings.

## Local embedding models

| ID | Model | Dimensions | Model token limit | Retrieval query formatting |
|---|---|---:|---:|---|
| `minilm` | sentence-transformers/all-MiniLM-L6-v2 | 384 | 256 | Plain question |
| `bge-small` | BAAI/bge-small-en-v1.5 | 384 | 512 | `Represent this sentence for searching relevant passages: ` + question |

Documents receive no prefix. Both outputs are L2-normalized and searched with exact inner product, equivalent to cosine for normalized vectors. Both run on CPU locally. Prompt application is explicit, so model defaults cannot double-prefix a query. Overlong questions are rejected with a helpful error instead of silently truncated.

Pinned revisions:

- MiniLM: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` (Apache-2.0).
- BGE Small: `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` (MIT).

The UI's chunk budgets remain whitespace-delimited **words**, preserving Phase 1 behavior. During indexing, actual tokenizer offsets split oversized chunks into model-sized subpassages. Each stores its parent chunk position, part, original character span, page numbers, word count, model token count, source name, and document ID. No document text is silently truncated for retrieval embeddings. Semantic boundary comparisons use normalized length-weighted pooling if a sentence unit exceeds the model limit. Whitespace between spans is not indexed as content.

Formatting and limits follow the [BGE model card](https://huggingface.co/BAAI/bge-small-en-v1.5), [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), and [SentenceTransformer API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html).

## Persistence and indexing lifecycle

- An index cache key includes sorted document IDs/content hashes, effective chunking settings, pinned model revision, formatting version, and chunker version. Identical ready configurations are reused after verifying artifact checksums.
- Passage embedding cache keys include exact text, model ID/revision, and formatting version. Rebuilds write a new version and reuse valid cached vectors. Old ready indexes remain searchable.
- SQLite records durable jobs (`queued`, `running`, `ready`, `cancelled`, `failed`, `invalidated`), phases, counters, errors, metadata, retrieval snapshots, and generated-answer results. A single indexing thread limits memory pressure. Run one API worker for this local architecture.
- FAISS runs in an isolated subprocess to avoid Torch/FAISS OpenMP conflicts on macOS. Indexing writes a real `index.faiss` and `vectors.npy`; queries load the persisted FAISS index and embed only the query. Process startup, index validation/load, and cold-model overhead are included in timing.
- Only a complete index and metadata transaction becomes `ready`. Missing/corrupted artifacts are rejected with rebuild guidance. Restarted in-flight jobs are marked failed rather than falsely completed; manually rebuild them.
- Document deletion preserves Phase 1 experiment cascade behavior and additionally invalidates affected collection indexes, cancels their work, removes their files/passages/retrievals/answers, and prevents stale searches. Cached numeric embedding vectors may remain in the local deduplication cache; no raw source text is stored there.
- Visualization computes deterministic PCA on up to 500 actual vectors spread across the index. It reports retained variance and sampling. Different indexes have independent projection axes. Similarity and visual proximity are not correctness/confidence measurements.

## Optional grounded answer generation

Configure an OpenAI-compatible Chat Completions provider in the **server** environment before starting FastAPI:

```sh
export LLM_API_BASE='https://api.openai.com/v1'
export LLM_MODEL='your-provider-model-id'
export LLM_API_KEY='your-key'
```

`OPENAI_API_KEY` is accepted as a fallback. For an already installed, trusted local compatible provider, configure its `/v1` base, installed model, and explicitly set `LLM_REQUIRE_KEY=false`. No LLM is bundled. Do not put keys in `NEXT_PUBLIC_*`, browser preferences, SQLite, reports, or source code.

The provider must support `/chat/completions`, system/user messages, `response_format: {"type":"json_object"}`, and `max_completion_tokens`. The adapter follows the [Chat Completions API reference](https://developers.openai.com/api/reference/resources/chat). Configure a compatible model rather than assuming every provider/model implements these fields.

Generation uses only the persisted retrieval snapshot. The prompt treats source text as untrusted data, requires an explicit insufficient-context decision, and requests claim-level source IDs plus verbatim supporting quotes. Context is bounded to the first 4,000 characters of each selected passage, at most 20 passages. Source IDs and quote substrings are validated against exactly the text sent to the provider. Invalid/missing citations, invalid JSON, and incomplete provider responses produce **no generated answer**. Click citations to inspect source offsets and highlighted quotes.

If no passage passes the configured similarity threshold, or if the provider reports insufficient support, the answer is: “I don't have enough context in the selected sources to answer that.” Missing credentials, timeout, invalid credentials, quota, network failures, and unsupported-provider responses are explicit states that leave retrieved evidence available. Provider response bodies and credentials are not included in errors. This validates quote presence and provenance, not the semantic truth of each claim; human review remains necessary. An LLM can still misinterpret genuine quotes.

Enabling generation sends the question and retrieved excerpts to the configured provider. Retrieval and embedding stay local. Disabling generation performs no LLM request.

## API additions

| Method | Path | Purpose |
|---|---|---|
| GET | `/models`, `/provider` | Pinned registry / sanitized provider status |
| GET / POST | `/indexes` | List jobs/indexes / queue a collection build |
| GET | `/indexes/{id}` | Durable progress, parameters, revision, statistics |
| POST | `/indexes/{id}/cancel`, `/indexes/{id}/rebuild` | Cooperative cancellation / versioned rebuild |
| GET | `/indexes/{id}/visualization` | Actual sampled PCA |
| GET | `/indexes/{id}/chunks/{ordinal}/source` | Original extracted pages with highlight coordinates |
| POST | `/retrieve` | Query embedding + persisted-index search |
| POST | `/answers` | Generate from a server-stored retrieval ID |
| POST | `/rag` | Retrieve then attempt grounded generation |
| GET | `/pipeline/report` | Index metadata and recent retrieval/answer history |

Phase 1 `/health`, `/documents`, `/documents/{id}`, `/chunks/preview`, `/experiments`, `/search`, and `/settings` remain. Legacy `/search` now builds/reuses a persistent index from the saved experiment configuration (MiniLM by default; `EMBEDDING_MODEL` can select either registered model) and keeps its extractive response contract.

Example:

```sh
curl -X POST http://localhost:8000/indexes \
  -H 'Content-Type: application/json' \
  -d '{"document_ids":["YOUR_DOCUMENT_ID"],"model_id":"bge-small","strategy":"sentence","budget":120,"overlap":0}'
# Poll /indexes/RETURNED_INDEX_ID until ready, then:
curl -X POST http://localhost:8000/rag \
  -H 'Content-Type: application/json' \
  -d '{"index_id":"READY_INDEX_ID","query":"What does the library lend?","top_k":3,"min_score":0.2}'
```

## Verification

```sh
source .venv/bin/activate
pytest apps/api/tests -q
npm run typecheck
npm run build
# Real model integration: downloads weights on first run.
mkdir -p work
python apps/api/scripts/smoke_pipeline.py --output work/real-pipeline-results.json
# After configuring a provider: opt in to six real API requests and grounded Q&A assertions.
python apps/api/scripts/smoke_pipeline.py --with-llm --output work/live-qa-results.json
```

The deterministic suite uses clearly identified controlled embedding/provider fixtures to test boundary behavior and real FAISS. `smoke_pipeline.py` uses **both real models**, all three chunkers, a generated two-page PDF and original CC0 notes, fresh Engine/persisted FAISS loading, query relevance, source/page mapping, rebuild cache reuse, and actual PCA. It never supplies a fabricated generated answer. Without LLM environment credentials it verifies the honest `provider_unconfigured` state. See `docs/VERIFICATION.md` for current execution evidence and the live-provider limitation.

## Architecture and limits

```text
apps/api/main.py                  FastAPI, Phase 1, pipeline routing and SQLite
apps/api/chunking.py              original three chunkers
apps/api/embeddings.py            pinned models, formatting, tokenizer spans
apps/api/pipeline.py              durable jobs, vector cache, retrieval, provenance/PCA
apps/api/vector_search.py         isolated persisted FAISS build/search
apps/api/generation.py            grounded provider adapter and citation validation
apps/api/tests/                   regression and API boundary tests
apps/api/scripts/smoke_pipeline.py real-model integration smoke
apps/web/components/              shared studio, index builder, playground, source dialog, charts
```

Single-user local research software: loopback only, no authentication/tenancy, one indexing worker, no distributed queue, no OCR, and no automated answer-quality benchmark. Source PDFs/TXT/MD are validated (10 MB, 500 PDF pages, 2 million extracted characters), normalized display filenames never become storage paths, and SQL is parameterized. Original binaries are not retained; extracted source text/pages are. Scanned PDFs require OCR elsewhere. A collection is limited to 50 documents and 10,000 indexed passages. Add authentication, quotas, isolated workers and managed persistence before multi-user deployment. Empty workspaces show empty states rather than fake analytics.


## Phase 3 checks and browser smoke tests

```sh
pytest apps/api/tests -q
npm run build
npm run typecheck
python apps/api/scripts/smoke_benchmark.py --repeat --output work/benchmark-evidence.json
npx playwright install chromium
# Build first. The suite owns disposable local API/frontend servers and uses real models.
RAGLAB_PYTHON="$PWD/.venv/bin/python" npm run test:e2e
```

Browser tests cover desktop/mobile dataset review validation, all 18 real configurations, cancellation/resume, measured heatmaps/filters/optimization/CSV export, and preservation of Phase 2 retrieval/source highlighting. They use `work/e2e-data` and never require LLM credentials. `HF_HOME` can point to an existing model cache. Set `RAGLAB_E2E_DATA_DIR` for another disposable location. Normal API development should still use one worker.

GitHub Actions runs backend tests, the production build and TypeScript on pushes/PRs. Its manual `real_benchmark` option additionally runs real local-model benchmarking and browser smoke tests. The environment example contains placeholders only. Do not commit credentials, runtime databases, private documents, generated vectors/indexes, model weights, virtual environments or build/test caches.

### Continuous cinematic opening

At `/`, the licensed Halftone Loop draws RAGLab's own headings, then normal scrolling reveals the real workspace on the same page. Enter Workspace scrolls to `#workspace`; `/overview` remains a direct dashboard entry. The overlapping blush/cream panel expands naturally, preserves one Studio instance and releases the Canvas while offscreen. [Source attribution and customization notes](docs/THREEUI.md).
