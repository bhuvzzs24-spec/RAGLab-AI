# Phase 4 vs Research Upgrade: Comparative Results

## 1. Objective

Compare Phase 4 and Research Upgrade using matched
questions and configurations.

## 2. Experimental Results

| Metric | Phase 4 | Research Upgrade |
|---|---:|---:|
| Precision@K | 0.3457 | 0.3457 |
| Recall@K | 1.0000 | 1.0000 |
| MRR | 1.0000 | 1.0000 |
| Evidence Coverage | 1.0000 | 1.0000 |
| Latency (ms) | 126.5455 | 105.4521 |
| Wall Latency (ms) | 127.3593 | 106.0339 |

## 3. Observations

- Retrieval quality metrics remained unchanged.
- Average latency decreased by 16.67%.
- Wall-clock latency decreased by 16.74%.
- The comparison included 72 matched
  configuration-question pairs.
- Quality metrics used 54 answerable matched pairs.
- Unanswerable questions were excluded from
  retrieval-quality calculations.

## 4. Limitations

- The evaluation dataset is small.
- Existing annotations have not undergone
  independent human review.
- The results are preliminary and do not establish
  statistical significance.
- Further testing on larger independent datasets
  is required.

## 5. Conclusion

Research Upgrade demonstrated lower measured
retrieval latency while maintaining the same
measured retrieval-quality metrics as Phase 4
on the evaluated sample.

These results should be treated as preliminary
experimental observations.
