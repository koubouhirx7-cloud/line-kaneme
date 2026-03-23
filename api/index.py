import sys
import os

try:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
    from main import app
except Exception as e:
    from fastapi import FastAPI
    import traceback
    
    app = FastAPI()
    err_str = traceback.format_exc()
    
    @app.api_route("/{path_name:path}", methods=["GET", "POST", "OPTIONS"])
    def catch_all(path_name: str):
        return {"crashing_error": str(e), "traceback": err_str}

