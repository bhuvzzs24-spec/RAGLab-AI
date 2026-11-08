# RAGLab AI – Aggregate Experimental Analysis

**Student:** Priyanka B M  
**SRN:** PES1UG24AM207  
**Benchmark Run:** 4a7b2bb4-70e1-4100-bdfc-b200b94843d1

## 1. Experiment Overview

The experiment evaluated 18 configurations using two embedding models:
all-MiniLM-L6-v2 and bge-small-en-v1.5.

Three chunking strategies were tested: fixed, sentence and semantic.
Each strategy was evaluated at 64, 128 and 256-word chunk budgets.

The run completed all 18 configurations and recorded 72 measurements.

## 2. Embedding Model Comparison

| Model | Precision@3 | Recall@3 | MRR | Avg Latency (ms) | Avg Indexing (ms) |
|---|---:|---:|---:|---:|---:|
| MiniLM | 0.3457 | 1.000 | 1.000 | 79.12 | 89.11 |
| BGE-small | 0.3457 | 1.000 | 1.000 | 83.64 | 108.33 |

MiniLM showed lower average retrieval latency and indexing time.
Both models produced identical average precision, recall and MRR.

## 3. Chunking Strategy Comparison

| Strategy | Precision@3 | Recall@3 | MRR | Avg Latency (ms) | Avg Indexing (ms) |
|---|---:|---:|---:|---:|---:|
| Fixed | 0.3704 | 1.000 | 1.000 | 81.29 | 74.09 |
| Sentence | 0.3333 | 1.000 | 1.000 | 80.04 | 74.78 |
| Semantic | 0.3333 | 1.000 | 1.000 | 82.82 | 147.28 |

Fixed chunking achieved the highest average precision.
Sentence chunking showed the lowest average retrieval latency.
Semantic chunking had the highest average indexing time.

## 4. Chunk Size Comparison

| Chunk Size | Precision@3 | Recall@3 | MRR | Avg Latency (ms) | Avg Indexing (ms) |
|---|---:|---:|---:|---:|---:|
| 64 words | 0.3704 | 1.000 | 1.000 | 81.79 | 94.62 |
| 128 words | 0.3333 | 1.000 | 1.000 | 82.23 | 102.56 |
| 256 words | 0.3333 | 1.000 | 1.000 | 80.13 | 98.98 |

The 64-word budget had the highest average precision.
The 256-word budget had the lowest average retrieval latency.

## 5. Best Ranked Configuration

The highest-ranked configuration was:

- Embedding model: all-MiniLM-L6-v2
- Chunking strategy: Sentence
- Chunk budget: 128 words
- Precision@3: 0.3333
- Recall@3: 1.000
- MRR: 1.000
- Mean retrieval latency: 75.62 ms
- Balanced optimizer score: 0.9067

This configuration ranked first under the benchmark's balanced accuracy-speed objective.

## 6. Interpretation

The results indicate that embedding model, chunking strategy and chunk
size affect retrieval performance and computational cost differently.

MiniLM showed lower average latency than BGE-small.
Fixed chunking achieved higher average precision, while sentence
chunking offered competitive retrieval speed.
Semantic chunking incurred higher indexing overhead.

No single strategy or chunk size dominated every metric.

## 7. Limitations

- The evaluation used one fictional CC0 sample source document.
- Only four validation questions were evaluated per configuration.
- There were three unique answerable questions and one unanswerable question.
- Only one repetition was used.
- Generation was disabled.
- Answer exact match and semantic groundedness were not evaluated.
- The results are exploratory and do not establish statistical significance.

## 8. Future Work

Future evaluation should use a larger and more diverse approved corpus,
50–100 or more reviewed questions, multiple repetitions, and a held-out
test set. Generation quality and groundedness should be evaluated
separately when answer generation is enabled.

## 9. Conclusion

The experiment demonstrates a working comparative retrieval benchmark
across 18 configurations. MiniLM Sentence with a 128-word budget achieved
the highest balanced optimizer score in this run. However, aggregate
results show that fixed chunking achieved higher average precision,
highlighting the importance of evaluating multiple metrics rather than
selecting a configuration using rank alone.
