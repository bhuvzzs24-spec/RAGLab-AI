# Adaptive optimization (Phase 4)

Phase 4 extends the existing monorepo and adds tables; it does not replace documents, indexes, embedding caches, datasets, benchmark runs or previous measurements. Existing datasets default to `unassigned` until explicitly partitioned. Historical snapshots are not rewritten. Back up the complete runtime directory before any upgrade. Run exactly one API process: the in-process executors and SQLite ownership are designed for a local research workstation, not multiple replicas.

## Workflow

1. Datasets → load the **split-ready sample**, or import CSV/JSON. All supplied sample judgments are **unreviewed**. The pending-review filter, original source selection, exact evidence quotes, reviewer identity, notes and explicit attestation support human review. Changing question/reference/evidence clears the UI review flag.
2. Set train/validation/test and optional related-question group IDs. **Assign group-safe splits** uses seed 7 and approximately 60/20/20 independent connected groups, ensuring each split has at least one group. It does not manufacture labels or guarantee class balance; check that validation and test each contain answerable questions. Save edits before assigning splits.
3. Split components connect exact normalized question duplicates, explicit groups and overlapping evidence intervals in the same source. A component cannot cross partitions. This does not detect all semantic paraphrases; group related questions manually. Split by document or topic for stronger distribution-shift studies when the corpus permits it. The index can contain all source documents: the held-out objects are question/evidence labels, not hidden corpus documents.
4. Benchmarks → Adaptive search. Set budgets (3 chunkers × 2 models × 3 budgets), fixed top-k, repetitions, accuracy weight and optional maximum mean query latency. Reviewed labels only by default; explicitly opt into provisional annotations for demonstrations.
5. Search all 18 candidates on **validation only**. Train questions are reserved for manual development and never scored by automatic search. A SHA256 seal fixes the winner, objective, validation fingerprint and reserved test fingerprint **before** test queries.
6. Evaluate **only that one frozen configuration** on test. The system refuses new adaptive searches that reserve an already reserved/exposed normalized test question. Resume an existing search, or collect genuinely new test questions. Manual benchmark endpoints remain available for descriptive research; do not treat an already inspected test set as unseen.
7. Inspect validation Pareto chart and seeded question-bootstrap intervals, then descriptive held-out results. Export PDF/CSV/JSON from either run. Small or unreviewed datasets support demonstrations, not general superiority claims.

## Objective

Quality is a normalized weighted sum of Recall@k, MRR and Precision@k (default .45/.35/.20). The API supports changing these weights. A mean-latency constraint removes infeasible candidates. Speed is inverse min-max latency within the feasible cohort (1 when equal). Score = accuracy_weight × quality + (1 - accuracy_weight) × speed, default .70/.30. Deterministic ties use quality, latency and configuration ID. The frontier includes non-dominated complete configurations maximizing quality and minimizing latency, before the latency constraint. Scores are cohort-dependent, not universal accuracy.

Intervals use 1,000 seeded percentile bootstrap resamples over per-question means, grouping query repetitions. N is unique questions, never repetitions. With fewer than two applicable questions the interval is unavailable. Intervals are exploratory, unadjusted for candidate multiplicity, and related questions can remain correlated. An interval [1,1] from three sample questions is not evidence of certainty. Within-run quality repeatability and a separate repeated validation run are reported separately from variable latency.

## APIs

- `POST /datasets/sample/adaptive`: original CC0 source, 12 unreviewed questions, preassigned 4/4/4 splits.
- `POST /datasets/{id}/split`: `{expected_revision, seed}`; optimistic revision and connected-group assignment.
- Question import/export fields include `split` and `group_id` in both CSV and JSON.
- `POST /adaptive/analyse/{validation_run_id}`: `{accuracy_weight, recall_weight, mrr_weight, precision_weight, max_latency_ms}`. Returns actual rankings, Pareto IDs, uncertainty, repeatability and caveats. Test runs are rejected for selection.
- `GET/POST /adaptive/searches`; `GET /adaptive/searches/{id}`; `POST .../{id}/cancel` and `.../{id}/resume`.
- Existing `POST /benchmarks/runs` adds optional `evaluation_split` (default `all`, preserving Phase 3 behavior). The ordinary default remains all 18 configurations.
- `GET /benchmarks/runs/{id}/export?format=pdf|csv|json` includes measured results. JSON retains full snapshots, provenance and per-query records; PDF contains actual charts, limitations, model versions and source hashes. No external chart renderer is contacted.

Cancellation is cooperative between retrieval/model calls. Completed measurements persist. Interrupted jobs are marked on restart and can resume missing stages with source/model/selection integrity checks. Failed/incomplete configurations cannot select a winner. A failed latency constraint does not trigger silent objective relaxation.

## Generative RAG status

The existing real OpenAI-compatible adapter is retained: environment-selected provider/model, retrieval-only fallback when unconfigured, explicit insufficient-context response, strict source-ID/verbatim quote/offset validation and sanitized error handling. To enable it, export `LLM_API_BASE`, `LLM_MODEL`, `LLM_API_KEY` (or `OPENAI_API_KEY`) before starting the API. Trusted local compatible servers can explicitly set `LLM_REQUIRE_KEY=false`. Providers must support JSON-object Chat Completions and `max_completion_tokens`. No compatibility with every provider/model is claimed.

Optional answer evaluation is normalized exact match against references on successfully generated answerable responses. Citation provenance is validated, but semantic correctness/groundedness is not inferred from quotes, similarity or an uncalibrated LLM judge. Semantic groundedness remains unevaluated. Live generation requires credentials and is **NOT TESTED** in this delivery; adapter success-contract, failure, abstention and citation-mapping paths are tested using explicit unit-test transports, never presented as live AI evidence.
