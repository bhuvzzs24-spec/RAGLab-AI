
"""Bounded PDF extraction worker. No imports of models, application state or credentials."""
import json
import sys

MAX_TEXT = 2_000_000
MAX_PDF_SIZE = 10 * 1024 * 1024


def extract(raw):
    import pymupdf as fitz

    with fitz.open(stream=raw, filetype='pdf') as pdf:
        if pdf.needs_pass:
            raise ValueError('Unlock the encrypted PDF before uploading')

        if len(pdf) > 500:
            raise ValueError('PDF exceeds the 500-page limit')

        pages = []
        extracted = 0
        decoded = 0
        seen = set()

        for page in pdf:
            for xref in page.get_contents():
                if xref in seen:
                    continue

                seen.add(xref)
                decoded += len(pdf.xref_stream(xref) or b'')

                if decoded > 16 * 1024 * 1024:
                    raise ValueError(
                        'Decoded PDF page streams exceed 16 MB. '
                        'Split or simplify the PDF'
                    )

            value = page.get_text(
                'text',
                flags=fitz.TEXTFLAGS_TEXT & ~fitz.TEXT_PRESERVE_IMAGES
            )

            extracted += len(value)

            if extracted > MAX_TEXT:
                raise ValueError(
                    'Extracted text exceeds 2 million characters'
                )

            pages.append(value)

        return pages


if __name__ == '__main__':
    try:
        # Apply operating-system resource limits on Linux.
        # Windows uses the parent process timeout and extraction limits.
        if sys.platform.startswith('linux'):
            import resource

            resource.setrlimit(
                resource.RLIMIT_CPU, (12, 15)
            )
            resource.setrlimit(
                resource.RLIMIT_AS,
                (768 * 1024**2, 768 * 1024**2)
            )

        raw = sys.stdin.buffer.read(MAX_PDF_SIZE + 1)

        if len(raw) > MAX_PDF_SIZE:
            raise ValueError('PDF exceeds 10 MB')

        print(json.dumps({'pages': extract(raw)}))

    except Exception as exc:
        print(json.dumps({'error': str(exc)[:180]}))
        sys.exit(1)
