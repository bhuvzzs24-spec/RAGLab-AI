# Existing-project audit and preservation

Audited on 5 November 2026 before Phase 3 integration.

- The working directory initially had no Git metadata, branch or remote. Authenticated GitHub API access confirmed an empty `bhuvzzs24-spec/RAGLab-AI` repository with `main` as its default branch. No prior remote commits were replaced; no force push is used.
- Existing backend: FastAPI, Pydantic, SQLite WAL/foreign keys, bounded PyMuPDF/TXT/MD uploads, exact-source chunk previews, three chunkers, persistent FAISS worker, normalized MiniLM/BGE embeddings, durable vector-index jobs, cache reuse, original page/offset highlighting and optional grounded generation.
- Existing model revisions are preserved: MiniLM `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` and BGE Small `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`. Both are 384d; BGE query instructions and model-token limits remain intact.
- Existing SQLite tables for documents, experiments, preferences, vector indexes, memberships, passages, embedding cache, retrieval snapshots and answers are retained. Phase 3 adds separate dataset/run/configuration/measurement tables rather than rebuilding existing storage.
- All original pages and the colorful interface are retained. Datasets and Benchmarks are added; the measured retrieval leaderboard is separated from the preserved legacy chunk-timing registry.
- Optional live LLM Q&A was already unverified because credentials were missing. It remains optional and honestly labeled. No external API is needed for retrieval benchmarks.

## Source availability recovery

During the audit, macOS cloud-storage placeholders made reads of original source, the saved ZIP, Git metadata and dependency files time out. Cloud-download requests did not materialize them during verification. Existing bytes were not guessed or replaced with a new application.

The source was recovered verbatim into an isolated non-cloud build directory from this project's earlier source-writing records, applying the original recorded edits in order. Thirty unchanged recovered source files matched their recorded placeholder lengths. The full original 29-test suite passed against that recovered Phase 2 source before the new features were tested. The two backend files already changed for Phase 3 were integrated from the same original source records.

The complete tested source is restored to the original working directory, with displaced cloud-only originals retained under ignored `work/cloud-originals/`. Dependency manifests were regenerated/locked from the tested installation; Next.js remains on the same 15.5 release line. Verification, browser artifacts and runtime caches live outside version control. No cloud recovery tooling or chat/execution logs are committed.

## Preservation checks

The expanded suite covers the original behavior and Phase 3. Real-model matrix execution uses the existing indexing/retrieval engine. Browser tests verify the original Playground and exact-source highlight dialog alongside new dataset/benchmark pages. See [VERIFICATION.md](VERIFICATION.md) for actual counts, execution evidence, limitations and publishing status.
