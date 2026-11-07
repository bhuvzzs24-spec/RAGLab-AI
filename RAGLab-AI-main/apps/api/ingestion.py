"""File-validation boundary; CPU/memory intensive parsing stays out of the API process."""
import json,os,subprocess,sys,unicodedata
from pathlib import Path

def safe_name(filename):
    name=Path((filename or '').replace('\\','/')).name
    name=''.join(c for c in name if not unicodedata.category(c).startswith('C')).strip()
    if not name or len(name)>180:raise ValueError('Use a non-empty filename no longer than 180 characters')
    return name

def extract_pages(raw,extension):
    if extension=='.pdf':
        if not raw.startswith(b'%PDF-'):raise ValueError('PDF signature is missing')
        try:
            worker=subprocess.run([sys.executable,str(Path(__file__).with_name('pdf_extract.py'))],input=raw,capture_output=True,
                timeout=25,env={'PATH':os.defpath,'LANG':'C.UTF-8','PYTHONIOENCODING':'utf-8','OMP_NUM_THREADS':'1'})
        except subprocess.TimeoutExpired:raise ValueError('PDF extraction exceeded 25 seconds. Split or simplify this file before retrying')
        try:body=json.loads(worker.stdout)
        except (ValueError,UnicodeError):raise ValueError('PDF extraction exceeded a resource limit or the parser failed. Split or simplify the PDF')
        if worker.returncode or body.get('error'):raise ValueError(body.get('error') or 'PDF parser failed')
        return body['pages']
    if raw.startswith((b'%PDF-',b'PK\x03\x04',b'MZ')):raise ValueError('File content does not match a plain-text document')
    text=raw.decode('utf-8-sig')
    if any(ord(c)<32 and c not in '\n\r\t' for c in text) or '\x7f' in text:raise ValueError('Binary/control-character content is not supported')
    return [text]


def csv_safe(value):
    # Spreadsheet programs treat these prefixes as formulas; JSON is the lossless export.
    if isinstance(value,str) and value.lstrip(' ').startswith(('=','+','-','@','\t','\r','\n')):return "'"+value
    return value
