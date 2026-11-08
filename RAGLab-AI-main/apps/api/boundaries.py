"""Explicit local-app request bounds, not authentication or a general sandbox."""
from urllib.parse import urlsplit
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException

MAX_REQUEST=12*1024*1024

def allowed_origins(value):
    origins=[v.strip().rstrip('/') for v in value.split(',') if v.strip()]
    for origin in origins:
        parsed=urlsplit(origin)
        try:parsed.port
        except ValueError:raise ValueError('CORS_ORIGINS contains an invalid port.')
        if '*' in origin or parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('CORS_ORIGINS must contain explicit HTTP(S) origins without paths, wildcards or credentials.')
    return origins

class RequestBoundary:
    def __init__(self,app,origins):self.app,self.origins=app,set(origins)
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers={k.decode('latin1').lower():v.decode('latin1') for k,v in scope['headers']}
        try:length=int(headers.get('content-length','0'))
        except ValueError:return await JSONResponse({'detail':'Invalid Content-Length.'},400)(scope,receive,send)
        if length<0 or length>MAX_REQUEST:return await JSONResponse({'detail':'Request exceeds the 12 MB total body limit.'},413)(scope,receive,send)
        origin=headers.get('origin');own=f"{scope['scheme']}://{headers.get('host','')}"
        if scope['method'] not in ('GET','HEAD','OPTIONS') and origin and origin not in self.origins|{own}:
            return await JSONResponse({'detail':'This browser origin is not allowed to modify the local workspace.'},403)(scope,receive,send)
        seen=0
        async def limited():
            nonlocal seen
            message=await receive()
            if message['type']=='http.request':
                seen+=len(message.get('body',b''))
                if seen>MAX_REQUEST:raise HTTPException(413,'Request exceeds the 12 MB streaming body limit.')
            return message
        await self.app(scope,limited,send)
