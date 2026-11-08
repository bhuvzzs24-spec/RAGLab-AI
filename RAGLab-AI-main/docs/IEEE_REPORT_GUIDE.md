# IEEE mini-project report writing guide

Use the exact IEEE/university template required by your faculty; this Markdown is a content and evidence guide, not a claim of IEEE publication acceptance. Replace author/institution fields yourself. Do not invent related-work citations, reviewer identities, user studies, live generation results or significance claims.

**Suggested title:** Adaptive RAG Benchmarking and Optimization with Source-Span Evaluation and Held-Out Validation.

**Abstract (150-200 words):** State the problem of coupled chunking/embedding choices; describe a local Next.js/FastAPI/SQLite/FAISS studio with three chunkers, two pinned embedding models and three budgets. Describe source-span judgments, 18-candidate validation search, configurable latency/quality objectives, Pareto analysis and one frozen held-out test. State measured execution counts from PHASE4_VERIFICATION.md. Explicitly identify illustrative unreviewed labels, tiny sample sizes, and unverified credentialed generation. Avoid claiming improved state-of-the-art performance.

## I. Introduction

Explain the need for fair comparisons across different chunk sizes, source-traceable retrieval and reproducibility. List concrete project contributions: preserved document pipeline, real model-specific embeddings, evidence-aware benchmarking, honest missing generation state, held-out search and reproducible reports. Distinguish working engineering contributions from unvalidated research hypotheses.

## II. Related Work

Read and cite primary papers/model cards/documentation for retrieval-augmented generation, sentence-transformers, FAISS, MiniLM and BGE. Verify exact titles, authors, year and DOI/arXiv links before including references. Do not cite this guide as evidence of model quality. Discuss why overlap-based source relevance and strict answer exact match are limited proxies.

## III. System Architecture

Use the Mermaid diagrams in ARCHITECTURE.md; render them as figures in the required template. Describe upload validation, PyMuPDF extraction, three chunkers, tokenizer-safe subpassages, normalized vectors, pinned revisions, SQLite metadata, isolated FAISS subprocess and source offsets. Document the single-host/single-worker design and persistent volumes. No deployment on Vercel's Python workers is claimed.

## IV. Methodology

Define requested-k precision, unique source-evidence recall, reciprocal rank and exclusion of unanswerable questions from P/R/MRR. Specify overlap threshold, corpus, source hashes, word budgets, top-k, model SHAs, seed, excluded warm-ups, repetition scheduling and cache state. Describe human-review attestation and the fact that supplied annotations remain unreviewed. Explain connected split groups, train development, validation-only candidate search, selection seal and untouched one-config test. Show quality/speed objective formulas and Pareto dominance from PHASE4.md. Discuss the reservation guard and remaining manual risk of semantic paraphrases or manually inspecting a test set through other endpoints.

## V. Results

Use only the committed execution JSON/CSV and PHASE4_VERIFICATION.md. Distinguish candidate count, unique answerable N, total questions and repeated query measurements. Include validation quality-versus-latency, configuration heatmap and held-out metrics for the selected configuration. State percentile bootstrap construction and multiplicity/correlation caveats. Never treat repetitions as more independent questions. A [1,1] interval on three answerable examples is not certainty. Label illustrative sample results **PROVISIONAL** in every figure/table caption.

Generation: adapter contract/failure/citation tests pass; live credentialed Q&A is NOT TESTED. Optional exact-match values are absent when no real answer was generated; semantic correctness/groundedness are not evaluated. Do not replace unavailable metrics with zero.

## VI. Testing and Limitations

Use actual final backend/browser test counts and production build/type status. Explain controlled fixtures versus real-model smoke evidence. Include SQLite integrity checks, snapshot preservation, restart/resume, invalid citations, provider failures, source highlighting and PDF rendering checks. Document unavailable Docker execution, live LLM credentials, OCR, multi-user isolation and distributed workers. State that data are tiny original fictional CC0 examples with no human-review claim or domain generalization.

## VII. Conclusion and Future Work

Summarize verified engineering capabilities. Propose a separately reviewed domain dataset, preregistered evaluation with enough independent evidence groups, genuinely fresh held-out questions, provider-funded live tests, calibrated human/semantic answer evaluation and deployment hardening. Report no unsupported superiority or readiness for public multi-user production.

## Reproducibility appendix

Record Git commit SHA, hardware/OS/Python/package versions, setup commands, source license, model revisions, immutable dataset fingerprint, objective weights, seed, top-k, run/search IDs, generation configuration status, cache behavior and export links. Private uploads, keys, weights, SQLite and generated FAISS files are intentionally excluded from Git.

## Research/editorial upgrade evidence

Use RESEARCH_VERIFICATION.md and the recorded research-upgrade JSON/CSV for the current execution. Describe explicit approval/rejection/reopen decisions, backend invalidation after content or reviewer changes, imported-flag resets, and append-only before/after provenance. Human answer correctness/claim groundedness use the documented explicit rubric; they are not automatic semantic truth. Report answer-judgment and unique-question denominators separately. No live-provider result or authentic human-reviewed sample study is claimed by the controlled test fixtures.

The optional introduction is conceptual communication, not research evidence. The Pipeline Tour displays actual selected-source boundaries, vectors, retrieval and matching stored experiments with provenance. Screenshots are software demonstration artifacts over public provisional samples. Keep the distinction between a visually polished implementation and validated research claims explicit in the abstract, results and conclusion.
