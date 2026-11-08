# Retrieval research notes

This original sample is dedicated to the public domain under CC0 1.0.

Retrieval augmented generation connects a question to relevant source passages. A retriever searches a document collection before a language model produces a response. Citations help readers verify the source of an answer.

Chunking divides long documents into smaller passages. Fixed-size chunking uses a token budget and can repeat tokens at the boundary. Overlap preserves context but increases index size. Sentence chunking preserves complete sentences whenever they fit the budget.

Semantic chunking compares sentence embeddings. A low cosine similarity between adjacent sentences can indicate a topic boundary. The threshold controls sensitivity. A larger threshold produces more boundaries.

University libraries organize research papers by subject and publication date. Students should record the source and license of every dataset. Evaluation questions should be separate from development questions.

Retrieval latency measures elapsed search time. Recall at k measures whether relevant material occurs in the top k results. A benchmark must use real relevance judgments. Chunk counts alone cannot measure answer quality.
