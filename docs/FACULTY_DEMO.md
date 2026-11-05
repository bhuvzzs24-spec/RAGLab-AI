# Faculty demonstration guide

Allow 10-15 minutes. Install dependencies and download both real models before presenting; test once with the network disconnected if an offline demonstration is planned. Keep the API terminal visible for actionable errors. No LLM credentials are needed.

1. **Overview:** explain local data, actual measurements and reproducibility. Show all original nine pages plus Datasets and Benchmarks. Switch theme and demonstrate a mobile viewport.
2. **Documents:** upload the supplied CC0 TXT/MD or a legally usable text PDF. Preview extracted pages. Explain safe type/size validation and the limitation that scanned image PDFs need OCR, which is not provided.
3. **Chunking Lab:** compare fixed overlap, sentence boundaries and semantic similarity splits. Inspect exact character boundaries, overlap and measured times. Save an experiment.
4. **Embeddings:** create MiniLM and BGE indexes; inspect 384-dimensional normalized vector statistics, pinned revisions, actual PCA and persisted index status. Explain BGE query instruction formatting.
5. **RAG Playground:** ask a supported question, compare two configurations and click original-source highlights. Ask an unsupported question; cosine retrieval alone does not prove answerability. With no provider configured, demonstrate honest retrieval-only status. Do not describe provider-contract unit tests as live Q&A.
6. **Datasets:** load the split-ready sample. Point out **0 human-reviewed labels**. Click a gold quote, inspect the source, select a new exact span if appropriate, record reviewer and notes, then explicitly attest only after checking. Show pending-review filtering and train/validation/test fields. Explain independent question/evidence groups and semantic-duplicate limitations.
7. **Benchmarks:** run the preserved 18-configuration matrix or use a completed local run. Show actual progress, cancellation/resume, source-span P@k/R@k/MRR, latency, indexing time, heatmap and comparisons. No metric is a hardcoded score.
8. **Adaptive search:** choose the split-ready dataset, explicitly include provisional labels for this illustrative sample, set accuracy weight/latency constraint, run search. Show validation Pareto trade-offs, uncertainty and frozen selection seal. Only one configuration is evaluated on reserved test. A second tuning search on those test questions is refused. More independent reviewed questions are needed for claims.
9. **Reports:** download PDF, CSV and JSON. Explain fixed top-k, source hashes, seed, model revisions, unavailable semantic groundedness and small-sample limitations. Open the actual PDF charts and per-query CSV.
10. **Conclusion:** describe what is implemented versus future work: reviewed domain data, credentialed live generation validation, calibrated semantic evaluation, authentication and durable distributed workers.

If a demonstration search already reserved the sample test questions, resume/show that completed search. Use genuinely new independent questions for another tuning study; changing dataset names or importing the same questions does not create unseen evidence. To reset only disposable demo data, use a new empty RAGLAB_DATA_DIR after stopping the API; never remove a research database.

Verification artifacts in `docs/verification/` are actual execution evidence with explicit provisional labels. Report latency as host-specific. A perfect recall on three illustrative answerable test questions is not a statistical superiority result.
