"""FAISS-only subprocess: never imports Torch; persists real FAISS binary indexes."""
import json
import sys
from pathlib import Path
import numpy as np
import faiss


def execute(payload):
    faiss.omp_set_num_threads(1)
    action = payload.get('action', 'legacy')
    if action == 'build':
        vectors = np.load(payload['vectors_path'], allow_pickle=False).astype('float32')
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, payload['index_path'])
        return {'count': index.ntotal, 'dimensions': index.d}
    if action == 'search':
        index = faiss.read_index(payload['index_path'])
        query = np.asarray(payload['query'], dtype='float32')
        if index.d != query.shape[1] or index.ntotal != payload['count']:
            raise ValueError('Index dimensions or vector count mismatch. Rebuild the index.')
    else:  # Phase 1 helper contract
        vectors = np.asarray(payload['vectors'], dtype='float32')
        query = np.asarray(payload['query'], dtype='float32')
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
    scores, indices = index.search(query, min(payload['k'], index.ntotal))
    return {'scores': scores[0].tolist(), 'indices': indices[0].tolist()}

if __name__ == '__main__':
    print(json.dumps(execute(json.load(sys.stdin))))
