import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# Attempt connection to PostgreSQL, with graceful fallback to SQLite
is_pgvector_active = False

try:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    is_pgvector_active = True
    logger.info("Connected to PostgreSQL with pgvector extension enabled.")
except Exception as e:
    if settings.USE_SQLITE_FALLBACK:
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sqlite_file = os.path.join(base_dir, "documind.db").replace("\\", "/")
        sqlite_url = f"sqlite:///{sqlite_file}"
        engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        is_pgvector_active = False
    else:
        raise e

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Import models so tables are registered with Base.metadata
    from app.models import user, document  # noqa: F401
    Base.metadata.create_all(bind=engine)
