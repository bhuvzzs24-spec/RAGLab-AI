# Phase 3 setup and usage

Follow the root README for the existing Next.js/FastAPI setup. Run all backend commands from the repository root with a stable `RAGLAB_DATA_DIR`.

1. Start FastAPI and Next.js.
2. Open **Datasets**. Import a UTF-8 CSV/JSON file, create questions, or load the explicitly unreviewed CC0 sample.
3. Select a source passage, add it as evidence, enter a reference answer and answerability, and record a reviewer before marking the item reviewed. Save the dataset.
4. Open **Benchmarks**. Select the dataset, three word budgets, fixed top-k, repetitions and seed. Default evaluation uses reviewed questions only. Explicitly opt into provisional annotations for the sample.
5. Run the 18 configurations. Observe actual indexing/query progress. Cancel and resume missing work as needed; committed measurements remain.
6. Inspect charts, measured heatmaps and configuration comparisons. Switch between accuracy, speed and balanced optimization. Recommendations are limited to the selected run and filter cohort.
7. Export CSV or JSON from the benchmark, Leaderboard or Reports page. Null answer/groundedness metrics remain null.

The original Documents, Chunking Lab, Embeddings, saved Experiments, RAG Playground, source highlighting, preferences and legacy timing registry are preserved. The new ranked leaderboard is separate from the historical chunk-count/timing table.

## Import schema

JSON uses a dataset object with `name`, optional `description`, `document_ids` and `questions`. Each question accepts `id`, `question`, `reference_answer` / `reference_answers`, `answerability` (`answerable`, `unanswerable`, `unknown`), `human_reviewed`, `reviewer`, `review_notes` and `relevant_spans`.

A source span accepts `document_id` or an unambiguous `document_name`, Unicode `start`/`end` offsets and/or an exact `quote`. Quote-only import is accepted only when the quote appears exactly once. Normalized exports include the full source hash and page mapping. Overlapping gold spans must be merged.

CSV columns: `question_id,question,reference_answer,reference_answers,answerability,human_reviewed,reviewer,review_notes,document_id,document_name,start,end,quote,source_sha256`. Repeat a question ID on multiple rows to add multiple evidence spans. CSV `reference_answers` is a JSON string array. Review values are `true/false` or `1/0`. Unknown items are editable but excluded from benchmarks.

`apps/api/samples/benchmark-sample.json` is a portable quote-anchored example over the original CC0 source files. The sample loader imports those sources if needed. No human review is claimed by the sample.

## API

- `GET/POST /datasets`; `GET/PUT /datasets/{id}`
- `POST /datasets/import` (multipart `file`, optional collection `document_ids` JSON)
- `POST /datasets/sample`; `GET /datasets/{id}/export?format=csv|json`
- `POST /benchmarks/runs`; `GET /benchmarks/runs`; `GET /benchmarks/runs/{id}`
- `POST /benchmarks/runs/{id}/cancel|resume`
- `GET /benchmarks/runs/{id}/measurements`
- `GET /benchmarks/runs/{id}/leaderboard?objective=accuracy|speed|balanced`
- `GET /benchmarks/runs/{id}/export?format=csv|json`
- `GET /benchmarks/methodology`

A local run supports at most 100 included questions and five repetitions. Datasets can contain up to 500 editable questions; split large research evaluations into intentional cohorts. Import size is limited to 2 MB.

## Checks

```sh
pytest apps/api/tests -q
npm run typecheck
npm run build
# Real-model 18-configuration execution, no synthetic retrieval:
python apps/api/scripts/smoke_benchmark.py --output work/benchmark-evidence.json
```

See [METHODOLOGY.md](METHODOLOGY.md) for exact metric definitions and optimizer formulas, and [ARCHITECTURE.md](ARCHITECTURE.md) for persistence and execution boundaries. Live LLM-generated Q&A remains optional and unverified without credentials.
