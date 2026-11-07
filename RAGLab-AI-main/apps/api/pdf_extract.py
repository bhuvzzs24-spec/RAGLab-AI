"""Bounded PDF extraction worker. No imports of models, application state or credentials."""
import json,sys
MAX_TEXT=2_000_000

def extract(raw):
    import pymupdf as fitz
    with fitz.open(stream=raw,filetype='pdf') as pdf:
        if pdf.needs_pass:raise ValueError('Unlock the encrypted PDF before uploading')
        if len(pdf)>500:raise ValueError('PDF exceeds the 500-page limit')
        pages=[];extracted=0;decoded=0;seen=set()
        for page in pdf:
            for xref in page.get_contents():
                if xref in seen:continue
                seen.add(xref);decoded+=len(pdf.xref_stream(xref) or b'')
                if decoded>16*1024*1024:raise ValueError('Decoded PDF page streams exceed 16 MB. Split or simplify the PDF')
            value=page.get_text('text',flags=fitz.TEXTFLAGS_TEXT & ~fitz.TEXT_PRESERVE_IMAGES)
            extracted+=len(value)
            if extracted>MAX_TEXT:raise ValueError('Extracted text exceeds 2 million characters')
            pages.append(value)
        return pages

if __name__=='__main__':
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(12,15))
        if sys.platform.startswith('linux'):resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2))
        raw=sys.stdin.buffer.read(10*1024*1024+1)
        if len(raw)>10*1024*1024:raise ValueError('PDF exceeds 10 MB')
        print(json.dumps({'pages':extract(raw)}))
    except Exception as exc:
        print(json.dumps({'error':str(exc)[:180]}));sys.exit(1)
