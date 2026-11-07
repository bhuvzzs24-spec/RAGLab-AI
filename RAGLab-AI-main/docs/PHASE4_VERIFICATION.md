# Phase 4 verification evidence

Executed on 2026-11-05, Apple Silicon macOS, Python 3.13.15, Node production Next.js build. The repository continues existing main commit `480f1b74baacb02be4c1465672f5a08d59031bbd`; no earlier source or Git history was replaced. Existing private runtime directories were not modified. All tests use controlled fixtures or disposable public-sample runtime directories.

## Real model execution

`python apps/api/scripts/smoke_adaptive.py` used the actual pinned MiniLM and BGE-small models and persisted FAISS artifacts, never fixture embeddings. The original Phase 3 evidence remains in this directory alongside the new `verification/phase4-adaptive-evidence.json` and CSV.

- Adaptive search: `4b8e37b0-74cf-4a66-abb3-7fe303d48766`.
- Validation run: `39f61ae7-d5a7-4e19-bd95-eb034214f216`: 18 configurations, 4 unique questions (3 answerable + 1 unanswerable), 2 repetitions, **144 measured queries**.
- Held-out run: `bb0726d7-6501-4147-b877-1bc55bfb1380`: exactly 1 frozen configuration, 4 different unique questions (3 answerable + 1 unanswerable), 2 repetitions, **8 measured queries**.
- Separate repeated validation run: **144 measured queries**, identical P@k/R@k/MRR per configuration. Latencies are real measurements and varied.
- Total real adaptive verification queries: **296**, excluding warm-ups. Both embedding dimensions: 384; generated artifacts passed checksum/load checks.
- SQLite `PRAGMA integrity_check`: `ok`; `foreign_key_check`: no rows.
- Reserving the same test questions for another search: correctly rejected (409). Test-run adaptive selection: correctly rejected (422).

The frozen choice was BGE-small / semantic / 128 words for this objective and host. Held-out P@3 = 0.333333, Recall@3 = 1.0, MRR = 1.0, mean retrieval latency = 126.95375 ms. Retrieval abstention on the illustrative unanswerable question was 0: vector similarity alone does not establish answerability. Generated answers and semantic groundedness were **not evaluated**. All 12 sample questions are **UNREVIEWED**, including all held-out labels. This tiny fictional CC0 dataset is a software smoke test, not evidence of general superiority. Its recall bootstrap interval [1,1] with N=3 is not certainty.

## Automated and visual checks

- Backend: **61 passed**, including all 51 prior Phase 1-3 tests and 10 adaptive/split/report tests. Tests cover actual upload validation, source/chunk offsets and overlap, persistence, retrieval relevance, citation mapping, provider failure/abstention contracts, 18-config execution, recovery, cancellation, immutable snapshots, split leakage, Pareto/constraints, bootstrap sample sizes, test reservation and PDF text/provenance.
- Frontend production build: PASS. TypeScript: PASS.
- Browser desktop/mobile: **10 passed** in one final production-build run (1.5 minutes). Includes actual real-model 18-config runs, cancellation/resume, adaptive validation/held-out, citation/source highlights, source review flags, PDF/CSV download, all nine original pages, mobile overflow checks and dark mode.
- PDF: held-out and full 18-config reports generated from persisted measurements, rendered locally and visually inspected; extracted text and all text-block page bounds checked. PyMuPDF rendering was used because the bundled Poppler fontconfig configuration was unavailable.
- Dependency consistency (`pip check`): PASS. Staged source/secret/oversize audit: performed before commit.
- CI: GitHub Actions verifies constrained Python dependencies, backend tests, npm lock installation, production build and types. Real-model smokes and browser workflows are available through the manual real_benchmark input. Actual delivery status is reported with the final commit.

## NOT TESTED / limitations

Live credentialed LLM Q&A: **NOT TESTED**, no provider key/model configured. Unit-test transports verify request/response contracts; they are never counted as live AI outputs. Semantic answer correctness/groundedness: **not evaluated**, no validated semantic/human claim evaluator configured. Strict normalized exact match is implemented only when real generation succeeds.

Docker execution: **NOT TESTED**, no Docker binary/daemon available here. Compose/Dockerfiles and persistent-volume/health configuration are included; native workflows are verified. No cloud deployment was created. OCR, multi-user authentication, distributed executors and calibrated semantic evaluation remain future work. Semantic paraphrases and previously manually inspected test sets still require responsible human study design beyond the automated reservation checks.
