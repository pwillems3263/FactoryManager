import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

DB_CONFIGS = {
    "prod": {
        "host":     os.getenv("DB_PROD_HOST", os.getenv("DB_HOST", "localhost")),
        "port":     os.getenv("DB_PROD_PORT", os.getenv("DB_PORT", "5432")),
        "name":     os.getenv("DB_PROD_NAME", "FactoryManager_prod"),
        "user":     os.getenv("DB_PROD_USER", os.getenv("DB_USER", "postgres")),
        "password": os.getenv("DB_PROD_PASSWORD", os.getenv("DB_PASSWORD", "")),
        "label":    "PRODUCTION",
        "color":    "red",
    },
    "test": {
        "host":     os.getenv("DB_TEST_HOST", os.getenv("DB_HOST", "localhost")),
        "port":     os.getenv("DB_TEST_PORT", os.getenv("DB_PORT", "5432")),
        "name":     os.getenv("DB_TEST_NAME", "FactoryManager_dev"),
        "user":     os.getenv("DB_TEST_USER", os.getenv("DB_USER", "postgres")),
        "password": os.getenv("DB_TEST_PASSWORD", os.getenv("DB_PASSWORD", "")),
        "label":    "TEST",
        "color":    "orange",
    },
}

def _make_url(cfg):
    return f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['name']}"

_engines = {}
_session_factories = {}

for db_key, cfg in DB_CONFIGS.items():
    engine = create_engine(_make_url(cfg), pool_size=10, max_overflow=5, pool_timeout=30, pool_pre_ping=True)
    _engines[db_key] = engine
    _session_factories[db_key] = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_session_factory(db_key: str):
    return _session_factories.get(db_key, _session_factories["test"])

def get_db_info(db_key: str) -> dict:
    return DB_CONFIGS.get(db_key, DB_CONFIGS["test"])

def get_db_for_key(db_key: str):
    factory = get_session_factory(db_key)
    db = factory()
    try:
        yield db
    finally:
        db.close()

# Backward compatibility — used by routers via Depends(get_db)
# Real per-request DB selection happens via auth.py
SessionLocal = _session_factories["test"]

def get_db():
    db = _session_factories["test"]()
    try:
        yield db
    finally:
        db.close()
