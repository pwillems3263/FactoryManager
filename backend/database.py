"""
backend/database.py
-------------------
Initialisation SQLAlchemy pour FastAPI — multi-utilisateurs simultanés.
Connection pool dimensionné pour le web.
Les credentials viennent uniquement des variables d'environnement (.env serveur).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()  # charge backend/.env (jamais commité dans Git)


def get_db_url() -> str:
    return (
        f"postgresql+psycopg2://"
        f"{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
        f"/{os.getenv('DB_NAME', 'FactoryManager')}"
    )


engine = create_engine(
    get_db_url(),
    pool_size=20,        # connexions maintenues en permanence
    max_overflow=10,     # connexions supplémentaires en pic de charge
    pool_timeout=30,     # secondes d'attente max avant erreur
    pool_pre_ping=True,  # vérifie la connexion avant chaque utilisation
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


# ─── Dépendance FastAPI : 1 session par requête HTTP ─────────────────────────
def get_db():
    """
    Injectée via Depends(get_db) dans chaque endpoint.
    Garantit qu'une session est ouverte ET fermée pour chaque requête,
    même en cas d'erreur — indispensable en multi-utilisateurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
