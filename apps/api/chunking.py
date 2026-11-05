import re
import numpy as np


def spans(text):
    return list(re.finditer(r'\S+', text))


def chunk_text(text, strategy='fixed', budget=120, overlap=20, threshold=0.55, encode=None):
    tokens = spans(text)
    if not tokens:
        return []
    def item(start, end):
        return {'text': text[start:end], 'start': start, 'end': end,
                'tokens': len(spans(text[start:end]))}
    if strategy == 'fixed':
        result = []
        for i in range(0, len(tokens), budget-overlap):
            end = min(i+budget, len(tokens))
            result.append(item(tokens[i].start(), tokens[end-1].end()))
            if end == len(tokens):
                break
        return result
    sentences = list(re.finditer(r'.+?(?:[.!?]+(?=\s|$)|$)', text, re.S))
    units = []
    for sentence in sentences:
        ts = spans(sentence.group())
        for i in range(0, len(ts), budget):
            group = ts[i:i+budget]
            if group:
                units.append((sentence.start()+group[0].start(), sentence.start()+group[-1].end()))
    embeddings = encode([text[a:b] for a,b in units]) if strategy == 'semantic' and units else None
    result, start, end, size = [], None, None, 0
    for i, (a,b) in enumerate(units):
        count = len(spans(text[a:b]))
        boundary = False
        if embeddings is not None and i:
            x,y = embeddings[i-1], embeddings[i]
            boundary = float(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y)+1e-12)) < threshold
        if start is not None and (size+count > budget or boundary):
            result.append(item(start,end))
            start, size = None, 0
        if start is None:
            start = a
        end, size = b, size+count
    if start is not None:
        result.append(item(start,end))
    return result
