import os
import sys

# Add the current directory to python path if not already there
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine, Base
import models

def seed_db():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Check if partners already exist
    existing_partners = db.query(models.Partner).count()
    if existing_partners == 0:
        print("Seeding partners...")
        partners = [
            models.Partner(name="ファーストリンク", line_group_id=None, icon_emoji="🏙️", is_active=True),
            models.Partner(name="サンプル運輸株式会社", line_group_id=None, icon_emoji="🚚", is_active=True),
            models.Partner(name="関西ロジスティクス", line_group_id=None, icon_emoji="🚄", is_active=True)
        ]
        db.add_all(partners)
        db.commit()
        print(f"Added {len(partners)} partners.")
    else:
        print(f"Database already contains {existing_partners} partners.")
        
    db.close()
    print("Seeding complete.")

if __name__ == "__main__":
    seed_db()
