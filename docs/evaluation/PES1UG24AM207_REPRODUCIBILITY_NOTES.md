# RAGLab AI – Reproducibility Notes

**Student:** Priyanka B M  
**SRN:** PES1UG24AM207  
**Project:** Comparative Analysis of Chunking Strategies and Embedding Models for RAG Retrieval

## 1. Benchmark Identification

- Dataset ID: 35ea593c-637b-42e7-810b-96647a56a617
- Benchmark run ID: 4a7b2bb4-70e1-4100-bdfc-b200b94843d1
- Run name: Priyanka Reviewed Dataset Smoke Test
- Run status: Completed
- Configurations completed: 18/18
- Measurements recorded: 72/72
- Failed configurations: 0

## 2. Dataset Details

- Total questions: 12
- Training questions: 4
- Validation questions: 4
- Test questions: 4
- Answerable questions: 10
- Unanswerable questions: 2
- Validation questions used in this benchmark: 4
- Answerable validation questions: 3
- Unanswerable validation questions: 1
- Dataset review: 12/12 questions reviewed; 0 rejected.

The dataset uses a fictional sample campus document. It must not be interpreted as actual PES University policy.

## 3. Experimental Configurations

The benchmark compared:

- Chunking strategies: Fixed, Sentence, Semantic
- Embedding models: all-MiniLM-L6-v2 and bge-small-en-v1.5
- Chunk sizes: 64, 128 and 256 words

Total configurations: 3 × 2 × 3 = 18.

## 4. Embedding Model Details

### MiniLM
- Model: sentence-transformers/all-MiniLM-L6-v2
- Revision: 1110a243fdf4706b3f48f1d95db1a4f5529b4d41
- Dimensions: 384
- License: Apache-2.0

### BGE-small
- Model: BAAI/bge-small-en-v1.5
- Revision: 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
- Dimensions: 384
- License: MIT

## 5. Benchmark Settings

- Retrieval top-k: 3
- Repetitions: 1
- Minimum score: 0.2
- Evidence overlap threshold: 0.5
- Semantic threshold: 0.55
- Overlap ratio: 0.15
- Random seed: 7
- Include unreviewed questions: false
- Generate answers: false
- Rebuild indexes: true

## 6. Evaluation Metrics

- Precision@3
- Recall@3
- Mean Reciprocal Rank (MRR)
- Retrieval latency
- Indexing time
- Unanswerable-question abstention rate

Precision@3 measures the proportion of the three requested retrieved passages that are relevant. Missing ranks count as non-relevant.

Recall@3 measures the fraction of distinct validated evidence spans covered by the retrieved passages.

MRR measures the reciprocal rank of the first relevant passage, averaged over answerable questions.

Unanswerable questions are assessed separately through retrieval abstention rate.

## 7. Scoring Method

Optimizer retrieval accuracy score:

0.45 × Recall + 0.35 × MRR + 0.20 × Precision

Speed score is normalized within the experiment cohort:

1 − (mean latency − cohort minimum) / (cohort maximum − cohort minimum)

Balanced score:

0.70 × retrieval accuracy score + 0.30 × speed score

Indexing time is reported separately and is not included in the speed score.

## 8. Runtime Environment

- Python: 3.12.9
- Platform: Darwin arm64
- sentence-transformers: 6.2.0
- faiss-cpu: 1.15.1
- NumPy: 2.5.4
- PyTorch: 2.15.0

## 9. Reproduction

From the repository root:

1. Activate the Python virtual environment.
2. Start the API using the documented project command.
3. Open the API documentation at http://127.0.0.1:8000/docs.
4. Select the reviewed dataset and configure the same chunking strategies, embedding models, chunk sizes and benchmark settings.
5. Run the benchmark and export the results.
6. Compare the exported measurements with the archived benchmark export.

Archived benchmark evidence:

- docs/verification/PES1UG24AM207_benchmark_export.json
- docs/evaluation/PES1UG24AM207_configuration_comparison.csv

The archived run ID and dataset ID above identify the specific experiment documented here.

## 10. Limitations

- Only four validation questions were used in this benchmark.
- Only three of those questions were answerable.
- The experiment used one repetition.
- Results are exploratory point estimates, not statistically significant findings.
- The sample dataset is fictional and is not representative of a real university knowledge base.
- Answer generation was disabled.
- Exact-match and groundedness scores were not evaluated.
- Retrieval results do not establish the correctness of generated answers.
- Hardware and runtime conditions can affect latency.

## 11. Reproducibility Caution

A future run may produce different latency measurements due to hardware, caching, dependency versions and runtime conditions. Exact reproduction requires matching the dataset snapshot, model revisions, configuration settings and software environment.
