# Evaluation Dataset Schema

## Purpose
Documents the structure of the RAGLab AI evaluation dataset.

## Question fields

| Field | Description |
|---|---|
| id | Unique question identifier |
| question | Evaluation question |
| reference_answer | Expected answer |
| reference_answers | Alternative accepted answers, if supported |
| answerability | Answerable or unanswerable |
| split | Train, validation or test |
| group_id | Independent question-group identifier |
| human_reviewed | Human approval indicator |
| annotation_origin | Source of annotation |
| relevant_spans | Supporting source passages |

## Evidence fields

| Field | Description |
|---|---|
| document_name | Original source document |
| quote | Exact supporting passage |
| document_id | Repository document identifier, if available |
| start / end | Source offsets, if available |
| source_sha256 | Source integrity hash, if available |

## Review requirements

- Answerable questions require a reference answer and supporting evidence.
- Unanswerable questions must not contain fabricated answers or supporting evidence.
- Human approval requires actual source inspection.
- Imported review flags are not proof of human review.
- Validation and held-out test groups must remain separate.
- Repeated questions must not be counted as independent samples.

## Current status

The existing sample datasets are provisional demonstration data.
They are not approved research ground truth.
