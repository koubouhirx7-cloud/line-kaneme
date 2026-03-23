import os
import shutil
import re

# 1. Frontend: Rename & replace API paths
html_src = 'seamless_workflow_preview.html'
html_dest = 'index.html'

if os.path.exists(html_src):
    with open(html_src, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace absolute API calls with relative API calls
    content = content.replace('http://127.0.0.1:8000/api/', '/api/')
    content = content.replace('http://127.0.0.1:8000/webhook/line', '/webhook/line')
    
    with open(html_dest, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Moved and updated frontend to {html_dest}")

# 2. vercel.json
vercel_json = """{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    },
    {
      "src": "index.html",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "api/index.py"
    },
    {
      "src": "/webhook/line",
      "dest": "api/index.py"
    },
    {
      "src": "/(.*)",
      "dest": "/index.html"
    }
  ]
}"""
with open('vercel.json', 'w', encoding='utf-8') as f:
    f.write(vercel_json)
print("Created vercel.json")

# 3. api/index.py
os.makedirs('api', exist_ok=True)
api_index = """import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from main import app
"""
with open('api/index.py', 'w', encoding='utf-8') as f:
    f.write(api_index)
print("Created api/index.py")

# 4. requirements.txt (root)
req_content = """fastapi
uvicorn
sqlalchemy
pydantic
python-dotenv
line-bot-sdk
psycopg2-binary
"""
with open('requirements.txt', 'w', encoding='utf-8') as f:
    f.write(req_content)
print("Created requirements.txt at root")

# 5. Modify backend/database.py for Postgres
db_file = 'backend/database.py'
if os.path.exists(db_file):
    with open(db_file, 'r', encoding='utf-8') as f:
        db_content = f.read()
    
    new_db_code = """import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Retrieve Vercel Postgres URL, fallback to local sqlite
SQLALCHEMY_DATABASE_URL = os.getenv("POSTGRES_URL", "sqlite:///./hubcargo.db")

# Vercel might give postgres:// instead of postgresql://
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite-specific args
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
"""
    with open(db_file, 'w', encoding='utf-8') as f:
        f.write(new_db_code)
    print("Updated backend/database.py for Postgres support")

