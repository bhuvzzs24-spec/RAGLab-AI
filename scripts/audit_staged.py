"""Read the Git index only: reject runtime files, oversized blobs and likely credentials."""
import re
import subprocess
import sys
from pathlib import PurePosixPath

def git(*args):return subprocess.check_output(['git',*args])
paths=git('diff','--cached','--name-only','--diff-filter=ACMR','-z').decode().split('\0')
problems=[];count=0
patterns=[re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
          re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b'),
          re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
          re.compile(rb'\bAKIA[A-Z0-9]{16}\b')]
for path in filter(None,paths):
    p=PurePosixPath(path);count+=1
    forbidden=set(p.parts)&{'node_modules','.next','work','outputs','.venv','venv','__pycache__','data','uploads','private_uploads','model-cache'}
    if forbidden or (p.name.startswith('.env') and p.name!='.env.example') or p.suffix in {'.sqlite','.sqlite3','.db','.faiss','.npy','.npz','.safetensors','.pt','.pth','.onnx','.pem','.key'}:
        problems.append((path,'runtime/secret artifact path'))
    blob=git('show',':'+path)
    if len(blob)>5*1024*1024:problems.append((path,'blob exceeds 5 MB; inspect before committing'))
    if any(pattern.search(blob) for pattern in patterns):problems.append((path,'possible credential/private key; value not printed'))
    if re.search(rb'(?im)^\s*(?:LLM_API_KEY|OPENAI_API_KEY|HF_TOKEN|GITHUB_TOKEN)\s*=\s*[\'\"]?[A-Za-z0-9_-]{16,}',blob):problems.append((path,'possible populated credential assignment'))
if problems:
    for path,reason in problems:print(path+': '+reason)
    sys.exit(1)
print(f'PASS: inspected {count} staged source blobs; no prohibited runtime artifacts, oversized blobs or recognized credentials.')
