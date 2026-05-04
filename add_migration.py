with open("backend/main.py", "r") as f:
    content = f.read()

migration_code = """
from sqlalchemy import text
@app.on_event("startup")
def startup_event():
    with engine.begin() as conn:
        try:
            # PostgreSQL syntax: DEFAULT FALSE, SQLite: DEFAULT 0
            conn.execute(text("ALTER TABLE inquiries ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE"))
        except Exception:
            pass
"""

if "ALTER TABLE inquiries ADD COLUMN reminder_sent" not in content:
    # insert before app = FastAPI()
    content = content.replace("app = FastAPI()", "app = FastAPI()\n" + migration_code)
    
    with open("backend/main.py", "w") as f:
        f.write(content)
