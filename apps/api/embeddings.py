"""Pinned local embedding models and explicit retrieval formatting."""
import os
import threading
from functools import lru_cache
import numpy as np

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
MODEL_LOCK = threading.RLock()
MODELS = {
    'minilm': {
        'id': 'minilm', 'name': 'all-MiniLM-L6-v2',
        'repository': 'sentence-transformers/all-MiniLM-L6-v2',
        'revision': '1110a243fdf4706b3f48f1d95db1a4f5529b4d41',
        'dimensions': 384, 'max_tokens': 256, 'query_prefix': '',
        'document_prefix': '', 'normalized': True, 'license': 'Apache-2.0',
    },
    'bge-small': {
        'id': 'bge-small', 'name': 'bge-small-en-v1.5',
        'repository': 'BAAI/bge-small-en-v1.5',
        'revision': '5c38ec7c405ec4b44b94cc5a9bb96e735b38267a',
        'dimensions': 384, 'max_tokens': 512,
        'query_prefix': 'Represent this sentence for searching relevant passages: ',
        'document_prefix': '', 'normalized': True, 'license': 'MIT',
    },
}
FORMAT_VERSION = 'explicit-prefix-normalized-v1'


def spec(model_id):
    if model_id not in MODELS:
        raise ValueError('Choose minilm or bge-small.')
    return MODELS[model_id]


@lru_cache(maxsize=2)
def load_model(model_id):
    import torch
    torch.set_num_threads(1)
    from sentence_transformers import SentenceTransformer
    s = spec(model_id)
    result = SentenceTransformer(s['repository'], revision=s['revision'], device='cpu',
                                 trust_remote_code=False,
                                 local_files_only=os.getenv('HF_HUB_OFFLINE') == '1')
    if result.get_sentence_embedding_dimension() != s['dimensions']:
        raise ValueError('Model dimension does not match its pinned configuration.')
    result.max_seq_length = s['max_tokens']
    return result


def encode(texts, model_id='minilm', query=False):
    s = spec(model_id)
    prefix = s['query_prefix'] if query else s['document_prefix']
    with MODEL_LOCK:
        model = load_model(model_id)
        formatted = [prefix + text for text in texts]
        # Reject query truncation; indexing splits document spans before encoding.
        if query and any(len(model.tokenizer(t, add_special_tokens=True)['input_ids']) > s['max_tokens'] for t in formatted):
            raise ValueError(f"Question is longer than {s['max_tokens']} model tokens. Shorten the question.")
        result = model.encode(formatted, prompt='', normalize_embeddings=True,
                              convert_to_numpy=True, show_progress_bar=False, batch_size=16)
    result = np.asarray(result, dtype='float32')
    if result.shape != (len(texts), s['dimensions']) or not np.isfinite(result).all():
        raise ValueError('Embedding model produced invalid vectors.')
    norms = np.linalg.norm(result, axis=1, keepdims=True)
    if (norms < 1e-8).any():
        raise ValueError('Embedding model produced a zero vector.')
    return result / norms


def split_for_model(text, model_id):
    """Character spans that fit the actual tokenizer, with no silent truncation."""
    with MODEL_LOCK:
        model = load_model(model_id)
        encoded = model.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True,
                                  truncation=False, verbose=False)
        limit = spec(model_id)['max_tokens'] - model.tokenizer.num_special_tokens_to_add(pair=False)
    offsets = encoded['offset_mapping']
    for i in range(0, len(offsets), limit):
        window = offsets[i:i+limit]
        if window:
            yield window[0][0], window[-1][1], len(window)


def encode_untruncated(texts, model_id):
    """Length-weighted pooling for boundary comparisons of oversized sentences."""
    result=[]
    for text in texts:
        spans=list(split_for_model(text,model_id))
        pieces=[text[a:b] for a,b,_ in spans]
        values=encode(pieces,model_id)
        value=np.average(values,axis=0,weights=[count for _,_,count in spans])
        result.append(value/max(np.linalg.norm(value),1e-12))
    return np.asarray(result,dtype='float32')
