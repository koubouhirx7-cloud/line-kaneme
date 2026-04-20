import os
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger("hubcargo.db")

# Retrieve Vercel Postgres or Neon URL, fallback to local sqlite
SQLALCHEMY_DATABASE_URL = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL") or "sqlite:////tmp/hubcargo.db"

# Vercel might give postgres:// instead of postgresql://
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres"):
    # Strip URL query parameters (like ?options=... & sslmode=...) because pg8000 rejects 'channel_binding' and others
    if "?" in SQLALCHEMY_DATABASE_URL:
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.split("?")[0]
        
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)
    
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    connect_args = {"ssl_context": ctx}
    # NullPool: サーバーレス環境ではコネクションプールを使わず毎回新規接続
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args=connect_args,
        poolclass=NullPool,
        pool_pre_ping=True,  # 使用前に接続を確認
    )
else:
    connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args=connect_args
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Neonのオートサスペンド復帰時のInterfaceErrorをリトライで吸収する"""
    max_retries = 2
    for attempt in range(max_retries + 1):
        db = SessionLocal()
        try:
            yield db
            return
        except Exception as e:
            db.close()
            err_name = type(e).__name__
            # Neon cold-start: pg8000 network error → リトライ
            if attempt < max_retries and ("InterfaceError" in err_name or "OperationalError" in err_name):
                logger.warning(f"DB connection error (attempt {attempt+1}/{max_retries}), retrying in 1s: {e}")
                time.sleep(1)
            else:
                raise
        finally:
            try:
                db.close()
            except Exception:
                pass
