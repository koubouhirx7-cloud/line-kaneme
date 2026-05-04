import sys
import os
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

try:
    from main import app as fastapi_app
except Exception as e:
    err = traceback.format_exc()
    async def fastapi_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 500, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": f"Import Error:\n{err}".encode()})

async def app(scope, receive, send):
    try:
        await fastapi_app(scope, receive, send)
    except Exception as e:
        err = traceback.format_exc()
        await send({"type": "http.response.start", "status": 500, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": f"ASGI Error:\n{err}".encode()})
