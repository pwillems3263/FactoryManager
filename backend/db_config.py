"""
db_config.py
------------
Gestion centralisée des paramètres de connexion PostgreSQL.

- Lecture/écriture dans un fichier .env à la racine du projet
- Fonction get_db_url() utilisée par database.py ET migrations/env.py
- Fonction test_connection() utilisée par DBConfigView
"""

from pathlib import Path

# Chemin du .env : même dossier que ce fichier (racine du projet)
import sys

# Détecte si on tourne dans un exe PyInstaller ou en dev
if getattr(sys, 'frozen', False):
    # Exe PyInstaller → dossier de l'exe
    _BASE_DIR = Path(sys.executable).parent
else:
    # Dev → dossier du fichier source
    _BASE_DIR = Path(__file__).parent

ENV_PATH = _BASE_DIR / ".env"

# Paramètres actuels du projet (repris depuis alembic.ini)
DEFAULTS = {
    "DB_HOST":     "localhost",
    "DB_PORT":     "5432",
    "DB_NAME":     "FactoryManager",
    "DB_USER":     "postgres",
    "DB_PASSWORD": "postgres",
}


def load_env() -> dict:
    """Charge les paramètres depuis le fichier .env.
    Retourne un dict avec les valeurs (ou les défauts si absent)."""
    params = dict(DEFAULTS)

    if not ENV_PATH.exists():
        return params

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key   = key.strip()
                value = value.strip().strip('"').strip("'")
                if key in params:
                    params[key] = value

    return params


def save_env(params: dict) -> None:
    """Sauvegarde les paramètres dans le fichier .env."""
    lines = [
        "# FactoryManager — paramètres de connexion PostgreSQL",
        "# Ce fichier ne doit PAS être commité dans le dépôt Git.",
        "",
    ]
    for key in DEFAULTS:
        value = params.get(key, DEFAULTS[key])
        lines.append(f"{key}={value}")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def get_db_url() -> str:
    """Retourne l'URL de connexion SQLAlchemy à partir du .env."""
    p = load_env()
    return (
        f"postgresql+psycopg2://{p['DB_USER']}:{p['DB_PASSWORD']}"
        f"@{p['DB_HOST']}:{p['DB_PORT']}/{p['DB_NAME']}"
    )


def test_connection(params: dict) -> tuple[bool, str]:
    """
    Teste une connexion avec les paramètres fournis.
    Retourne (True, "OK") ou (False, "message d'erreur").
    """
    try:
        from sqlalchemy import create_engine, text

        url = (
            f"postgresql+psycopg2://{params['DB_USER']}:{params['DB_PASSWORD']}"
            f"@{params['DB_HOST']}:{params['DB_PORT']}/{params['DB_NAME']}"
        )
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True, "Connection successful."

    except Exception as e:
        msg = str(e)
        if "password authentication" in msg:
            return False, "Authentication failed: wrong username or password."
        if "could not connect" in msg or "Connection refused" in msg:
            return False, f"Cannot reach server at {params['DB_HOST']}:{params['DB_PORT']}."
        if "does not exist" in msg:
            return False, f"Database '{params['DB_NAME']}' does not exist."
        return False, f"Connection error: {msg[:200]}"