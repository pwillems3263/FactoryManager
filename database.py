"""
database.py
-----------
Initialisation du moteur SQLAlchemy.
Les paramètres de connexion sont lus depuis le fichier .env via db_config.py.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from db_config import get_db_url

engine = create_engine(
    get_db_url(),
    pool_size=3,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()