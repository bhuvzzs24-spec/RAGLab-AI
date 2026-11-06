# Research and editorial upgrade (2026-11-06)

This continues the existing main history through `5db4acf`. The original chunkers, pinned MiniLM/BGE models, normalized 384d embeddings, persisted FAISS artifacts, 18-configuration suite, adaptive search, source highlighting, datasets and exports are retained. Schema changes are additive; runtime data and historical snapshots are never reset by this upgrade.

## Evidence review and valid experiments

Questions have explicit unreviewed/reviewed/rejected states. Approve, reject and reopen decisions require reviewer attribution and optimistic dataset revision checks. Rejected questions are excluded even when a run includes provisional annotations. Content edits revoke approval on the backend; the UI also clears its attestation immediately. A reviewer name is a local self-attestation, not an authenticated identity.

`dataset_review_history` appends before/after question snapshots, action, actor when explicitly supplied, notes, revision and timestamp. Unattributed edits remain unattributed. Legacy review flags are preserved without invented historical events. Imported flags/reviewer names are reset to unreviewed/unattributed; importing a file is not a new human review. Actual question/reference/evidence content survives the import. Dataset JSON exports include recorded audit events. New benchmark snapshots retain the IDs of the audit events available at that revision; JSON exports include only those frozen audit events.

The research-scope filter separates provisional runs from reviewed annotation scopes. This is provenance, not a guarantee that labels are objectively correct. A descriptive rerun can follow genuine review without rewriting earlier results. Paired comparison refuses different source/question/evidence cohorts, top-k, cutoff, evidence threshold or evaluation version; it reports actual right-minus-left retrieval/timing deltas for matching complete configurations. Reference-based generative scores are not compared by that tool.

The original validation-only 18-candidate search, frozen selection seal, one-config held-out evaluation, test-question reservations, configurable weights/latency constraint, Pareto frontier and question-cluster bootstrap remain. Exact optimizer ties now use stable configuration specifications before random job IDs. Repetitions do not create additional independent questions. Semantic paraphrases and manually inspected test sets still require responsible human study design.

## Real provider adapter and optional human answer evaluation

`POST /provider/check` is an explicit model-list reachability probe. It reports not configured, invalid URL, unsupported probe, access/quota errors, reachable model list or absent configured model. It never exposes credentials or raw provider error bodies, and never claims a successful generation test from a model-list response. No external call is made when configuration is absent.

The existing Chat Completions adapter remains real and opt-in: source-only prompt, explicit insufficient-context response, exact quote and source-ID validation, original citation offsets, bounded context and sanitized failures. `LLM_MAX_RETRIES=0` by default; an explicit value permits at most two short retries for HTTP 429 with bounded Retry-After. Timeouts and 5xx generation requests are not automatically replayed. This is not a claim of support for every provider/model; JSON-object output and max_completion_tokens must be supported.

`GET/POST /answers/{id}/review` provides an optional human rubric. Correctness is incorrect=0, partial=0.5 or correct=1 against an explicitly supplied human reference; not evaluated remains null. Every claim can be marked supported/unsupported/uncertain. Groundedness is the supported fraction only when every claim is judged; any uncertain claim leaves the metric null. Abstentions have no claim groundedness. A named reviewer and explicit inspection attestation are required. Provider failures cannot receive answer scores. Subsequent reviews append history with optimistic latest-review checks.

Benchmark human-review summaries and JSON/PDF exports show latest judgments, answer counts, unique-question counts, rubric and as-of time separately from immutable automated retrieval/exact-match metrics. No review is manufactured when live generation is unavailable. Controlled test transports/fixtures test mechanics only and are not research results.

## Security and reliability bounds

- Maximum file: 10 MB; maximum aggregate request: 12 MB, including streaming bodies with misleading Content-Length.
- Safe basename/control-character validation, UTF-8/control-byte checks and rejection of PDF/ZIP/binary signatures disguised as text. Extension acceptance does not rely on user-supplied MIME types.
- PDF text extraction runs in a separate process with a 25-second parent timeout, Unix CPU limits and a Linux address-space cap of 768 MiB. Decoded page streams are capped at 16 MB, pages at 500 and extracted text at two million characters. Two concurrent PDF extractions maximum; further requests receive 429.
- This is a resource boundary, not a general native-code sandbox. OCR is not implemented. Malformed, encrypted, resource-exhausting or textless PDFs return actionable errors.
- At most three active benchmark jobs, enforced atomically for new and resumed runs. Existing cancellation/resume, checksums, source hashes and model-version checks remain.
- Explicit CORS origins and write-origin checks protect the local browser workflow; they are not authentication. A missing Origin is permitted for local programmatic clients. Add access control, quotas and tenant isolation before public multi-user hosting.
- CSV textual formula prefixes are escaped for spreadsheet safety. Use JSON for lossless text round-trips. Exports can contain private extracted passages, references and review attribution; share responsibly.

## Editorial interface and motion

The selected identity is Orchid Pink `#E7B0DE`, Deep Eggplant `#400849`, Signal Orange `#FF5A0A`, warm white and neutral surfaces. Dark text on orange primary controls preserves contrast. Shared shells, cards, forms, charts, source modals, report previews and all existing pages use the new system.

Overview shows actual stored counts, recent runs and a conditional recommendation. Datasets add decisions/history. Chunking Lab adds actual side-by-side outputs. Embeddings uses deterministic-sign PCA with exact-source-span stable identities; independently computed projections do not share a semantic coordinate system. Leaderboard includes explanations, sample counts, uncertainty and the actual complete-run Pareto frontier. Reports has measured PDF/CSV/JSON download previews. Settings shows provider/storage health, artifact verification and persisted motion preference.

The introduction is optional, skippable and pausable; it is explicitly conceptual motion with no fake metrics or jobs. The optional six-stage Pipeline Tour uses native scrolling, a sticky section rail, actual selected-source chunks, stored vectors, real retrieval, source-matched benchmark history and conditional frozen recommendations when available. No scroll hijacking or GSAP dependency is used. Missing data produce honest empty states. Modal Escape/focus handling, keyboard vector selection, mobile navigation and reduced motion are tested. Intensive movement stays in the optional experience; research forms and tables remain stable.

## Delivery boundaries

Native local execution is verified separately from a public deployment. The existing Compose architecture still separates web and persistent Python API volumes; Docker execution requires Docker and is not claimed when unavailable. Vercel can host a separately configured frontend, not automatically the heavy local workers, model cache, SQLite or FAISS lifecycle. See DEPLOYMENT.md for persistent-host requirements. Live generation remains NOT CONFIGURED / NOT TESTED without credentials. No semantic judge scores, human-reviewed sample results or public deployment are invented.
