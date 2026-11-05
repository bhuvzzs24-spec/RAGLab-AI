# RAGLab architecture

RAGLab retains the Next.js / TypeScript / Tailwind / Framer Motion / Recharts frontend and FastAPI / SQLite / PyMuPDF / sentence-transformers / FAISS backend. The additions extend the Phase 2 engine; they do not replace the existing models, indexing, chunking, playground or source viewer.

```mermaid
flowchart LR
    UI[Next.js studio] --> API[FastAPI]
    API --> DS[Dataset manager]
    DS --> SNAP[Immutable source/evidence snapshot]
    API --> JOB[Durable benchmark runner]
    SNAP --> JOB
    JOB --> GRID[18 model/chunker/budget configurations]
    GRID --> ENGINE[Existing Phase 2 indexing/retrieval engine]
    ENGINE --> EMB[Local pinned MiniLM / BGE]
    ENGINE --> FAISS[Persisted isolated FAISS worker]
    ENGINE --> SRC[Original source offsets / pages]
    JOB --> MET[Versioned span evaluation]
    MET --> DB[(SQLite measurements and history)]
    DB --> OPT[Explainable optimizer]
    OPT --> UI
    DB --> EXPORT[CSV / JSON exports]
    ENGINE -. optional .-> LLM[Configured LLM provider]
```

## Modules

| Module | Responsibility |
|---|---|
| `apps/api/main.py` | Existing API/upload/preferences routes and service wiring |
| `chunking.py` | Existing fixed, sentence and semantic source boundaries |
| `embeddings.py` | Existing pinned model revisions, query formatting and tokenizer-safe spans |
| `pipeline.py` | Existing embedding cache, persistent FAISS artifacts, indexing lifecycle, retrieval and sources |
| `generation.py` | Existing optional grounded provider adapter and quote validation |
| `datasets.py` | CSV/JSON import, editable judgments, review attestations and source validation |
| `evaluation.py` | Pure, versioned retrieval metrics, exact match, aggregation and optimizer |
| `benchmarks.py` | Durable 18-configuration run orchestration, resume, history and export |
| `dataset-manager.tsx` | Dataset editor, Unicode-aware source selection and human review workflow |
| `benchmark-center.tsx` | Run builder, actual progress, run history, heatmap, filters and leaderboard |
| `benchmark-charts.tsx` | Lazily loaded charts of measured results |

## Data and execution boundaries

SQLite stores source text/pages, saved experiments, vector-index provenance, embeddings, retrieval/answer snapshots, datasets, immutable benchmark snapshots, configuration statuses and individual measurements. Model weights, SQLite files, source uploads and generated indexes are runtime data and must not be committed.

One existing indexing worker builds FAISS artifacts; one benchmark worker orchestrates configurations and queries. The benchmark uses the same real retrieval engine as the Playground. FAISS remains in a subprocess to avoid Torch/OpenMP conflicts. Warm-ups use the same retrieval path without creating benchmark measurements or normal retrieval history.

A completed per-question measurement has a unique `(config_id, question_id, repetition)` key. Cancellation preserves committed work. Resume validates exact source hashes and pinned model metadata, skips completed configurations and existing measurements, and reruns only missing work. A completed run is immutable; repeat it as a new run. Dataset edits increment revision and do not mutate earlier run snapshots.

Failures retain actionable state and remain excluded from ranking. Null means unavailable/unmeasured; zero means an actual measured zero. Review status, answerability, sample size, model versions, thresholds, seed and cache policy travel with exports.

## Deployment boundary

This is a local, single-user research application. Use one FastAPI worker. Authentication, tenancy, distributed scheduling, OCR and production secrets management are Phase 4/deployment concerns. Optional generation sends the question and retrieved excerpts to the configured provider; local retrieval and benchmarking do not require external API credentials.
