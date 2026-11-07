# Phase 1–3 verification

Executed on 5 November 2026, macOS ARM64, Python 3.13.15 and Node.js 20.20.2.

| Feature/check | Result | Evidence |
|---|---|---|
| Original Phase 1–2 baseline | PASS | All 29 original backend tests passed before testing Phase 3 |
| Expanded backend suite | PASS | 51 tests passed, including metric arithmetic, dataset imports/review rules, Unicode offsets, snapshots, cache/model separation, real FAISS persistence, cancellation/resume, failure/restart recovery, exports and optimizer objectives |
| Frontend production build | PASS | Next.js compiled, type-checked and generated the app |
| Standalone TypeScript | PASS | `npm run typecheck` |
| Dependency audit | PASS | Clean installation reported zero vulnerabilities |
| Real 18-configuration matrix | PASS | Two actual local models × three chunkers × budgets 64/128/256; 216 measured queries |
| Real repeatability run | PASS | A second 18-configuration/216-query run reproduced retrieval-quality scores; latency remains variable |
| Desktop/mobile browser smoke | PASS | Six Chromium tests cover source review validation, real 18-configuration runs, cancellation/resume, charts/comparison/filter/optimizer/CSV behavior, and preserved Phase 2 retrieval/source highlighting |
| Optional live LLM-generated Q&A | NOT TESTED | No provider model/credentials; retrieval benchmarks run without them |
| Semantic groundedness / semantic answer correctness | NOT TESTED | No validated semantic evaluator; no invented scores |
| Remote GitHub Actions execution | See GitHub | The workflow is included; local results above are not a claim that remote CI passed |

## Actual benchmark evidence

Primary run: `8ed1cc53-844c-4b63-83bd-e917dc5b7543`.

Dataset fingerprint: `5702cd5af5c6f8f6bd0a6e62d8898aae5d15059cb62010906d3a447242c79cbb`.

Repeat run: `2ef292fd-71ef-4152-8ea7-48a815508dea`.

Both completed 18 configurations and 216 unique `(configuration, question, repetition)` measurements: six questions × two repetitions × 18 configurations. Four questions are answerable and two are unanswerable. The annotations are explicitly **unreviewed/provisional**; no human review or generalized research-quality claim is made. Each configuration has four unique answerable questions and eight answerable retrieval measurements, not 216 independent questions. The repeat reused 143 passage embeddings while rebuilding versioned artifacts and reproduced quality scores.

The sample balanced winner in the primary execution was MiniLM/fixed/256 words, with Precision@3 0.3333, evidence Recall@3 1.0, MRR 1.0 and mean retrieval latency 99.01 ms on this machine. This is a tiny-corpus, provisional point estimate; it is not a universal model/chunker recommendation. Full per-configuration measurements, timings and cache conditions are recorded in [verification/benchmark-evidence.json](verification/benchmark-evidence.json), with actual query rows in [verification/benchmark-measurements.csv](verification/benchmark-measurements.csv).

Browser runs additionally execute the real 18-configuration matrix on desktop and mobile using one repetition (108 measurements each) and explicitly test cancellation followed by immediate resume. They use disposable data and do not mark automated judgments as genuine human review.

## Failures found and fixed

- The initial browser submit was blocked by a numeric step/minimum mismatch for the default evidence overlap. The form now permits its default threshold, and the test asserts no invalid input before submission.
- Immediate resume could reuse an index whose cancellation had been requested but not finished. The engine now excludes cancellation-requested indexes from reuse; a new backend regression test and both real browser cancellation/resume flows verify the fix.
- CSV rows sharing a question ID now reject contradictory reference, answerability or review metadata instead of silently using the first row.
- The expanded navigation can scroll on short viewports. Unicode source highlights use code-point offsets consistent with Python/evidence imports.
- Existing source was restored from original authoring records after cloud-only placeholders blocked reads; original behavior passed its baseline tests before Phase 3 integration. See [AUDIT.md](AUDIT.md).

## Limits and Phase 4 readiness

Phase 3 provides a tested local research foundation for Phase 4. Its sample judgments need independent human review and a larger/held-out dataset before research conclusions. Repeated questions are not independent samples, and latency ranks can change with load/cache state. The optimizer discloses its heuristic scoring weights.

Optional generation can calculate strict normalized exact match only after actual successful provider output and valid references. Quote validation does not establish semantic entailment. Live Q&A and semantic groundedness remain unverified/unscored.

The app remains single-user/local with one indexing worker and one benchmark orchestrator. Cancellation is cooperative between model calls; interrupted jobs require explicit resume. Authentication, tenancy, distributed scheduling, broader browser/accessibility coverage and a validated semantic evaluation method remain Phase 4/deployment work. Cloud-only local dependency files may require `npm ci` / a fresh Python environment; the GitHub source does not depend on the recovery logs or runtime caches.
