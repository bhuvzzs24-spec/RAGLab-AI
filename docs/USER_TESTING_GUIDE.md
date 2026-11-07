# RAGLab AI — User Testing Guide

## 1. Introduction

This guide explains how to run and manually test RAGLab AI. It helps users verify the application's document ingestion, retrieval, benchmarking and evaluation workflows.

## 2. Prerequisites

- Python 3.13 or compatible project-supported version
- Node.js 20 or compatible project-supported version
- npm
- Git
- FAISS and Python dependencies listed in the project requirements

## 3. Starting the Application

1. Clone the RAGLab AI repository.
2. Install the backend dependencies using the project's documented setup instructions.
3. Configure the required environment variables using `.env.example`.
4. Start the backend using the documented FastAPI command.
5. Install frontend dependencies using `npm ci`.
6. Start the frontend using `npm run dev`.
7. Open the local frontend URL in a browser.

## 4. Manual Testing Checklist

### Document Upload
- Upload a supported document.
- Verify that the document appears in the application.
- Check that invalid file types are handled appropriately.

### Document Processing
- Verify that uploaded documents are processed.
- Check chunk creation and source information.
- Verify that source references are retained.

### Retrieval
- Submit a research question.
- Verify that relevant document chunks are retrieved.
- Inspect the displayed evidence and source references.

### Benchmarking
- Run the available benchmark configurations.
- Inspect Precision@K, Recall@3 and MRR.
- Compare retrieval latency across configurations.

### Optimization
- Run the optimizer.
- Inspect its recommended configuration.
- Verify that the recommendation is based on the available benchmark measurements.

### Reports and Exports
- Test CSV export.
- Test PDF export.
- Verify that exported information corresponds to the displayed results.

## 5. Existing Automated Verification

According to the project's Phase 4 verification record:

- 61 backend tests passed.
- Frontend production build passed.
- TypeScript checks passed.
- 10 desktop/mobile browser tests passed.
- Real embedding-model and FAISS persistence checks passed.

## 6. Known Limitations

- Live credentialed LLM Q&A has not been tested.
- Semantic answer correctness and groundedness have not been evaluated.
- Docker execution has not been tested.
- Human review of benchmark labels remains necessary.
- Cloud deployment has not yet been verified.

## 7. Conclusion

This guide provides a practical checklist for manually exploring and testing RAGLab AI. Testing results should be recorded with screenshots and actual execution evidence. Features not verified should not be reported as successfully tested.