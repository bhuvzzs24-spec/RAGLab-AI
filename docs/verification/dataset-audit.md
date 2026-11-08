# Evaluation Dataset Audit

## Audit scope

Existing files:
- apps/api/samples/benchmark-sample.json
- apps/api/samples/adaptive-sample.json

Source documents:
- campus-guide.txt
- retrieval-notes.md
- adaptive-campus.txt

## Observed dataset statistics

| Dataset | Questions | Train | Validation | Test | Human reviewed |
|---|---:|---:|---:|---:|---:|
| Benchmark sample | 6 | 0 | 0 | 0 | 0 |
| Adaptive sample | 12 | 4 | 4 | 4 | 0 |
| Total | 18 | 4 | 4 | 4 | 0 |

The six benchmark questions have no assigned split.

## Preliminary validation results

| Check | Result |
|---|---|
| JSON parsing | PASS |
| Evidence quote exact-match check | PASS (18 records) |
| Duplicate question check | No exact duplicates found |
| Adaptive split presence | PASS |
| Benchmark split assignment | INCOMPLETE |
| Human review | NOT COMPLETED |
| Independent answer correctness | NOT VERIFIED |
| Dataset representativeness | INSUFFICIENT |

## Provenance

The repository sample licence identifies the three original sample documents as CC0 material. The adaptive campus document contains fictional demonstration policies and must not be represented as real university guidance.

## Limitations

The available source corpus is small. Eighteen questions do not establish broad benchmark coverage. Exact quotation matching does not establish that a reference answer is complete or correct.

All existing annotations remain provisional pending independent human review.

## Next actions

1. Obtain additional approved source documents.
2. Audit reference answers and answerability labels.
3. Prepare additional evidence-backed questions.
4. Preserve independent validation and held-out test groups.
5. Obtain genuine human review.
6. Re-run benchmarks only after the evaluation dataset is approved.
