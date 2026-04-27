with open("backend/main.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "@app.on_event(\"startup\")" in line:
        skip = True
    if skip and line.strip() == "pass":
        skip = False
        continue
    if not skip:
        new_lines.append(line)

content = "".join(new_lines)


migration_code = """
models.Base.metadata.create_all(bind=engine)

from sqlalchemy import text
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE inquiries ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE"))
except Exception:
    pass
"""

content = content.replace("models.Base.metadata.create_all(bind=engine)", migration_code)

with open("backend/main.py", "w") as f:
    f.write(content)
