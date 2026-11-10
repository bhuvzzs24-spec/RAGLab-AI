# Local Setup and Backend Verification Guide

## 1. Overview

RAGLab is a local research application for document ingestion, chunking,
embedding generation, vector indexing, retrieval and retrieval evaluation.

The backend uses:

- FastAPI for HTTP APIs.
- Pydantic for request validation.
- SQLite for persistent application records.
- PyMuPDF for PDF text extraction.
- Sentence Transformers for local text embeddings.
- FAISS for vector similarity search.
- NumPy for vector storage and processing.

The frontend uses Next.js and TypeScript. The backend can be run and tested
independently of the frontend.

For overall architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).
For hosting and deployment, see [DEPLOYMENT.md](DEPLOYMENT.md).

## 2. Backend folder structure

Important backend files:

| File | Responsibility |
|---|---|
| `apps/api/main.py` | FastAPI application, routes, SQLite setup and service wiring |
| `apps/api/ingestion.py` | Filename handling and PDF/TXT/Markdown extraction |
| `apps/api/pdf_extract.py` | Bounded PDF extraction worker |
| `apps/api/boundaries.py` | Request-size and browser-origin boundaries |
| `apps/api/chunking.py` | Fixed, sentence and semantic chunking |
| `apps/api/embeddings.py` | Pinned embedding models and vector generation |
| `apps/api/vector_search.py` | FAISS index construction and search |
| `apps/api/pipeline.py` | Index lifecycle, caching, persistence and retrieval |
| `apps/api/tests/` | Backend automated tests |

## 3. Prerequisites

Refer to the repository dependency manifests for the supported versions.

The deployment guide documents Node.js 20+ and Python 3.12 or 3.13
for the standard native setup. Python binary dependencies such as FAISS
and PyTorch must have compatible wheels for the operating system and
Python version.

Windows PowerShell setup:

```powershell
python --version
node --version
npm --version

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -r apps/api/requirements.txt `
    -c apps/api/requirements.lock.txt
```

If PowerShell blocks virtual-environment activation, use the appropriate
local execution-policy setting or invoke the environment's Python directly.

## 4. Starting the backend

Run commands from the repository root.

Create a persistent local runtime directory:

```powershell
New-Item -ItemType Directory -Force .\work\raglab-data

$env:RAGLAB_DATA_DIR = (
    Resolve-Path .\work\raglab-data
).Path
```

Start FastAPI:

```powershell
python -m uvicorn main:app `
    --app-dir apps/api `
    --host 127.0.0.1 `
    --port 8000
```

The API is available at:

- API base: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

Keep the server terminal open while making requests from another terminal.

The health endpoint reports application status, model registry information
and optional language-model provider configuration. Embedding models load
lazily when indexing or retrieval requires them.

## 5. Main API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Backend health and configuration |
| GET | `/documents` | List stored documents |
| POST | `/documents` | Upload and extract a document |
| GET | `/documents/{id}` | Read a document |
| DELETE | `/documents/{id}` | Delete a document and invalidate dependent indexes |
| POST | `/chunks/preview` | Preview chunking |
| POST | `/experiments` | Create a search experiment |
| GET | `/experiments` | List experiments |
| POST | `/search` | Search through an experiment |
| GET | `/models` | List supported embedding models |
| GET | `/provider` | Inspect provider configuration |
| POST | `/provider/check` | Check configured provider access |
| GET | `/storage` | Inspect database integrity and storage statistics |
| GET | `/storage/check-indexes` | Check stored index artifacts |
| GET | `/indexes` | List vector indexes |
| POST | `/indexes` | Start an indexing job |
| GET | `/indexes/{id}` | Inspect index status and progress |
| POST | `/retrieve` | Retrieve similar document chunks |
| GET | `/answers` | Inspect saved answer records |
| POST | `/rag` | Run the RAG answer workflow |

Use `/openapi.json` as the authoritative source for current request
schemas, required fields, response codes and available operations.

## 6. Document ingestion and validation

The document upload endpoint accepts:

- PDF (`.pdf`)
- UTF-8 text (`.txt`)
- Markdown (`.md`)

The upload is sent as multipart form data using the field name `file`.

Example:

```powershell
curl.exe -i -X POST "http://127.0.0.1:8000/documents" `
    -F "file=@work/sample.pdf"
```

Important validation boundaries:

- Unsupported extensions are rejected with HTTP 415.
- Invalid or unreadable document content is rejected with HTTP 422.
- The document upload endpoint enforces a 10 MB file-size limit.
- The request boundary middleware enforces a 12 MB request-size limit.
- Empty extracted content is rejected.
- PDF extraction runs through a separate bounded worker.
- PDF processing has a timeout and limits on file size, page count
  and decoded content.
- Text extraction rejects binary content disguised as text.

The application stores extracted source text and page information.
It does not retain original PDF binaries as its document-storage format.

## 7. Chunking and embedding generation

RAGLab supports three chunking strategies:

1. Fixed: splits content according to a token budget and overlap.
2. Sentence: uses sentence boundaries while respecting the budget.
3. Semantic: uses content-aware boundaries.

The embedding registry contains two pinned models:

| Model ID | Model | Dimensions |
|---|---|---:|
| `minilm` | all-MiniLM-L6-v2 | 384 |
| `bge-small` | bge-small-en-v1.5 | 384 |

Both models use pinned revisions and normalized embeddings.
The BGE model uses its configured query instruction.

Model weights are downloaded and cached locally on first use.
Retrieval does not require an external LLM API key.

## 8. FAISS indexing and retrieval

Index creation is an asynchronous operation.

The `POST /indexes` request uses a `Build` schema. The required
`document_ids` property is an array of document IDs.

Example:

```json
{
  "document_ids": ["DOCUMENT_ID"],
  "model_id": "minilm",
  "strategy": "fixed",
  "budget": 120,
  "overlap": 20,
  "rebuild": false
}
```

The API initially returns HTTP 202 when the job is accepted.
Inspect `GET /indexes/{id}` to follow its progress.

Typical lifecycle states include queued, running, ready, failed
and cancelled.

A successful index contains persisted vector and FAISS artifacts.
The pipeline records artifact checksums, model metadata and index
statistics. It validates stored artifacts before retrieval.

Example retrieval request:

```json
{
  "index_id": "INDEX_ID",
  "query": "What does the document explain?",
  "top_k": 3
}
```

The retrieval response includes matching source chunks, similarity
scores, source metadata and timing information.

## 9. SQLite and persistence

The backend stores application data under `RAGLAB_DATA_DIR`.

The SQLite database is named `raglab.sqlite3`. SQLite uses WAL mode,
foreign-key enforcement and a connection timeout.

Persistent data includes document records, experiments, vector-index
metadata, chunk information, embedding-cache records, retrieval
snapshots and answer records.

FAISS index artifacts and vector arrays are stored alongside the
runtime data.

For a persistence check:

1. Upload a valid document.
2. Create an index and wait until its status is `ready`.
3. Retrieve content from that index.
4. Stop the API process cleanly.
5. Restart the API with the same `RAGLAB_DATA_DIR`.
6. Check `/documents` and `/storage`.
7. Retrieve from the original index again.

A successful restart should preserve the document, ready index and
retrieval capability.

Back up the complete runtime directory while the backend is stopped.
Do not commit runtime databases, private documents, model caches or
generated index artifacts.

## 10. Request boundaries and security

The backend includes several defensive measures:

- Explicit CORS origin configuration.
- Request-size validation, including streamed request bodies.
- Filename normalization.
- Upload extension and content validation.
- Bounded PDF extraction.
- Restricted PDF worker resource consumption.
- CSV formula-injection protection.
- Secret redaction in provider-facing responses.
- Git ignore rules for local environment files and private artifacts.

Configure allowed browser origins through `CORS_ORIGINS`.

Use local environment variables for secrets. Never commit actual API
keys or private credentials. `.env.example` is intended for placeholders,
not real secrets.

These controls do not provide authentication, tenant isolation or a
general security sandbox. The application is intended as a local,
single-user research application. Do not expose it publicly without
additional access control and deployment hardening.

## 11. Automated backend tests

Run the backend test suite from the repository root:

```powershell
python -m pytest apps/api/tests -v
```

For a shorter summary:

```powershell
python -m pytest apps/api/tests -q
```

The backend tests cover areas including:

- Chunking strategies and source boundaries.
- PDF, TXT and Markdown validation.
- Invalid uploads and oversized files.
- PDF extraction limits and timeouts.
- API request validation and error handling.
- SQLite persistence and document deletion.
- Embedding and retrieval behavior.
- FAISS artifact creation, loading and integrity.
- Cache reuse and index lifecycle.
- Restart recovery and cancellation.
- CORS and request-boundary behavior.
- Provider configuration and secret redaction.

### Recorded automated test result

A previous full backend run on the Windows PDF compatibility
contribution branch completed with:

- 73 tests passed.
- 0 tests failed.
- 1 warning.
- Execution time: approximately 630.62 seconds.

This result was recorded before the compatibility fix was merged into
`main`. Re-run the suite on the current branch when performing a fresh
release verification.

## 12. Live Windows backend verification

A separate live API verification was performed on Windows using a
disposable runtime directory:

`work/startup-check`

A generated one-page PDF named `valid-test.pdf` was used as test input.
It contained text for validating ingestion and retrieval.

Recorded results:

| Verification | Observed result |
|---|---|
| Backend startup | Application startup complete |
| Health endpoint | HTTP 200 |
| Valid PDF upload | HTTP 201 |
| Unsupported `.exe` upload | HTTP 415 |
| Invalid PDF upload | HTTP 422 |
| Document listing | One document persisted |
| SQLite integrity | `ok` |
| Index creation | HTTP 202 |
| MiniLM embedding | 384 dimensions |
| FAISS indexing | One vector, index ready |
| Retrieval | HTTP 200 |
| Empty retrieval query | HTTP 422 |
| Server shutdown | Clean shutdown |
| Server restart | Application startup complete |
| Document after restart | Still present |
| Ready indexes after restart | 1 |
| FAISS artifact bytes after restart | 3245 |
| Retrieval after restart | Successful |
| Index reuse after restart | `true` |

The final post-restart retrieval returned content from `valid-test.pdf`
with a similarity score of approximately 0.5654.

The first indexing run downloaded the pinned MiniLM model. Subsequent
runs can use the local model cache.

This is a live local verification, not a claim of production deployment
or a substitute for the automated regression suite.

## 13. Troubleshooting

### Port 8000 is already occupied

Identify the process using the port before stopping anything.
Do not terminate an unknown process.

### Model download takes time

The first embedding operation downloads the pinned model revision.
Allow time for the download and ensure the machine has sufficient
disk space and memory.

### Hugging Face symlink warning on Windows

The cache can still work without symlink support, but may use more
disk space. Developer Mode or appropriate permissions can enable
symlink support.

### Index remains queued or running

Inspect `GET /indexes/{id}` and the Uvicorn terminal for progress
or an error. Do not submit duplicate builds while a job is active.

### Retrieval reports an index error

Check that the index status is `ready` and that its artifacts pass
the storage/index integrity checks.

### Upload returns HTTP 413

Check both the document upload limit and the overall request-size
boundary. A request can exceed the middleware limit before reaching
the upload handler.

## 14. Known limitations

- The application is designed for local, single-process use.
- Multi-user authentication and tenant isolation are not implemented.
- OCR is not part of the documented PDF text-extraction workflow.
- Optional LLM answer generation requires separately configured
  provider credentials.
- A successful health response does not prove that external
  generation is configured or available.
- Docker and cloud deployment must be verified separately.
- Local persistence depends on retaining the configured runtime
  directory and its contents.

For broader deployment constraints and hosting guidance, see
[DEPLOYMENT.md](DEPLOYMENT.md).
