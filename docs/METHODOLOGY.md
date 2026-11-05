# RAGLab research methodology

## The experiment matrix

Each run evaluates exactly 18 combinations: fixed, sentence and semantic chunking × pinned MiniLM L6 v2 and BGE Small EN v1.5 × three distinct word budgets (default 64, 128, 256). Word budgets are the same across all methods/models. Fixed chunking uses 15% word overlap; sentence/semantic overlap is zero. The semantic boundary threshold is held fixed at 0.55 unless explicitly changed before the run. Model tokenizer limits remain enforced by the existing indexing pipeline. A configuration is one model/chunker/budget combination, not one question.

Run settings fix top-k, minimum cosine, evidence overlap, repetitions and seed for every configuration. Configuration and question execution order is shuffled deterministically from the seed. One query warm-up per configuration is excluded from benchmark measurements. Machine, Python/package versions, exact model revisions, cache use and evaluation version are saved. Repeating a run reproduces source/configuration judgments; wall-clock timings can vary with CPU load and caches.

## Ground truth and review

The dataset manager imports UTF-8 CSV/JSON and edits questions, reference answers, answerability and relevant source spans. Every gold evidence unit uses a document ID, full extracted-source SHA-256, Unicode-character half-open offsets `[start, end)`, exact quote and page membership. The dataset validator checks quotes against the original extracted text. Gold spans within a question must not overlap; merge overlapping spans into one evidence unit.

The human-reviewed flag is an explicit single-user attestation covering the question, answerability, reference answer and all evidence. A reviewer name is required. Changes to the question, reference or evidence clear this flag in the editor. Review flags are not authentication or proof that another person independently reviewed the data.

The included six-question CC0 dataset is illustrative and **unreviewed**. It contains four answerable and two unanswerable questions. Default runs exclude unreviewed annotations. Explicitly including them marks the entire run and its recommendations provisional. Unknown answerability is always excluded. A run needs at least one included answerable question with a reference answer and valid source evidence.

## Chunk-size-independent retrieval judgments

Judgments are anchored to source spans rather than chunk IDs. A passage and gold span must belong to the same validated source. A passage is relevant when

`intersection_length(passage, gold) / min(passage_length, gold_length) >= evidence_overlap`.

The default threshold is 0.5, fixed for the run. This overlap coefficient lets a smaller passage fully inside a long evidence span be relevant, and lets a larger passage containing the evidence be relevant. It does not penalize all irrelevant context in a large chunk; inspect evidence coverage and use a representative corpus before claiming a chunker is superior.

For answerable questions:

- **Precision@k:** count of relevant, non-duplicate passages in the first k ranks divided by the **requested** k. Missing slots and repeated identical document/start/end passages are not extra true positives. Original ranks are retained.
- **Recall@k:** fraction of distinct gold evidence spans for which the union of retrieved source intervals covers at least the fixed overlap threshold. Interval overlaps are merged first, so repeating or overlapping chunks cannot inflate recall above 1.
- **Reciprocal rank:** `1 / first relevant rank`, or 0 when no relevant passage is returned. MRR averages it over included answerable question/repetition measurements.
- **Evidence coverage:** mean union-covered fraction of gold spans, reported separately from thresholded recall.

These are passage precision and evidence-span recall, not document-level recall. Their denominators differ deliberately and are disclosed. Unanswerable questions have undefined P/R/MRR (null, never invented zero); they contribute to a separate retrieval-abstention rate and timing measurements. A similarity cutoff does not establish that a question is semantically answerable.

Macro averages weight each included answerable question/repetition equally. Repetitions improve timing observations but do not create new independent questions. Report unique answerable questions alongside total measurements. Complete configurations must contain the same expected question × repetition set before ranking.

Definitions are informed by the [Stanford Introduction to Information Retrieval evaluation chapter](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-in-information-retrieval-1.html). The source-span overlap and union-coverage rules above are RAGLab's explicitly versioned adaptation for comparing different chunk sizes; they should not be confused with standard document relevance judgments.

## Timings and cache policy

Retrieval latency is the existing pipeline's measured query embedding, index validation/load and FAISS search interval, after one separate warm-up. Additional wall time includes persistence overhead and is saved separately. Mean, median and 95th percentile are descriptive statistics over actual query measurements, including unanswerable questions.

Indexing time is the actual index builder's measured time for an index built during this run. By default, artifacts are rebuilt while reusable document vectors may come from the persistent embedding cache. Cache-hit counts and index-preparation wall time are recorded. A reused pre-existing ready index has no new indexing measurement (null), rather than a fabricated zero. Resumed work retains the previously measured build duration.

Do not compare a cached index build to a cold download as if the cache conditions were identical. Download/inference calls cannot safely be interrupted mid-call; cancellation is cooperative between calls and batches. Completed measurements are persisted and retained. Resume performs only missing work. A server restart marks active work interrupted; it never fabricates completion.

## Answer metrics

LLM generation is optional and disabled by default. It requires a configured provider. Without credentials, the benchmark remains fully functional for retrieval.

When actual generation succeeds for an answerable question with references, RAGLab can calculate **normalized exact match**: remove source markers, lowercase, remove punctuation/articles and collapse whitespace, then compare against reference answers. This strict text match is not general semantic correctness. Failed, missing or insufficient-context generations do not receive a made-up correctness score. The number of successfully evaluated answers is reported.

**Semantic groundedness remains not evaluated.** Existing source-ID and verbatim-quote validation establishes citation provenance, not semantic entailment. No semantic groundedness metric is emitted without a validated semantic or human evaluation method. Live provider-generated Q&A remains unverified while credentials are missing.

## Explainable optimization

Only completed configurations from one immutable dataset snapshot and one fixed run enter the optimizer. Model/chunker filters define its comparison cohort.

- Retrieval accuracy score = `0.45 × Recall@k + 0.35 × MRR + 0.20 × Precision@k`.
- Speed score = `1 - (mean_latency - cohort_min) / (cohort_max - cohort_min)`; equal latencies all score 1.
- Accuracy objective uses retrieval accuracy only.
- Speed objective uses speed only.
- Balanced objective = `0.70 × accuracy_score + 0.30 × speed_score`.

Weights are disclosed heuristics, not learned universal utility. Indexing times are reported but excluded from speed ranking because embedding-cache conditions vary. Recommendations include their inputs and unique-question sample size. Provisional annotations, a tiny corpus, timing variability, lack of held-out queries, and absence of statistical significance all limit conclusions. A top-ranked sample configuration is not a claim of general superiority.


## Phase 4 adaptive evaluation

See [PHASE4.md](PHASE4.md) for split isolation, held-out reservation, normalized objective weights, Pareto dominance, question-cluster bootstrap construction and repeatability limitations. The original Phase 3 descriptive leaderboard formula remains compatible. Adaptive search chooses from validation only and runs one frozen configuration on reserved test; test results cannot enter the adaptive analysis endpoint.
